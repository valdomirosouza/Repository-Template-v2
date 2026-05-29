package handler

import (
	"encoding/json"
	"net/http"

	"github.com/yourorg/monorepo/services/__SERVICE_NAME__/internal/config"
)

func Register(mux *http.ServeMux, cfg *config.Config) {
	mux.HandleFunc("GET /health", health(cfg))
	mux.HandleFunc("GET /ready", ready())
}

func health(cfg *config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"status":  "ok",
			"service": cfg.ServiceName,
		})
	}
}

func ready() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// TODO: add dependency checks (DB, Redis, etc.)
		writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
	}
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
