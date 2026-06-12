package com.yourorg.goldensignals.infra;

import com.yourorg.goldensignals.domain.Bucket;
import com.yourorg.goldensignals.domain.Signal;
import com.yourorg.goldensignals.domain.Window;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/**
 * Production Redis-backed {@link MetricStore} (ADR-0067), selected by the
 * {@code redis} Spring profile. <strong>STUB</strong> for the Phase-6 build:
 * the in-memory store is the build/test default (no external Redis), and the
 * full Lettuce/TLS implementation (key grammar per ADR-0068 §4, sorted-set
 * latency samples, per-window {@code EXPIRE} TTL from {@code RETENTION_1M_SECONDS}
 * /{@code RETENTION_5M_SECONDS}) is delivered in a later phase. Every method
 * fails fast so an accidental {@code redis}-profile run never silently no-ops.
 *
 * <p>This class is the seam ADR-0067 names; {@link InMemoryMetricStore} proves
 * the contract and {@code RedisStoreContractTest} (Phase 8) will prove parity.
 */
@Component
@Profile("redis")
public class RedisMetricStore implements MetricStore {

    private static final String NOT_IMPLEMENTED =
            "RedisMetricStore is a Phase-6 stub; the in-memory store is the build/test default "
                    + "(ADR-0067). Full Lettuce/TLS impl lands in a later phase.";

    @Override
    public void persist(final Bucket bucket) {
        throw new UnsupportedOperationException(NOT_IMPLEMENTED);
    }

    @Override
    public List<Bucket> query(
            final String path, final Signal signal, final Window window,
            final Instant from, final Instant to) {
        throw new UnsupportedOperationException(NOT_IMPLEMENTED);
    }

    @Override
    public Set<String> trackedPaths() {
        throw new UnsupportedOperationException(NOT_IMPLEMENTED);
    }

    @Override
    public boolean ping() {
        // A real impl would PING Redis; the stub reports "not connected" so
        // /analytics/health surfaces 503 rather than pretending health (FR-09, NFR-06).
        return false;
    }
}
