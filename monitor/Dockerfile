FROM golang:1.23-bookworm AS builder

WORKDIR /src

COPY . .

RUN if [ -f go.mod ]; then \
      go mod download && go build -o /out/solana-latency-monitor . ; \
    else \
      echo "monitor/go.mod not found. Add the monitoring source code later." && exit 1 ; \
    fi

FROM debian:bookworm-slim

WORKDIR /app

COPY --from=builder /out/solana-latency-monitor /usr/local/bin/solana-latency-monitor
COPY configs /app/configs

EXPOSE 9464

ENTRYPOINT ["solana-latency-monitor"]
CMD ["--config", "/app/configs/config.local.yaml"]
