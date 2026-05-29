package config

import "os"

type Config struct {
	ServiceName string
	Port        string
	AppEnv      string
	LogLevel    string
}

func Load() *Config {
	return &Config{
		ServiceName: getEnv("SERVICE_NAME", "__SERVICE_NAME__"),
		Port:        getEnv("APP_PORT", "8000"),
		AppEnv:      getEnv("APP_ENV", "development"),
		LogLevel:    getEnv("LOG_LEVEL", "info"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
