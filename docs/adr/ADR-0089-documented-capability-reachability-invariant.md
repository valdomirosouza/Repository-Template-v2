# ADR-0089 — Documented-Capability Reachability as a Tested Invariant

**Status:** Accepted
**Date:** 2026-09-12
**Authors:** Tech Lead (drafted with Claude Code, Wave 12 · W12-T1, issue #354)
**Spec:** specs/system/architecture.md §Runtime wiring invariants
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0014](ADR-0014-multi-agent-harness-strategy.md), [ADR-0044](ADR-0044-otel-agent-span-hierarchy.md), [ADR-0075](ADR-0075-resilience-fallback-policy.md), [ADR-0086](ADR-0086-hitl-approval-resumption-and-expiry-sweep.md)

---

## Context

The Seven-Axis Review of 2026-09-12 found that the running service did not reach five
capabilities the documentation describes as present:

| Documented in                               | Capability                                    | Runtime reality before this ADR                                                                         |
| ------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| CLAUDE.md §0.1, ADR-0014 and six other ADRs | `harness_mode: solo \| simplified \| full`    | `HarnessCoordinator` was never constructed in `src/`                                                    |
| ADR-0044, ADR-0045, ADR-0075                | `Otel → Resilient → Timeout` LLM client stack | consumer built a bare `AnthropicLLMClient()` per retry; timeout/retry/breaker settings were dead config |
| ADR-0006, `docs/sre/`                       | HTTP Golden Signals (`http_requests_total`)   | `record_request()` had no caller; `src/api/rest/middleware/` was empty                                  |
| ADR-0011, `specs/ai/hitl-hotl.md`           | approved HITL actions execute                 | `agent.action.approved` had no consumer; requests were stored `completed` while suspended               |
| `config.py`                                 | `max_concurrent_agents` semaphore             | created in lifespan, read by the capacity gate, acquired by nothing                                     |

Coverage did not notice because `src/api/rest/main.py` was excluded "covered by integration
tests", and integration coverage was gated at zero. For an agentic repository this is the
highest-severity drift class (CLAUDE.md §3.6): agents ground on CLAUDE.md and the ADRs first and
will confidently describe behaviour the system does not have.

## Decision

We will treat **documented-capability reachability** as a tested invariant:

1. Every capability that CLAUDE.md §0.1, an accepted ADR, or an approved spec presents as part of
   the runtime **must be constructed by the application lifespan** (`src/api/rest/main.py`) under
   the configuration the documentation names — or the documentation must carry an explicit
   "not wired" label naming the tracking issue.
2. `tests/integration/test_lifespan_wiring.py` boots the real lifespan offline (every
   infrastructure client forced to its documented in-memory fallback, a stub LLM behind the real
   wrapper stack) and asserts each capability. **A new documented runtime capability must add an
   assertion to this test in the same PR.**
3. `src/api/rest/main.py` is no longer excluded from coverage.
4. The AI-agents extension is gated at runtime by `settings.ai_agents_enabled`, not only in
   configuration validation: when false, no consumer, sweeper or LLM client is created and the
   service logs that submitted requests will not be processed.

## Consequences

### Positive

- The wiring test fails when a documented component is unplugged, which is exactly what a
  reviewer cannot see in a diff.
- The in-memory fallbacks now carry subscriptions, so the whole pipeline (submit → consume →
  orchestrate → HITL → approve → execute) runs in-process; the e2e tier exercises real wiring.
- `main.py` coverage exposes future dead branches instead of hiding them.

### Negative / Trade-offs

- The wiring test couples to `app.state` attribute names; renaming a component means touching
  the test (intended — the test _is_ the contract).
- The lifespan grew by ~60 lines. A later refactor may extract an `AgentsRuntime` builder;
  the invariant, not the file shape, is the decision.

### Neutral

- "Not wired" labels are legitimate outcomes — ADR-0014's harness is now wired (W12-T6), but a
  future capability may be documented ahead of implementation as long as it says so.

## Alternatives Considered

- **Keep excluding `main.py` and rely on staging smoke tests.** Rejected: the drift survived
  eleven releases that way.
- **A static "every class in `src/agents` is imported by `main.py`" check.** Rejected: import
  is not construction; the harness _was_ importable.
- **Do nothing and fix the five findings.** Rejected: the failure class recurs with the next
  ADR; the invariant is the durable fix.

## Compliance & Risk

- **Controls affected:** none weakened. The HITL path is strengthened (ADR-0086).
- **Data classification impact:** none.
- **Autonomy impact:** none — `harness_mode` and `ai_agents_enabled` are existing settings, no
  feature flag is introduced or changed (ADR-0015).
- **Review/expiry:** permanent.

---

## Related

- Seven-Axis Review §3 Implementation drift detection (2026-09-12)
- Template v2 Improvement Plan, Wave 12
