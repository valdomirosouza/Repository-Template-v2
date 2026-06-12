package com.yourorg.goldensignals.domain;

import java.util.ArrayList;
import java.util.List;

/**
 * Mutable accumulator for one {@code (path, window, epoch_bucket)} while the
 * worker drains the queue (ADR-0069). Tracks count / errors / saturation tallies
 * and the running latency sample list; {@link #toBucket()} snapshots it into an
 * immutable {@link Bucket} for persistence (FR-05).
 *
 * <p>Not thread-safe by itself: the single virtual-thread worker owns its
 * accumulators (ADR-0069 §3), so no external synchronisation is required there.
 */
public final class Aggregate {

    private final String path;
    private final Window window;
    private final long epochBucket;
    private long count;
    private long errors;
    private long saturated;
    private final List<Double> latencySamples = new ArrayList<>();

    public Aggregate(final String path, final Window window, final long epochBucket) {
        this.path = path;
        this.window = window;
        this.epochBucket = epochBucket;
    }

    /**
     * Fold one extracted event into this accumulator.
     *
     * @param event the signal event (its {@code path}/{@code timestamp} must already
     *              match this accumulator's bucket — the worker guarantees that)
     */
    public void add(final SignalEvent event) {
        count++;
        if (event.error()) {
            errors++;
        }
        if (event.saturated()) {
            saturated++;
        }
        latencySamples.add(event.responseTimeMs());
    }

    /** Snapshot this accumulator as an immutable {@link Bucket}. */
    public Bucket toBucket() {
        return new Bucket(path, window, epochBucket, count, errors, saturated, latencySamples);
    }

    public String path() {
        return path;
    }

    public Window window() {
        return window;
    }

    public long epochBucket() {
        return epochBucket;
    }

    public long count() {
        return count;
    }
}
