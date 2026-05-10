package utils

import (
	"fmt"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Config 定义运行时配置映射，与 YAML 结构保持一致。
type Config struct {
	RPC      string        `mapstructure:"rpc"`
	GRPC     string        `mapstructure:"grpc"`
	Interval time.Duration `mapstructure:"interval"`
	LogLevel string        `mapstructure:"log_level"`
	Metrics  MetricsConfig `mapstructure:"metrics"`
	Filters  FilterConfig  `mapstructure:"filters"`
	Reconnect RetryConfig  `mapstructure:"reconnect"`
}

// MetricsConfig 管理指标端口配置。
type MetricsConfig struct {
	PrometheusPort int `mapstructure:"prometheus_port"`
}

// FilterConfig 定义账户等过滤条件。
type FilterConfig struct {
	Accounts []string `mapstructure:"accounts"`
}

// RetryConfig 控制重连策略。
type RetryConfig struct {
	Retries int           `mapstructure:"retries"`
	Backoff time.Duration `mapstructure:"backoff"`
}

// LoadConfig 使用 viper 解析 YAML，并对字符串时长配置进行转换。
func LoadConfig(path string) (*Config, error) {
	v := viper.New()
	v.SetConfigFile(path)
	v.SetConfigType("yaml")
	v.SetEnvPrefix("SLR")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("读取配置失败: %w", err)
	}

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("配置解析失败: %w", err)
	}

	if cfg.Interval == 0 {
		cfg.Interval = 5 * time.Second
	}
	if cfg.Reconnect.Backoff == 0 {
		cfg.Reconnect.Backoff = 2 * time.Second
	}
	return &cfg, nil
}
