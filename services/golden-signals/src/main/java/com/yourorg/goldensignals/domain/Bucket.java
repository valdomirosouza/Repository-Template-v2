package com.yourorg.goldensignals.domain;

import java.util.List;

/**
 * An immutable, persisted aggregate for one {@code (path, window, epoch_bucket)}
 * (ADR-0068 §4). Carries the count/error/saturation tallies and the raw latency
 * samples needed by {@link PercentileCalculator} for rank interpolation at query
 * time (FR-07; ADR-0067 stores these in a sorted set).
 *
 * @param path             request path (raw / unencoded; encoding is a key concern only)
 * @param window           the window (1m or 5m)
 * @param epochBucket      epoch-second bucket start (ADR-0068 §3)
 * @param count            total events (traffic)
 * @param errors           events with {@code status >= 400}
 * @param saturated        events with {@code bytesSent >= threshold}
 * @param latencySamples   raw latency samples (immutable copy)
 */
public record Bucket(
        String path,
        Window window,
        long epochBucket,
        long count,
        long errors,
        long saturated,
        List<Double> latencySamples) {

    public Bucket {
        latencySamples = latencySamples == null ? List.of() : List.copyOf(latencySamples);
    }

    /** Latency samples (immutable; returned via {@code List.copyOf} so callers cannot mutate state). */
    @Override
    public List<Double> latencySamples() {
        return List.copyOf(latencySamples);
    }

    /** {@code errors / count}, or {@code 0.0} when {@code count == 0} (E1, no div-by-zero). */
    public double errorRate() {
        return count == 0 ? 0.0 : (double) errors / count;
    }

    /** {@code saturated / count * 100}, or {@code 0.0} when {@code count == 0} (ADR-0068 §1). */
    public double saturationPct() {
        return count == 0 ? 0.0 : (double) saturated / count * 100.0;
    }
}
