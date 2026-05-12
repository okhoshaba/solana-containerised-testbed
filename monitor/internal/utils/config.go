package utils

import (
	"fmt"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Config defines the runtime configuration mapping and mirrors the YAML structure.
type Config struct {
	RPC      string        `mapstructure:"rpc"`
	GRPC     string        `mapstructure:"grpc"`
	Interval time.Duration `mapstructure:"interval"`
	LogLevel string        `mapstructure:"log_level"`
	Metrics  MetricsConfig `mapstructure:"metrics"`
	Filters  FilterConfig  `mapstructure:"filters"`
	Reconnect RetryConfig  `mapstructure:"reconnect"`
}

// MetricsConfig manages metrics port configuration.
type MetricsConfig struct {
	PrometheusPort int `mapstructure:"prometheus_port"`
}

// FilterConfig defines account and related filtering conditions.
type FilterConfig struct {
	Accounts []string `mapstructure:"accounts"`
}

// RetryConfig controls reconnect behaviour.
type RetryConfig struct {
	Retries int           `mapstructure:"retries"`
	Backoff time.Duration `mapstructure:"backoff"`
}

// LoadConfig parses YAML using viper and converts string-based duration values.
func LoadConfig(path string) (*Config, error) {
	v := viper.New()
	v.SetConfigFile(path)
	v.SetConfigType("yaml")
	v.SetEnvPrefix("SLR")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	if cfg.Interval == 0 {
		cfg.Interval = 5 * time.Second
	}
	if cfg.Reconnect.Backoff == 0 {
		cfg.Reconnect.Backoff = 2 * time.Second
	}
	return &cfg, nil
}
