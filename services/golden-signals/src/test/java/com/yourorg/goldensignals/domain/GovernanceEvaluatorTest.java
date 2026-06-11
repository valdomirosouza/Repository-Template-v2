package com.yourorg.goldensignals.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** FR-13 / AC-08 / E5 — governance HITL flip with strict {@code >} thresholds. */
class GovernanceEvaluatorTest {

    private final GovernanceEvaluator evaluator = new GovernanceEvaluator(1000.0, 0.05);

    @Test
    @DisplayName("below thresholds ⇒ HOTL, no approval required")
    void belowThresholdsHotl() {
        final GovernanceDecision d = evaluator.evaluate(500.0, 0.01);
        assertThat(d.recommendedActionMode()).isEqualTo("HOTL");
        assertThat(d.humanApprovalRequired()).isFalse();
        assertThat(d.piiSanitized()).isTrue();
        assertThat(d.dataClassification()).isEqualTo("telemetry-L2");
    }

    @Test
    @DisplayName("exactly-at-threshold is NOT a flip (strict >, E5)")
    void exactlyAtThresholdNoFlip() {
        assertThat(evaluator.evaluate(1000.0, 0.05).recommendedActionMode()).isEqualTo("HOTL");
        assertThat(evaluator.evaluate(1000.0, 0.05).humanApprovalRequired()).isFalse();
    }

    @Test
    @DisplayName("P99 one tick over threshold ⇒ HITL + approval (E5)")
    void p99OverFlipsHitl() {
        final GovernanceDecision d = evaluator.evaluate(1000.001, 0.0);
        assertThat(d.recommendedActionMode()).isEqualTo("HITL");
        assertThat(d.humanApprovalRequired()).isTrue();
    }

    @Test
    @DisplayName("error rate over threshold ⇒ HITL + approval")
    void errorRateOverFlipsHitl() {
        final GovernanceDecision d = evaluator.evaluate(10.0, 0.06);
        assertThat(d.recommendedActionMode()).isEqualTo("HITL");
        assertThat(d.humanApprovalRequired()).isTrue();
    }

    @Test
    @DisplayName("null P99 (no latency samples) does not trip the latency flip")
    void nullP99NoFlip() {
        final GovernanceDecision d = evaluator.evaluate(null, 0.01);
        assertThat(d.recommendedActionMode()).isEqualTo("HOTL");
    }
}
