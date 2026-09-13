/**
 * k6 Smoke Test — post-deploy baseline (staging gate)
 *
 * Referenced by harness/staging-check.yml (`performance-baseline`) and cd-staging.yml.
 * A short, low-VU run that proves the deployed service answers within SLO before the
 * heavier scenarios in request-api-load.js / hitl-decision-load.js are considered.
 *
 * CUJ:  CUJ-001 (User Request Processing)
 * SLO:  availability ≥ 99.9%; submit latency p99 ≤ MAX_P99_MS (default 500 ms);
 *       health p99 ≤ 200 ms
 * ADR:  ADR-0003 (Async API Strategy), ADR-0042 (probe strategy)
 *
 * Run:
 *   k6 run --env BASE_URL=https://staging.example.com --env MAX_P99_MS=500 tests/performance/k6/smoke.js
 *
 * Added by W11-T4 (issue #349): the staging-check spec pointed at this file before it existed.
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const MAX_P99_MS = Number(__ENV.MAX_P99_MS || 500);

const submitErrors = new Rate("submit_error_rate");
const submitLatency = new Trend("submit_latency_ms", true);
const healthLatency = new Trend("health_latency_ms", true);

export const options = {
  scenarios: {
    smoke: {
      executor: "constant-vus",
      vus: 5,
      duration: "1m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.001"], // availability ≥ 99.9%
    submit_latency_ms: [`p(99)<${MAX_P99_MS}`],
    health_latency_ms: ["p(99)<200"],
    submit_error_rate: ["rate<0.001"],
  },
};

export default function () {
  const health = http.get(`${BASE_URL}/ready`);
  healthLatency.add(health.timings.duration);
  check(health, { "ready 200": (r) => r.status === 200 });

  const payload = JSON.stringify({
    request_text:
      "SMOKE: summarise the on-call runbook index (synthetic, no PII)",
    priority: "low",
  });
  const res = http.post(`${BASE_URL}/v1/requests`, payload, {
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": `smoke-${__VU}-${__ITER}`,
    },
  });
  submitLatency.add(res.timings.duration);
  const ok = check(res, {
    "submit 202": (r) => r.status === 202,
    "has request_id": (r) => r.status === 202 && !!r.json("request_id"),
  });
  submitErrors.add(!ok);

  sleep(1);
}
