package health_test

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/yourorg/monorepo/services/event-worker/internal/health"
)

func TestLiveness_AlwaysReturns200(t *testing.T) {
	srv := health.New()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rr.Code)
	}
}

func TestLiveness_Returns200WhenNotReady(t *testing.T) {
	srv := health.New() // ready=false by default
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("liveness must return 200 regardless of ready state, got %d", rr.Code)
	}
}

func TestReadiness_Returns503WhenNotReady(t *testing.T) {
	srv := health.New()
	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503 before SetReady, got %d", rr.Code)
	}
}

func TestReadiness_Returns200AfterSetReady(t *testing.T) {
	srv := health.New()
	srv.SetReady(true)
	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("expected 200 after SetReady(true), got %d", rr.Code)
	}
}

func TestReadiness_Returns503AfterUnset(t *testing.T) {
	srv := health.New()
	srv.SetReady(true)
	srv.SetReady(false)
	req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503 after SetReady(false), got %d", rr.Code)
	}
}

func TestIsReady_ReflectsSetReadyState(t *testing.T) {
	srv := health.New()
	if srv.IsReady() {
		t.Fatal("new server must not be ready")
	}
	srv.SetReady(true)
	if !srv.IsReady() {
		t.Fatal("expected IsReady() true after SetReady(true)")
	}
}

func TestUnknownPath_Returns404(t *testing.T) {
	srv := health.New()
	req := httptest.NewRequest(http.MethodGet, "/unknown", nil)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusNotFound {
		t.Fatalf("unknown path expected 404, got %d", rr.Code)
	}
}

func TestHandler_ConcurrentAccess(t *testing.T) {
	srv := health.New()
	done := make(chan struct{})
	for i := range 20 {
		go func(n int) {
			srv.SetReady(n%2 == 0)
			req := httptest.NewRequest(http.MethodGet, "/readyz", nil)
			rr := httptest.NewRecorder()
			srv.Handler().ServeHTTP(rr, req)
			done <- struct{}{}
		}(i)
	}
	for range 20 {
		<-done
	}
}
