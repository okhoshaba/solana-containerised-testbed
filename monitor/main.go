package main

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/spf13/pflag"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/proto"

	geyserpb "github.com/rpcpool/yellowstone-grpc/examples/golang/proto"

	"solana-latency-research/internal/metrics"
	"solana-latency-research/internal/utils"
)

func main() {
	logger := log.New(os.Stdout, "[solana-latency] ", log.LstdFlags|log.Lmicroseconds)

	flags := pflag.NewFlagSet(os.Args[0], pflag.ExitOnError)
	configPath := flags.String("config", "configs/config.example.yaml", "Path to YAML config file")
	overrideGRPC := flags.String("grpc-endpoint", "", "Override gRPC endpoint (host:port)")
	overrideAccount := flags.StringSlice("account", nil, "Override account subscription list (comma-separated)")

	if err := flags.Parse(os.Args[1:]); err != nil {
		logger.Fatalf("Failed to parse flags: %v", err)
	}

	cfg, err := utils.LoadConfig(*configPath)
	if err != nil {
		logger.Fatalf("Failed to load config: %v", err)
	}

	if flags.Changed("grpc-endpoint") && *overrideGRPC != "" {
		cfg.GRPC = *overrideGRPC
	}
	if flags.Changed("account") && len(*overrideAccount) > 0 {
		cfg.Filters.Accounts = *overrideAccount
	}

	logger.Printf("Starting Solana latency monitor. gRPC endpoint: %s", cfg.GRPC)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	col := metrics.NewCollector()
	if cfg.Metrics.PrometheusPort > 0 {
		go exposeMetrics(ctx, cfg.Metrics.PrometheusPort, col, logger)
	}

	conn, err := dialWithRetry(ctx, cfg.GRPC, cfg.Reconnect, logger)
	if err != nil {
		logger.Fatalf("Failed to connect to Yellowstone gRPC: %v", err)
	}
	defer conn.Close()

	logger.Printf("gRPC connection established. Starting live subscriptions (slots + transactions).")

	client := geyserpb.NewGeyserClient(conn)

	accounts := normalizeAccounts(cfg.Filters.Accounts)
	if len(accounts) == 0 {
		logger.Printf("WARNING: filters.accounts is empty after trimming. " +
			"Yellowstone forbids full tx stream with `any`. Tx-latency will be DISABLED.")
	}

	go subscribeSlotsLoop(ctx, client, cfg.Reconnect, col, logger)

	if len(accounts) > 0 {
		logger.Printf("tx: AccountInclude filters: %v", accounts)
		go subscribeTxLatencyLoop(ctx, client, cfg.Reconnect, accounts, col, logger)
	}

	<-ctx.Done()
	logger.Println("Shutdown signal received. Exiting.")
}

func normalizeAccounts(in []string) []string {
	out := make([]string, 0, len(in))
	seen := make(map[string]struct{}, len(in))
	for _, a := range in {
		s := strings.TrimSpace(a)      // removes \r \n spaces
		s = strings.Trim(s, `"'`)      // defensive: remove accidental quotes
		if s == "" {
			continue
		}
		if _, ok := seen[s]; ok {
			continue
		}
		seen[s] = struct{}{}
		out = append(out, s)
	}
	return out
}

func ptrCommitment(c geyserpb.CommitmentLevel) *geyserpb.CommitmentLevel { return &c }

func dialWithRetry(ctx context.Context, endpoint string, retryCfg utils.RetryConfig, logger *log.Logger) (*grpc.ClientConn, error) {
	if retryCfg.Backoff <= 0 {
		retryCfg.Backoff = 2 * time.Second
	}

	var attempt int
	for {
		attempt++
		conn, err := grpc.DialContext(
			ctx,
			endpoint,
			grpc.WithTransportCredentials(insecure.NewCredentials()),
			grpc.WithBlock(),
			grpc.WithReturnConnectionError(),
		)
		if err == nil {
			return conn, nil
		}

		logger.Printf("Connection attempt %d failed: %v", attempt, err)
		if retryCfg.Retries >= 0 && attempt > retryCfg.Retries {
			return nil, fmt.Errorf("exceeded max retries (%d): %w", retryCfg.Retries, err)
		}

		select {
		case <-ctx.Done():
			return nil, errors.Join(err, ctx.Err())
		case <-time.After(retryCfg.Backoff):
		}
	}
}

func exposeMetrics(ctx context.Context, port int, col *metrics.Collector, logger *log.Logger) {
	addr := fmt.Sprintf("0.0.0.0:%d", port)
	mux := http.NewServeMux()
	mux.Handle("/metrics", col.Handler())

	srv := &http.Server{
		Addr:              addr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := srv.Shutdown(shutdownCtx); err != nil {
			logger.Printf("Error shutting down Prometheus HTTP server: %v", err)
		}
	}()

	logger.Printf("Prometheus metrics exposed on %s", addr)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Printf("Prometheus server stopped unexpectedly: %v", err)
	}
}

func subscribeSlotsLoop(ctx context.Context, client geyserpb.GeyserClient, retryCfg utils.RetryConfig, col *metrics.Collector, logger *log.Logger) {
	if retryCfg.Backoff <= 0 {
		retryCfg.Backoff = 2 * time.Second
	}

	var prev time.Time

	for {
		if ctx.Err() != nil {
			return
		}

		stream, err := client.Subscribe(ctx)
		if err != nil {
			logger.Printf("slots: Subscribe() failed: %v", err)
			select {
			case <-ctx.Done():
				return
			case <-time.After(retryCfg.Backoff):
				continue
			}
		}

		req := &geyserpb.SubscribeRequest{
			Commitment: ptrCommitment(geyserpb.CommitmentLevel_PROCESSED),
			Slots: map[string]*geyserpb.SubscribeRequestFilterSlots{
				"slots": {
					FilterByCommitment: proto.Bool(true),
					InterslotUpdates:   proto.Bool(false),
				},
			},
		}

		if err := stream.Send(req); err != nil {
			logger.Printf("slots: stream.Send() failed: %v", err)
			_ = stream.CloseSend()
			select {
			case <-ctx.Done():
				return
			case <-time.After(retryCfg.Backoff):
				continue
			}
		}

		for {
			upd, err := stream.Recv()
			if err != nil {
				logger.Printf("slots: stream.Recv() ended: %v", err)
				break
			}

			slotUpd := upd.GetSlot()
			if slotUpd == nil {
				continue
			}

			// created_at works fine for slot cadence
			now := time.Now()
			if t := upd.GetCreatedAt(); t != nil {
				now = t.AsTime()
			}

			if slotUpd.GetStatus() == geyserpb.SlotStatus_SLOT_PROCESSED {
				if !prev.IsZero() {
					delta := now.Sub(prev).Seconds()
					if delta < 0 {
						delta = 0
					}
					col.SlotInterval.Observe(delta)
					logJSON(logger, map[string]any{
						"stream":           "slot",
						"publisher":        "yellowstone",
						"slot":             slotUpd.GetSlot(),
						"status":           slotUpd.GetStatus().String(),
						"interval_seconds": delta,
						"timestamp":        now.Format(time.RFC3339Nano),
					})
				}
				prev = now
			}
		}

		_ = stream.CloseSend()
		select {
		case <-ctx.Done():
			return
		case <-time.After(retryCfg.Backoff):
		}
	}
}

func subscribeTxLatencyLoop(ctx context.Context, client geyserpb.GeyserClient, retryCfg utils.RetryConfig, accounts []string, col *metrics.Collector, logger *log.Logger) {
	if retryCfg.Backoff <= 0 {
		retryCfg.Backoff = 2 * time.Second
	}

	firstSeen := make(map[string]time.Time)
	var mu sync.Mutex

	var procSeen, confSeen, matched uint64

	// periodic diagnostics (every 10s)
	go func() {
		t := time.NewTicker(10 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				mu.Lock()
				fs := len(firstSeen)
				ps := procSeen
				cs := confSeen
				mm := matched
				mu.Unlock()
				logger.Printf("tx_diag: processed_seen=%d confirmed_seen=%d matched=%d firstSeen_map=%d", ps, cs, mm, fs)
			}
		}
	}()

	// TTL cleanup
	const entryTTL = 120 * time.Second
	const cleanupEvery = 10 * time.Second
	go func() {
		t := time.NewTicker(cleanupEvery)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				cut := time.Now().Add(-entryTTL)
				mu.Lock()
				for k, v := range firstSeen {
					if v.Before(cut) {
						delete(firstSeen, k)
					}
				}
				mu.Unlock()
			}
		}
	}()

	for {
		if ctx.Err() != nil {
			return
		}

		// PROCESSED tx stream (sets t0)
		txStream, err := client.Subscribe(ctx)
		if err != nil {
			logger.Printf("tx: Subscribe(PROCESSED) failed: %v", err)
			select {
			case <-ctx.Done():
				return
			case <-time.After(retryCfg.Backoff):
				continue
			}
		}

		txReq := &geyserpb.SubscribeRequest{
			Commitment: ptrCommitment(geyserpb.CommitmentLevel_PROCESSED),
			Transactions: map[string]*geyserpb.SubscribeRequestFilterTransactions{
				"tx": {AccountInclude: accounts},
			},
		}
		if err := txStream.Send(txReq); err != nil {
			logger.Printf("tx: stream.Send(PROCESSED) failed: %v", err)
			_ = txStream.CloseSend()
			select {
			case <-ctx.Done():
				return
			case <-time.After(retryCfg.Backoff):
				continue
			}
		}

		// CONFIRMED status stream (computes latency)
		stStream, err := client.Subscribe(ctx)
		if err != nil {
			logger.Printf("tx: Subscribe(CONFIRMED status) failed: %v", err)
			_ = txStream.CloseSend()
			select {
			case <-ctx.Done():
				return
			case <-time.After(retryCfg.Backoff):
				continue
			}
		}

		stReq := &geyserpb.SubscribeRequest{
			Commitment: ptrCommitment(geyserpb.CommitmentLevel_CONFIRMED),
			TransactionsStatus: map[string]*geyserpb.SubscribeRequestFilterTransactions{
				"tx_status": {AccountInclude: accounts},
			},
		}
		if err := stStream.Send(stReq); err != nil {
			logger.Printf("tx: stream.Send(CONFIRMED status) failed: %v", err)
			_ = stStream.CloseSend()
			_ = txStream.CloseSend()
			select {
			case <-ctx.Done():
				return
			case <-time.After(retryCfg.Backoff):
				continue
			}
		}

		done := make(chan struct{})
		go func() {
			defer close(done)
			for {
				upd, err := txStream.Recv()
				if err != nil {
					logger.Printf("tx: PROCESSED Recv() ended: %v", err)
					return
				}
				tu := upd.GetTransaction()
				if tu == nil {
					continue
				}
				info := tu.GetTransaction()
				if info == nil {
					continue
				}
				sig := info.GetSignature()
				if len(sig) == 0 {
					continue
				}
				key := hex.EncodeToString(sig)

				// LOCAL receive time
				now := time.Now()

				mu.Lock()
				procSeen++
				if _, ok := firstSeen[key]; !ok {
					firstSeen[key] = now
				}
				mu.Unlock()
			}
		}()

		for {
			upd, err := stStream.Recv()
			if err != nil {
				logger.Printf("tx: CONFIRMED status Recv() ended: %v", err)
				break
			}

			su := upd.GetTransactionStatus()
			if su == nil {
				continue
			}

			sig := su.GetSignature()
			if len(sig) == 0 {
				continue
			}
			key := hex.EncodeToString(sig)

			// LOCAL receive time
			now := time.Now()

			mu.Lock()
			confSeen++
			t0, ok := firstSeen[key]
			if ok {
				delete(firstSeen, key)
				matched++
			}
			mu.Unlock()

			if !ok {
				continue
			}

			latency := now.Sub(t0).Seconds()
			if latency < 0 {
				latency = 0
			}
			col.TransactionDelay.Observe(latency)

			logJSON(logger, map[string]any{
				"stream":              "transaction",
				"publisher":           "yellowstone",
				"latency_seconds":      latency,
				"signature_hex":        key,
				"slot":                 su.GetSlot(),
				"timestamp_local_recv": now.Format(time.RFC3339Nano),
				"accounts":             accounts,
			})
		}

		_ = stStream.CloseSend()
		_ = txStream.CloseSend()
		<-done

		select {
		case <-ctx.Done():
			return
		case <-time.After(retryCfg.Backoff):
		}
	}
}

func logJSON(logger *log.Logger, payload map[string]any) {
	data, err := json.Marshal(payload)
	if err != nil {
		logger.Printf("Failed to encode JSON log payload: %v", err)
		return
	}
	logger.Printf("%s", data)
}

