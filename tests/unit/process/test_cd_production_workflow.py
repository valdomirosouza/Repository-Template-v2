"""Governance tests for the production deploy workflow (cd-production.yml).

ADR-0056 — these lock the Wave D release-hardening properties so they cannot
silently regress:
  - P0-5: deploy cannot start unless cab-check (and error budget + artifact) pass.
  - P1-5: DORA lead time is resolved from the version tag, not silently zeroed.
  - P1-6: artifact integrity (cosign signature, SBOM, provenance) is verified, and
          the deploy uses an immutable digest; change evidence captures provenance.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _ROOT / ".github" / "workflows" / "cd-production.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text())


@pytest.fixture(scope="module")
def jobs(workflow) -> dict:
    return workflow["jobs"]


def _needs(job: dict) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def _job_text(job: dict) -> str:
    """Flatten all run-step scripts of a job into one string."""
    return "\n".join(step.get("run", "") for step in job.get("steps", []))


def test_workflow_exists(workflow):
    assert "jobs" in workflow


# ── P0-5: CAB blocks deployment ────────────────────────────────────────────────


def test_deploy_canary_needs_cab_check(jobs):
    assert "cab-check" in _needs(jobs["deploy-canary"])


def test_deploy_canary_needs_error_budget(jobs):
    assert "check-error-budget" in _needs(jobs["deploy-canary"])


def test_cab_check_validates_change_type_and_rfc(jobs):
    text = _job_text(jobs["cab-check"])
    assert "normal-change" in text
    assert "emergency-change" in text
    assert "RFC" in text


def test_emergency_change_requires_emergency_evidence(jobs):
    text = _job_text(jobs["cab-check"])
    assert "Emergency-Approval" in text
    assert "Incident" in text


# ── P1-6: artifact integrity ────────────────────────────────────────────────────


def test_verify_artifact_job_exists(jobs):
    assert "verify-artifact" in jobs


def test_deploy_canary_needs_verify_artifact(jobs):
    assert "verify-artifact" in _needs(jobs["deploy-canary"])


def test_verify_artifact_runs_cosign_verify(jobs):
    text = _job_text(jobs["verify-artifact"])
    assert "cosign verify" in text  # signature verification (blocking)
    assert "verify-attestation" in text  # SBOM + provenance attestations
    assert "cyclonedx" in text  # SBOM attestation type
    assert "slsaprovenance" in text  # provenance attestation type


def test_verify_artifact_resolves_immutable_digest(jobs):
    text = _job_text(jobs["verify-artifact"])
    assert "crane digest" in text


def test_verify_artifact_outputs_digest_and_sbom_hash(jobs):
    outputs = jobs["verify-artifact"].get("outputs", {})
    assert "image_digest" in outputs
    assert "sbom_hash" in outputs


def test_deploy_uses_digest_not_only_tag(jobs):
    text = _job_text(jobs["deploy-canary"])
    assert "verify-artifact.outputs.image_digest" in text


# ── P1-5: DORA lead time ─────────────────────────────────────────────────────────


def test_emit_dora_does_not_read_pull_request_number(jobs):
    # The workflow is workflow_dispatch-only; pull_request context is unavailable.
    text = _job_text(jobs["emit-dora-event"])
    assert "github.event.pull_request.number" not in text


def test_emit_dora_resolves_lead_time_from_version_tag(jobs):
    text = _job_text(jobs["emit-dora-event"])
    assert "refs/tags" in text or "version_tag" in text


def test_emit_dora_records_workflow_dispatch_source_not_zero(jobs):
    text = _job_text(jobs["emit-dora-event"])
    assert "workflow_dispatch" in text
    # Lead time is only emitted when known — not defaulted to a misleading zero.
    assert "known" in text


# ── Change evidence completeness ─────────────────────────────────────────────────


def test_change_evidence_captures_full_provenance(jobs):
    text = _job_text(jobs["record-change-evidence"])
    for field in (
        "version:",
        "commit_sha:",
        "image_digest:",
        "sbom_hash:",
        "timestamp:",
        "deployer:",
    ):
        assert field in text, f"change evidence missing '{field}'"


def test_change_evidence_uses_verified_digest(jobs):
    text = _job_text(jobs["record-change-evidence"])
    assert "verify-artifact.outputs.image_digest" in text
    assert "verify-artifact.outputs.sbom_hash" in text
