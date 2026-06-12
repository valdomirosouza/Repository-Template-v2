package com.yourorg.goldensignals.domain;

import java.time.Instant;

/**
 * A single normalised HAProxy log entry, post-validation and post-IP-masking
 * (FR-01/FR-02). Immutable (Java 21 record). {@code clientIp} here is already
 * masked (FR-02, ADR-0012) before it ever reaches the domain/persistence layer.
 *
 * @param path           request path (e.g. {@code /api/orders})
 * @param statusCode     HTTP status code (>=400 ⇒ error sample, ADR-0068 §1)
 * @param responseTimeMs response latency in milliseconds (latency sample)
 * @param bytesSent      response body size in bytes (saturation proxy, ADR-0068 §1)
 * @param clientIp       already-masked client IP (FR-02); never raw at this layer
 * @param timestamp      event timestamp used for window bucketing (ADR-0068 §3)
 */
public record LogEntry(
        String path,
        int statusCode,
        double responseTimeMs,
        long bytesSent,
        String clientIp,
        Instant timestamp) {
}
