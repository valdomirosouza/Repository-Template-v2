package com.yourorg.goldensignals.domain;

import java.time.Instant;

/**
 * The signal-extracted view of a {@link LogEntry}, queued for the worker
 * (FR-03/FR-04, ADR-0068 §1). One log entry yields exactly one
 * {@code SignalEvent}; the worker fans it into both the 1m and 5m buckets.
 *
 * @param path           request path
 * @param responseTimeMs latency sample value
 * @param error          true iff {@code statusCode >= 400} (ADR-0068 §1)
 * @param saturated      true iff {@code bytesSent >= threshold} (ADR-0068 §1/§2)
 * @param timestamp      event timestamp for bucketing
 */
public record SignalEvent(
        String path,
        double responseTimeMs,
        boolean error,
        boolean saturated,
        Instant timestamp) {
}
