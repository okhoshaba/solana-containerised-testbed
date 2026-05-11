package metrics

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Collector aggregates commonly used metrics for direct use in application code.
type Collector struct {
	registry         *prometheus.Registry
	SlotInterval     prometheus.Observer
	TransactionDelay prometheus.Observer
	Errors           *prometheus.CounterVec
}

// NewCollector initializes a custom registry to avoid polluting the global metrics registry.
func NewCollector() *Collector {
	reg := prometheus.NewRegistry()
	slot := promauto.With(reg).NewSummary(prometheus.SummaryOpts{
		Name:       "solana_slot_interval_seconds",
		Help:       "Time interval between consecutive Solana slots, used to measure slot production stability.",
		Objectives: map[float64]float64{0.5: 0.01, 0.9: 0.01, 0.99: 0.001},
	})
	tx := promauto.With(reg).NewSummary(prometheus.SummaryOpts{
		Name:       "solana_transaction_latency_seconds",
		Help:       "Latency distribution from transaction broadcast to confirmation.",
		Objectives: map[float64]float64{0.5: 0.01, 0.95: 0.005, 0.99: 0.001},
	})
	errors := promauto.With(reg).NewCounterVec(prometheus.CounterOpts{
		Name: "solana_stream_errors_total",
		Help: "Total number of errors observed in the subscription stream.",
	}, []string{"stream"})

	return &Collector{
		registry:         reg,
		SlotInterval:     slot,
		TransactionDelay: tx,
		Errors:           errors,
	}
}

// Registry exposes the internal registry for use by the HTTP handler.
func (c *Collector) Registry() *prometheus.Registry {
	return c.registry
}

// Handler returns a Prometheus-compatible metrics handler.
func (c *Collector) Handler() http.Handler {
	return promhttp.HandlerFor(c.registry, promhttp.HandlerOpts{})
}
