# ADR-0065 — Test-Integrity Invariants

**Status:** Accepted
**Date:** 2026-06-09
**Authors:** Valdomiro Souza

---

## Context

The repository's testing gate is **coverage ≥ 80%** (`CLAUDE.md §3.5`, ADR-0022,
`harness/code-check.yml`). Coverage is a **quantity** metric: it is fully satisfiable while the
test suite's _integrity_ silently degrades. You can add weak tests to lift the percentage, delete
strong assertions, skip a flaky test "for now", or implement first and backfill thin tests — and
coverage sees none of it. For an agentic system that writes its own tests, these are exactly the
shortcuts an optimiser takes to make a gate go green.

The lightweight Spec-Driven workflow (`spec-driven-insights-for-repository-template-v2.md` §2.4)
out-disciplines our heavyweight pipeline on precisely this axis, with hard, machine-checkable test
rules. Those rules are integrity metrics coverage cannot see, they are cheap to enforce, and they
align with our evidence-and-gates culture (ADR-0061's control-binding gate is the sibling
mechanism). Source: Spec-Driven v2.0.0 by Felipe Rodrigues (Tech Lead's Club, CC-BY-4.0).

## Decision

Adopt four **test-integrity invariants** and enforce the machine-checkable ones as a CI governance
gate (`scripts/governance/check_test_integrity.py`), wired into `harness/code-check.yml` and listed
in `CLAUDE.md §7.1`. The invariants are documented for authors/reviewers in
`skills/engineering/testing-strategy.md`.

1. **RED before GREEN.** Tests are written and **confirmed failing** before the implementation that
   satisfies them. A test that passes on first write is too weak — it does not constrain the code.
   _(Review-time invariant; evidenced in the PR/commit narrative, not statically enforceable.)_
2. **Test co-location.** Tests live in the **same task/commit** as the code they cover. "Tested in
   another task / later PR" is **test deferral**, an explicit anti-pattern.
   _(Review-time invariant; reinforced by the per-task "one reviewable artifact" rule, ADR-0060.)_
3. **No silent test-count decrease.** The per-marker and total test count is compared against a
   committed baseline (`tests/.test-integrity-baseline.json`). A **decrease fails the PR** unless
   justified with a `TEST-WAIVER: <reason>` line in the PR body or diff. This catches silent
   deletions that coverage cannot. _(Machine-enforced.)_
4. **No assertion weakening / silent skip.** A newly added `skip` / `xfail` / `skipif` /
   `pytest.skip(...)` without a rationale (`reason=`, a string argument, or an inline `# why`
   comment) **fails the PR**. Assertions must not be weakened or disabled to make a gate pass —
   **tests are the spec; the implementation conforms to the tests**, never the reverse.
   _(Machine-enforced for added skips; assertion-weakening is also a review-time invariant.)_

### Enforcement boundary (what the gate is and is not)

- **It enforces integrity discipline**, not test _correctness_. Like ADR-0061's control-binding
  gate, it checks "did the change preserve the suite's integrity?", not "are these good tests?".
  A weak-but-present test passes the gate; review still owns quality.
- **It is offline and deterministic.** The checker counts tests by `ast` static analysis (no pytest
  collection, no network, no clock) and diffs against the committed baseline — mirroring
  `check_control_bindings.py`. The baseline is regenerated with `--update-baseline` and committed
  whenever the intended count changes.
- **It complements coverage, does not replace it.** Coverage (≥ 80%) remains the quantity gate;
  this is the integrity gate beside it.

## Consequences

### Positive

- Silent test deletion and "skip-to-green" become **failing, auditable** events instead of
  invisible erosion.
- The integrity invariants pair with the existing CI-gate machinery (ADR-0061) at near-zero cost.
- Reinforces "tests are the spec" — the implementation conforms to tests, not vice-versa.

### Negative / Trade-offs

- A committed baseline must be kept current; legitimate deletions need a `TEST-WAIVER:` line or a
  baseline refresh (friction, intended — it forces an explicit, reviewed decision).
- Static `ast` counting is approximate at the margins (e.g. dynamically generated tests). It is a
  tripwire for _silent decreases_, not a substitute for pytest collection — documented as such.
- RED-first and co-location are review-time, not machine-enforced; they rely on reviewer diligence.

## Alternatives Considered

1. **Rely on coverage alone.** Rejected: coverage is a quantity metric blind to integrity erosion —
   the gap this ADR closes.
2. **Run pytest collection to count tests.** Rejected for the gate: it requires the full test
   dependency tree and is slower/flakier; static `ast` counting is offline, deterministic, and
   sufficient to detect silent decreases.
3. **Enforce RED-first mechanically (e.g. require a failing CI run before the fix).** Rejected for
   v1: it needs commit-sequence forensics that are brittle in a squash-merge flow; kept as a
   documented review invariant. Revisit if erosion shows up despite review.

## References

- `spec-driven-insights-for-repository-template-v2.md` §2.4 (source insight; CC-BY-4.0,
  Felipe Rodrigues / Tech Lead's Club)
- `scripts/governance/check_test_integrity.py` + `tests/unit/governance/test_check_test_integrity.py`
- ADR-0022 (Testing Strategy) · ADR-0061 (control-binding CI gate — sibling) · ADR-0060 (task atomicity)
- ADR-0050 (adversarial abuse testing) · `CLAUDE.md` §3.5 (quality), §7.1 (CI-enforced gates)
- `harness/code-check.yml` · `skills/engineering/testing-strategy.md`
