package com.yourorg.goldensignals.domain;

/**
 * The governance block attached to an analytics response (FR-12/13).
 *
 * @param dataClassification    fixed telemetry classification (ADR-0012)
 * @param piiSanitized          true — IPs masked before persist (FR-02)
 * @param retentionPolicy       human-readable retention (ADR-0067)
 * @param auditTrail            path to the audit endpoint (FR-14)
 * @param recommendedActionMode {@code "HOTL"} or {@code "HITL"} (FR-13 flip)
 * @param humanApprovalRequired true when a threshold breach forces HITL (FR-13)
 */
public record GovernanceDecision(
        String dataClassification,
        boolean piiSanitized,
        String retentionPolicy,
        String auditTrail,
        String recommendedActionMode,
        boolean humanApprovalRequired) {
}
