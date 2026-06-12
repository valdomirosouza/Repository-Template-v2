package com.yourorg.goldensignals.api.dto;

/**
 * Ingestion response body (FR-01): {@code 202 {"accepted": <int>, "rejected": <int>}}.
 * {@code rejected} counts per-entry validation failures and queue-full drops
 * (ADR-0069 §2); the batch is still accepted (202) unless the JSON itself is
 * malformed (→ 422).
 *
 * @param accepted number of entries enqueued for processing
 * @param rejected number of entries dropped (validation or queue-full)
 */
public record IngestionResponse(int accepted, int rejected) {
}
