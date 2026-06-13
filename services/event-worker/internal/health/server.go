// Package health provides a lightweight HTTP health server for Kubernetes probes.
// Serves /healthz (liveness) and /readyz (readiness) on a dedicated port (default 8081)
// so probe traffic is isolated from the Prometheus metrics port.
//
// Spec: specs/k8s/probe-strategy.md §3.3 | ADR-0042
package health

import (
	"fmt"
	"net/http"
	"sync/atomic"
	"time"
)

// Server holds the ready state for the /readyz probe.
type Server struct {
	ready atomic.Bool
}

// New returns a Server with ready=false (not ready until SetReady is called).
func New() *Server {
	return &Server{}
}

// SetReady marks the worker as ready to process events.
// Call this after the Kafka consumer group has completed its partition assignment.
func (s *Server) SetReady(v bool) {
	s.ready.Store(v)
}

// IsReady reports the current readiness state (used in tests).
func (s *Server) IsReady() bool {
	return s.ready.Load()
}

// Handler returns an http.Handler that serves /healthz and /readyz.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", s.handleLiveness)
	mux.HandleFunc("/readyz", s.handleReadiness)
	return mux
}

// Start runs the health HTTP server on the given port in a background goroutine.
// It never blocks; errors are swallowed after the goroutine exits.
func (s *Server) Start(port int) {
	addr := fmt.Sprintf(":%d", port)
	srv := &http.Server{Addr: addr, Handler: s.Handler(), ReadHeaderTimeout: 5 * time.Second}
	go func() { _ = srv.ListenAndServe() }()
}

func (s *Server) handleLiveness(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
}

func (s *Server) handleReadiness(w http.ResponseWriter, _ *http.Request) {
	if s.ready.Load() {
		w.WriteHeader(http.StatusOK)
		return
	}
	w.WriteHeader(http.StatusServiceUnavailable)
}
