FROM golang:1.24-bookworm AS builder

WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/solana-latency-monitor .

FROM debian:bookworm-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl bash \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /out/solana-latency-monitor /usr/local/bin/solana-latency-monitor
COPY configs /app/configs

EXPOSE 9464

ENTRYPOINT ["solana-latency-monitor"]
CMD ["--config", "/app/configs/config.local.yaml"]
