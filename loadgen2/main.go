package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	"golang.org/x/time/rate"

	"github.com/gagliardetto/solana-go"
	"github.com/gagliardetto/solana-go/programs/system"
	"github.com/gagliardetto/solana-go/rpc"
)

type Stats struct {
	PayerPubkey  string  `json:"payer_pubkey"`
	TargetLambda float64 `json:"target_lambda"`

	SentTotal uint64 `json:"sent_total"`
	OkTotal   uint64 `json:"ok_total"`
	ErrTotal  uint64 `json:"err_total"`

	Inflight    int32 `json:"inflight"`
	InflightMax int   `json:"inflight_max"`

	SentPerSec float64 `json:"sent_per_sec"`
	ErrPerSec  float64 `json:"err_per_sec"`

	LastErr string `json:"last_err"`
	TS      string `json:"ts"`
}

func main() {
	// ---- flags
	rpcURL := flag.String("rpc", "http://127.0.0.1:8899", "Solana RPC URL")
	keypairPath := flag.String("keypair", "", "Path to solana keypair json (array of ints)")
	listen := flag.String("listen", "127.0.0.1:7070", "HTTP listen address")
	workers := flag.Int("workers", 16, "Number of worker goroutines")
	inflightMax := flag.Int("inflight", 128, "Max inflight tx")
	burst := flag.Int("burst", 1, "Rate limiter burst (>=1)")
	lambda0 := flag.Float64("lambda", 20, "Initial target lambda tx/s")
	skipPreflight := flag.Bool("skip-preflight", true, "Skip preflight to increase throughput")
	flag.Parse()

	if *keypairPath == "" {
		log.Fatalf("missing -keypair")
	}
	if *workers <= 0 {
		log.Fatalf("-workers must be > 0")
	}
	if *inflightMax <= 0 {
		log.Fatalf("-inflight must be > 0")
	}
	if *burst < 1 {
		*burst = 1
	}
	if *lambda0 < 0 {
		*lambda0 = 0
	}

	// ---- keypair
	priv, err := solana.PrivateKeyFromSolanaKeygenFile(*keypairPath)
	if err != nil {
		log.Fatalf("failed to read keypair: %v", err)
	}
	payer := priv.PublicKey().String()

	// ---- rpc client
	client := rpc.New(*rpcURL)

	// ---- context
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// ---- shared / atomics
	var (
		targetBits atomic.Uint64 // math.Float64bits
		sentTotal  atomic.Uint64
		okTotal    atomic.Uint64
		errTotal   atomic.Uint64

		inflight atomic.Int32

		sentThisSec atomic.Uint64
		errThisSec  atomic.Uint64

		sentPerSec atomic.Uint64 // float64bits
		errPerSec  atomic.Uint64 // float64bits

		lastErr atomic.Value // string
	)

	lastErr.Store("")

	setTarget := func(x float64) {
		if x < 0 {
			x = 0
		}
		targetBits.Store(math.Float64bits(x))
	}

	getTarget := func() float64 {
		return math.Float64frombits(targetBits.Load())
	}

	setTarget(*lambda0)

	// ---- limiter (dynamic)
	lim := rate.NewLimiter(rate.Limit(*lambda0), *burst)

	// ---- blockhash refresher
	var bh atomic.Value // solana.Hash
	bh.Store(solana.Hash{}) // zero initially

	refreshBlockhash := func() {
		// commitment processed is enough for loadgen
		resp, e := client.GetLatestBlockhash(ctx, rpc.CommitmentProcessed)
		if e != nil {
			lastErr.Store(fmt.Sprintf("GetLatestBlockhash: %v", e))
			return
		}
		bh.Store(resp.Value.Blockhash)
	}

	refreshBlockhash()
	go func() {
		t := time.NewTicker(700 * time.Millisecond)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				refreshBlockhash()
			}
		}
	}()

	// ---- per-second counters sampler
	go func() {
		t := time.NewTicker(1 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				s := sentThisSec.Swap(0)
				e := errThisSec.Swap(0)
				sentPerSec.Store(math.Float64bits(float64(s)))
				errPerSec.Store(math.Float64bits(float64(e)))
			}
		}
	}()

	// ---- inflight semaphore
	sem := make(chan struct{}, *inflightMax)

	// ---- worker loop: builds and sends tx
	sendOne := func() {
		// inflight cap
		sem <- struct{}{}
		inflight.Add(1)
		defer func() {
			inflight.Add(-1)
			<-sem
		}()

		// get current blockhash
		h := bh.Load().(solana.Hash)
		if h.IsZero() {
			// try refresh once
			refreshBlockhash()
			h = bh.Load().(solana.Hash)
			if h.IsZero() {
				errTotal.Add(1)
				errThisSec.Add(1)
				lastErr.Store("blockhash is zero")
				return
			}
		}

		// simple transfer 1 lamport to self (pays fee anyway)
		ix := system.NewTransferInstruction(
			1,
			priv.PublicKey(),
			priv.PublicKey(),
		).Build()

		tx, e := solana.NewTransaction(
			[]solana.Instruction{ix},
			h,
			solana.TransactionPayer(priv.PublicKey()),
		)
		if e != nil {
			errTotal.Add(1)
			errThisSec.Add(1)
			lastErr.Store(fmt.Sprintf("NewTransaction: %v", e))
			return
		}

		_, e = tx.Sign(func(key solana.PublicKey) *solana.PrivateKey {
			if key.Equals(priv.PublicKey()) {
				return &priv
			}
			return nil
		})
		if e != nil {
			errTotal.Add(1)
			errThisSec.Add(1)
			lastErr.Store(fmt.Sprintf("Sign: %v", e))
			return
		}

		// rate-limit happens outside
		sentTotal.Add(1)
		sentThisSec.Add(1)

		_, e = client.SendTransactionWithOpts(ctx, tx, rpc.TransactionOpts{
			SkipPreflight:       *skipPreflight,
			PreflightCommitment: rpc.CommitmentProcessed,
			MaxRetries:          nil,
		})
		if e != nil {
			errTotal.Add(1)
			errThisSec.Add(1)
			lastErr.Store(fmt.Sprintf("SendTransaction: %v", e))
			return
		}
		okTotal.Add(1)
	}

	worker := func() {
		for {
			select {
			case <-ctx.Done():
				return
			default:
			}

			// dynamic lambda
			lam := getTarget()
			if lam <= 0 {
				time.Sleep(200 * time.Millisecond)
				continue
			}
			lim.SetLimit(rate.Limit(lam))

			// wait for token
			if e := lim.Wait(ctx); e != nil {
				return
			}

			sendOne()
		}
	}

	for i := 0; i < *workers; i++ {
		go worker()
	}

	// ---- HTTP server
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	mux.HandleFunc("/stats", func(w http.ResponseWriter, r *http.Request) {
		st := Stats{
			PayerPubkey:  payer,
			TargetLambda: getTarget(),

			SentTotal: sentTotal.Load(),
			OkTotal:   okTotal.Load(),
			ErrTotal:  errTotal.Load(),

			Inflight:    inflight.Load(),
			InflightMax: *inflightMax,

			SentPerSec: math.Float64frombits(sentPerSec.Load()),
			ErrPerSec:  math.Float64frombits(errPerSec.Load()),

			LastErr: lastErr.Load().(string),
			TS:      time.Now().Format(time.RFC3339Nano),
		}

		w.Header().Set("Content-Type", "application/json")
		enc := json.NewEncoder(w)
		enc.SetEscapeHTML(false)
		_ = enc.Encode(&st) // always valid JSON + newline
	})

	mux.HandleFunc("/rate", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "POST required", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			Lambda float64 `json:"lambda"`
		}
		dec := json.NewDecoder(r.Body)
		if err := dec.Decode(&req); err != nil {
			http.Error(w, "bad json", http.StatusBadRequest)
			return
		}
		setTarget(req.Lambda)
		w.WriteHeader(http.StatusOK)
	})

	srv := &http.Server{
		Addr:              *listen,
		Handler:           mux,
		ReadHeaderTimeout: 3 * time.Second,
	}

	// Ensure we bind only to requested interface
	ln, err := net.Listen("tcp", *listen)
	if err != nil {
		log.Fatalf("listen %s: %v", *listen, err)
	}

	go func() {
		<-ctx.Done()
		shCtx, cancel2 := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel2()
		_ = srv.Shutdown(shCtx)
	}()

	log.Printf("loadgen2: payer=%s rpc=%s listen=%s workers=%d inflight=%d lambda=%.2f",
		payer, *rpcURL, *listen, *workers, *inflightMax, *lambda0)

	if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
		log.Printf("http server error: %v", err)
		os.Exit(1)
	}
}

