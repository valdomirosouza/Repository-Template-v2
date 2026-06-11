package com.yourorg.goldensignals.api.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

/**
 * Inbound HAProxy log entry (FR-01). Bean Validation enforces the boundary
 * contract (CLAUDE.md §3.2): any per-entry constraint violation routes the
 * batch to a 422 (FR-01, AC-02). {@code clientIp} is optional on the wire and
 * is masked before any persist/log (FR-02).
 *
 * @param path           request path (required, non-blank)
 * @param statusCode     HTTP status (100..599)
 * @param responseTimeMs latency in ms (>= 0)
 * @param bytesSent      response size in bytes (>= 0)
 * @param clientIp       raw client IP (optional; masked before use)
 * @param timestamp      epoch-millis event time (required, >= 0)
 */
public record LogEntryDto(
        @NotBlank(message = "path is required")
        String path,

        @NotNull(message = "status_code is required")
        @Min(value = 100, message = "status_code must be a valid HTTP status")
        Integer statusCode,

        @NotNull(message = "response_time_ms is required")
        @PositiveOrZero(message = "response_time_ms must be >= 0")
        Double responseTimeMs,

        @NotNull(message = "bytes_sent is required")
        @PositiveOrZero(message = "bytes_sent must be >= 0")
        Long bytesSent,

        String clientIp,

        @NotNull(message = "timestamp is required")
        @PositiveOrZero(message = "timestamp must be epoch millis >= 0")
        Long timestamp) {
}
