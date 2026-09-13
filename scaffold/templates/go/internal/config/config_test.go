package config_test

import (
	"testing"

	"github.com/yourorg/monorepo/services/__SERVICE_NAME__/internal/config"
)

// Configuration validation (scaffold starter, W15-T5): defaults and env overrides.

func TestLoad_Defaults(t *testing.T) {
	t.Setenv("APP_PORT", "")
	t.Setenv("APP_ENV", "")
	cfg := config.Load()
	if cfg.Port != "8000" || cfg.AppEnv != "development" || cfg.LogLevel != "info" {
		t.Errorf("unexpected defaults: %+v", cfg)
	}
	if cfg.ServiceName != "__SERVICE_NAME__" {
		t.Errorf("service name default: %q", cfg.ServiceName)
	}
}

func TestLoad_EnvOverrides(t *testing.T) {
	t.Setenv("APP_PORT", "9001")
	t.Setenv("APP_ENV", "staging")
	t.Setenv("LOG_LEVEL", "debug")
	cfg := config.Load()
	if cfg.Port != "9001" || cfg.AppEnv != "staging" || cfg.LogLevel != "debug" {
		t.Errorf("overrides not applied: %+v", cfg)
	}
}
