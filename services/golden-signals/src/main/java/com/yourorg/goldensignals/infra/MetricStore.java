package com.yourorg.goldensignals.infra;

import com.yourorg.goldensignals.domain.Bucket;
import com.yourorg.goldensignals.domain.Signal;
import com.yourorg.goldensignals.domain.Window;
import java.time.Instant;
import java.util.List;
import java.util.Set;

/**
 * The time-series store seam (ADR-0067). All read/write goes through this
 * interface; an {@link InMemoryMetricStore} backs tests/local dev and a Redis
 * implementation (env {@code SPRING_PROFILES_ACTIVE=redis}) backs prod. The
 * InfluxDB/TimescaleDB exit path (ADR-0067) plugs in as a third implementation
 * with no caller change.
 */
public interface MetricStore {

    /**
     * Upsert (merge) one window aggregate plus its latency samples (FR-05/06).
     * Re-persisting the same {@code (path,window,epochBucket)} accumulates the
     * counts and appends the samples.
     *
     * @param bucket the aggregate snapshot to persist
     */
    void persist(Bucket bucket);

    /**
     * Range query buckets for a {@code (path, signal, window)} between {@code from}
     * (inclusive) and {@code to} (exclusive) (FR-07).
     *
     * @param path   the raw request path
     * @param signal the signal of interest
     * @param window the window
     * @param from   inclusive lower bound (by bucket start)
     * @param to     exclusive upper bound (by bucket start)
     * @return the matching buckets, ascending by bucket start (possibly empty)
     */
    List<Bucket> query(String path, Signal signal, Window window, Instant from, Instant to);

    /**
     * Every tracked path (FR-08).
     *
     * @return the set of raw (decoded) paths seen so far
     */
    Set<String> trackedPaths();

    /**
     * Liveness probe for the store (FR-09).
     *
     * @return true if the store is reachable/healthy
     */
    boolean ping();
}
