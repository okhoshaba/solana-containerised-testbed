package metrics

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Collector 聚合常用指标，便于在业务代码中直接记录。
type Collector struct {
	registry         *prometheus.Registry
	SlotInterval     prometheus.Observer
	TransactionDelay prometheus.Observer
	Errors           *prometheus.CounterVec
}

// NewCollector 初始化自定义 registry，避免污染全局指标。
func NewCollector() *Collector {
	reg := prometheus.NewRegistry()
	slot := promauto.With(reg).NewSummary(prometheus.SummaryOpts{
		Name:       "solana_slot_interval_seconds",
		Help:       "记录连续 slot 之间的时间差，用于衡量出块间隔稳定性。",
		Objectives: map[float64]float64{0.5: 0.01, 0.9: 0.01, 0.99: 0.001},
	})
	tx := promauto.With(reg).NewSummary(prometheus.SummaryOpts{
		Name:       "solana_transaction_latency_seconds",
		Help:       "记录交易从广播到确认的延迟分布。",
		Objectives: map[float64]float64{0.5: 0.01, 0.95: 0.005, 0.99: 0.001},
	})
	errors := promauto.With(reg).NewCounterVec(prometheus.CounterOpts{
		Name: "solana_stream_errors_total",
		Help: "统计订阅流中的错误次数。",
	}, []string{"stream"})

	return &Collector{
		registry:         reg,
		SlotInterval:     slot,
		TransactionDelay: tx,
		Errors:           errors,
	}
}

// Registry 暴露内部 registry，供 HTTP Handler 使用。
func (c *Collector) Registry() *prometheus.Registry {
	return c.registry
}

// Handler 返回 Prometheus 兼容的指标 Handler。
func (c *Collector) Handler() http.Handler {
	return promhttp.HandlerFor(c.registry, promhttp.HandlerOpts{})
}
