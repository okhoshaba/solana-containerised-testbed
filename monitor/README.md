# Solana Latency Research

A high-performance trading infrastructure and research framework for Solana,
focused on studying **transaction propagation**, **block inclusion latency**, and
**order execution efficiency** across validators.

## Features
- Real-time subscription via gRPC and WebSocket
- Latency measurement and statistical visualization
- Configurable connection to public or self-hosted RPC nodes
- Designed for quantitative strategy and execution research

## Example Usage
```bash
go run main.go --config configs/config.example.yaml
```

Example configuration:
rpc: "https://api.mainnet-beta.solana.com"
grpc: "solana-yellowstone-grpc.publicnode.com:443"
interval: 5s
log_level: info

🧪 Research Goals
	•	Measure end-to-end transaction latency across validators
	•	Analyze shred and block propagation in real time
	•	Benchmark different validator locations for optimal routing
	•	Improve trading execution timing for quantitative strategies

⸻

🔬 Tech Stack
	•	Go 1.22
	•	gRPC
	•	Prometheus (for metrics)
	•	Plotly / Grafana (for visualization)

Research Focus

This project analyzes:
	•	Block inclusion delay between validators
	•	Propagation time of shreds and bundles
	•	Transaction confirmation latency

License

MIT License © 2025 tongor
