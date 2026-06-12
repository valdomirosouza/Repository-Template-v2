package com.yourorg.goldensignals.domain;

import java.time.Instant;

/**
 * Epoch-aligned window bucketing (ADR-0068 §3, FR-05). Boundaries are
 * <strong>LEFT-closed / RIGHT-open</strong>: a sample at timestamp {@code t}
 * belongs to bucket {@code b} iff {@code bucketStart <= t < bucketStart + W}.
 * A sample at exactly {@code bucketStart + W} belongs to the <em>next</em>
 * bucket (E3). {@code bucketStart = floor(epochSeconds / W) * W}.
 *
 * <p>Pure / stateless — no Spring dependency, fully unit-testable.
 */
public final class WindowBucketer {

    private WindowBucketer() {
    }

    /**
     * Compute the epoch-second start of the bucket containing {@code timestamp}
     * for the given window.
     *
     * @param timestamp the event timestamp
     * @param window    the window (1m or 5m)
     * @return the bucket start as epoch seconds (the integer {@code epoch_bucket} key field)
     */
    public static long bucketStartEpochSeconds(final Instant timestamp, final Window window) {
        final long epochSeconds = Math.floorDiv(timestamp.getEpochSecond(), 1L); // truncate sub-second
        final long w = window.seconds();
        return Math.floorDiv(epochSeconds, w) * w;
    }

    /**
     * Bucket start as an {@link Instant} (convenience for response rendering).
     *
     * @param timestamp the event timestamp
     * @param window    the window
     * @return the bucket start instant
     */
    public static Instant bucketStart(final Instant timestamp, final Window window) {
        return Instant.ofEpochSecond(bucketStartEpochSeconds(timestamp, window));
    }
}
