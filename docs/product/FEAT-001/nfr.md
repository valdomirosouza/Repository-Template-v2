# NFRs — FEAT-001 HTTP Golden Signals for the API Gateway

> **Phase:** 2 (Discovery) · **Issue:** #357 · **Spec:** SPEC-FEAT-001 · **Taxonomy:** `docs/product/nfr-taxonomy.md`
> **Approved by:** Security Lead — N/A: no new PII surface or security threat (Tech Lead confirmed, PR #365)

| NFR    | Category        | Requirement                                                                  | Verification                                         |
| ------ | --------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------- |
| NFR-01 | Performance     | Added latency per request ≤ 0.1 ms p99                                       | benchmarks nightly (`tests/performance/benchmarks/`) |
| NFR-02 | Privacy         | No request identifier, query string or header value enters a metric label    | unit test AC-02; ADR-0043 review                     |
| NFR-03 | Reliability     | Middleware failure must not change response semantics (exceptions propagate) | unit test AC-03                                      |
| NFR-04 | Observability   | Metrics exposed on `/metrics` without self-scrape recursion                  | unit test AC-05                                      |
| NFR-05 | Maintainability | Wiring asserted by the ADR-0089 lifespan test                                | `tests/integration/test_lifespan_wiring.py`          |
