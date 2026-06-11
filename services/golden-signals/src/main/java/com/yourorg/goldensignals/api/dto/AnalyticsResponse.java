package com.yourorg.goldensignals.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.yourorg.goldensignals.domain.GovernanceDecision;
import java.util.List;

/**
 * {@code GET /analytics} response body (FR-07/12/13).
 *
 * @param buckets    per-bucket percentile rows (may be empty, E1)
 * @param summary    aggregate summary across the returned buckets
 * @param governance the {@code _governance} block (FR-12/13)
 */
public record AnalyticsResponse(
        List<BucketRow> buckets,
        Summary summary,
        @JsonProperty("_governance") GovernanceBlock governance) {

    public AnalyticsResponse {
        buckets = buckets == null ? List.of() : List.copyOf(buckets);
    }

    /** Bucket rows (immutable; returned via {@code List.copyOf} so callers cannot mutate state). */
    @Override
    public List<BucketRow> buckets() {
        return List.copyOf(buckets);
    }

    /**
     * One bucket row.
     *
     * @param bucketStart   epoch-second bucket start
     * @param p50           P50 latency (null if no samples, E1)
     * @param p95           P95 latency (null if no samples)
     * @param p99           P99 latency (null if no samples)
     * @param count         event count (traffic)
     * @param errorRate     errors / count
     * @param saturationPct saturated / count * 100
     */
    public record BucketRow(
            @JsonProperty("bucket_start") long bucketStart,
            Double p50,
            Double p95,
            Double p99,
            long count,
            @JsonProperty("error_rate") double errorRate,
            @JsonProperty("saturation_pct") double saturationPct) {
    }

    /**
     * Cross-bucket summary.
     *
     * @param totalCount   total events across buckets
     * @param errorRate    aggregate error rate
     * @param p99          highest P99 across buckets (null if none)
     * @param bucketCount  number of buckets returned
     */
    public record Summary(
            @JsonProperty("total_count") long totalCount,
            @JsonProperty("error_rate") double errorRate,
            Double p99,
            @JsonProperty("bucket_count") int bucketCount) {
    }

    /** Serialised form of {@link GovernanceDecision} with snake_case wire names (FR-12). */
    public record GovernanceBlock(
            @JsonProperty("data_classification") String dataClassification,
            @JsonProperty("pii_sanitized") boolean piiSanitized,
            @JsonProperty("retention_policy") String retentionPolicy,
            @JsonProperty("audit_trail") String auditTrail,
            @JsonProperty("recommended_action_mode") String recommendedActionMode,
            @JsonProperty("human_approval_required") boolean humanApprovalRequired) {

        /** Adapt a domain {@link GovernanceDecision} to the wire block. */
        public static GovernanceBlock from(final GovernanceDecision d) {
            return new GovernanceBlock(
                    d.dataClassification(),
                    d.piiSanitized(),
                    d.retentionPolicy(),
                    d.auditTrail(),
                    d.recommendedActionMode(),
                    d.humanApprovalRequired());
        }
    }
}
