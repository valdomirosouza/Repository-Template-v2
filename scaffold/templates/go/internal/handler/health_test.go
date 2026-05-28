package handler_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/yourorg/monorepo/services/__SERVICE_NAME__/internal/config"
	"github.com/yourorg/monorepo/services/__SERVICE_NAME__/internal/handler"
)

func TestHealthReturnsOK(t *testing.T) {
	cfg := &config.Config{ServiceName: "__SERVICE_NAME__", Port: "8000"}
	mux := http.NewServeMux()
	handler.Register(mux, cfg)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rr.Code)
	}
	var body map[string]string
	if err := json.NewDecoder(rr.Body).Decode(&body); err != nil {
		t.Fatalf("decode error: %v", err)
	}
	if body["status"] != "ok" {
		t.Errorf("expected status=ok, got %q", body["status"])
	}
}

func TestReadyReturnsReady(t *testing.T) {
	cfg := &config.Config{ServiceName: "__SERVICE_NAME__", Port: "8000"}
	mux := http.NewServeMux()
	handler.Register(mux, cfg)

	req := httptest.NewRequest(http.MethodGet, "/ready", nil)
	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rr.Code)
	}
}
