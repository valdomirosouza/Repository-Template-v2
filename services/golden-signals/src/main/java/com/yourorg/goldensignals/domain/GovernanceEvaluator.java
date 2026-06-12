package com.yourorg.goldensignals.domain;

/**
 * Applies the FR-13 governance thresholds to a computed analytics result and
 * produces the {@code _governance} block (FR-12). When the observed P99 latency
 * exceeds {@code HITL_P99_LATENCY_MS}, or the error rate exceeds
 * {@code HITL_ERROR_RATE}, the recommended action mode flips from HOTL to HITL
 * and {@code humanApprovalRequired} is set (FR-13, AC-08).
 *
 * <p>Comparison is strict ({@code >}): exactly-at-threshold is <em>not</em> a flip;
 * one tick over flips (E5).
 */
public final class GovernanceEvaluator {

    private static final String DATA_CLASSIFICATION = "telemetry-L2";
    private static final String RETENTION_POLICY = "1m:2h,5m:24h";
    private static final String AUDIT_TRAIL = "/audit";
    private static final String MODE_HOTL = "HOTL";
    private static final String MODE_HITL = "HITL";

    private final double p99LatencyThresholdMs;
    private final double errorRateThreshold;

    public GovernanceEvaluator(final double p99LatencyThresholdMs, final double errorRateThreshold) {
        this.p99LatencyThresholdMs = p99LatencyThresholdMs;
        this.errorRateThreshold = errorRateThreshold;
    }

    /**
     * Evaluate the governance block for an observed P99 latency and error rate.
     *
     * @param observedP99Ms the highest P99 latency across the returned buckets,
     *                      or {@code null}/NaN when no latency samples exist
     * @param observedErrorRate the aggregate error rate across the returned buckets
     * @return the governance decision (FR-12/13)
     */
    public GovernanceDecision evaluate(final Double observedP99Ms, final double observedErrorRate) {
        final boolean latencyBreach = observedP99Ms != null
                && !observedP99Ms.isNaN()
                && observedP99Ms > p99LatencyThresholdMs;
        final boolean errorBreach = observedErrorRate > errorRateThreshold;
        final boolean flip = latencyBreach || errorBreach;
        return new GovernanceDecision(
                DATA_CLASSIFICATION,
                true,
                RETENTION_POLICY,
                AUDIT_TRAIL,
                flip ? MODE_HITL : MODE_HOTL,
                flip);
    }
}
