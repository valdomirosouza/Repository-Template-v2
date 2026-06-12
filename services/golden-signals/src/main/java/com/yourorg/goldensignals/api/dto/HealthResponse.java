package com.yourorg.goldensignals.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * {@code GET /analytics/health} response body (FR-09).
 *
 * @param status        {@code "ok"} or {@code "degraded"}
 * @param storeConnected whether {@link com.yourorg.goldensignals.infra.MetricStore#ping()} is true
 * @param trackedPaths  number of distinct tracked paths (FR-08)
 */
public record HealthResponse(
        String status,
        @JsonProperty("store_connected") boolean storeConnected,
        @JsonProperty("tracked_paths") int trackedPaths) {
}
