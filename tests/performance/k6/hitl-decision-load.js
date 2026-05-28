/**
 * k6 Load Test — HITL Decision Endpoint
 *
 * CUJ:  CUJ-002 (HITL Decision Flow)
 * SLO:  HITL gateway availability ≥ 99.9%; decision submission p95 ≤ 300 ms
 * ADR:  ADR-0011 (HITL/HOTL Model)
 *
 * This test simulates concurrent HITL operators processing the approval queue.
 * It seeds pending requests via the submission endpoint, then submits decisions
 * concurrently to measure decision endpoint latency under realistic operator load.
 *
 * Scenarios:
 *   operator_baseline — 5 concurrent operators; sustained 3 min (normal ops)
 *   operator_surge    — 15 concurrent operators; 1 min surge (backlog drain scenario)
 *
 * Run:
 *   k6 run tests/performance/k6/hitl-decision-load.js
 *   BASE_URL=http://localhost:8000 k6 run tests/performance/k6/hitl-decision-load.js
 *
 * Prerequisites:
 *   The api-gateway must be running with a HITL-triggering configuration.
 *   In testing, seed pending requests with the setup() function or via a fixture.
 */

import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

// ── Custom metrics ─────────────────────────────────────────────────────────────

const decisionErrors = new Rate("decision_error_rate");
const decisionLatency = new Trend("decision_latency_ms", true);
const statusLatency = new Trend("hitl_status_latency_ms", true);
const decisionsTotal = new Counter("decisions_submitted_total");
const approvals = new Counter("approvals_total");
const rejections = new Counter("rejections_total");

// ── Configuration ─────────────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Synthetic operator identifiers — no real PII
const OPERATORS = [
  "operator-00000000-0000-0000-0000-000000000001",
  "operator-00000000-0000-0000-0000-000000000002",
  "operator-00000000-0000-0000-0000-000000000003",
  "operator-00000000-0000-0000-0000-000000000004",
  "operator-00000000-0000-0000-0000-000000000005",
];

const RATIONALES = {
  APPROVED: [
    "Action verified against approved scope. Risk within accepted bounds.",
    "Proposed change is consistent with the current sprint objective and safe to execute.",
    "Risk score within LOW_RISK threshold. File path is within the approved write zone.",
  ],
  REJECTED: [
    "Action exceeds approved risk threshold for this action_type in this environment.",
    "Proposed write operation targets a path outside the approved sandbox directory.",
    "Rejection per policy: external API calls require supervisor approval in production.",
  ],
};

export const options = {
  scenarios: {
    operator_baseline: {
      executor: "constant-vus",
      vus: 5,
      duration: "3m",
      tags: { scenario: "baseline" },
    },
    operator_surge: {
      executor: "ramping-vus",
      startVUs: 5,
      stages: [
        { duration: "30s", target: 15 },
        { duration: "1m", target: 15 },
        { duration: "30s", target: 5 },
      ],
      startTime: "3m30s",
      tags: { scenario: "surge" },
    },
  },

  thresholds: {
    // Decision submission: p95 ≤ 300 ms (CUJ-002 SLO target)
    decision_latency_ms: ["p(95)<300", "p(99)<500"],

    // HITL status poll: fast read — p95 ≤ 100 ms
    hitl_status_latency_ms: ["p(95)<100"],

    // Error rate: < 0.5% (excludes expected 404s for already-decided requests)
    decision_error_rate: ["rate<0.005"],

    // Overall HTTP failure rate
    http_req_failed: ["rate<0.005"],
  },
};

// ── Helper: submit a request to create a pending HITL entry ──────────────────

function seedPendingRequest() {
  const res = http.post(
    `${BASE_URL}/v1/requests`,
    JSON.stringify({
      request_text: "evaluate risk profile for quarterly batch operation",
      priority: "high",
    }),
    { headers: { "Content-Type": "application/json" } },
  );

  if (res.status !== 202) return null;
  try {
    return JSON.parse(res.body).request_id;
  } catch {
    return null;
  }
}

// ── Helper: pick a random operator and rationale ──────────────────────────────

function randomOperator() {
  return OPERATORS[Math.floor(Math.random() * OPERATORS.length)];
}

function randomRationale(decision) {
  const pool = RATIONALES[decision];
  return pool[Math.floor(Math.random() * pool.length)];
}

// ── Main VU loop ──────────────────────────────────────────────────────────────

export default function () {
  const operatorId = randomOperator();
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  group("check_queue_depth", () => {
    const start = Date.now();
    const statusRes = http.get(`${BASE_URL}/v1/hitl/status`, {
      headers: { Accept: "application/json" },
      tags: { endpoint: "hitl_status" },
    });
    statusLatency.add(Date.now() - start);

    check(statusRes, {
      "hitl_status: 200 OK": (r) => r.status === 200,
      "hitl_status: operational": (r) => {
        try {
          return JSON.parse(r.body).status === "operational";
        } catch {
          return false;
        }
      },
    });
  });

  // Seed a pending HITL request to decide (simulates the agent creating the request)
  const requestId = seedPendingRequest();

  if (!requestId) {
    sleep(1);
    return;
  }

  // Operators typically spend a few seconds reviewing before deciding
  sleep(0.5 + Math.random() * 2.5);

  group("submit_decision", () => {
    // 80% approval rate (mirrors expected autonomous resolution target complement)
    const decision = Math.random() < 0.8 ? "APPROVED" : "REJECTED";
    const rationale = randomRationale(decision);

    const start = Date.now();
    const decisionRes = http.post(
      `${BASE_URL}/v1/hitl/requests/${requestId}/decision`,
      JSON.stringify({ decision, rationale, approver_id: operatorId }),
      { headers, tags: { endpoint: "hitl_decision", decision } },
    );
    decisionLatency.add(Date.now() - start);
    decisionsTotal.add(1);

    const ok = check(decisionRes, {
      "decision: 200 or 404": (r) => r.status === 200 || r.status === 404,
      "decision: 200 has decision field": (r) => {
        if (r.status !== 200) return true; // 404 is acceptable (already decided)
        try {
          const body = JSON.parse(r.body);
          return ["APPROVED", "REJECTED"].includes(body.decision);
        } catch {
          return false;
        }
      },
    });

    // Only count as error if it's not a 200 or expected 404
    decisionErrors.add(
      decisionRes.status !== 200 && decisionRes.status !== 404,
    );

    if (decisionRes.status === 200) {
      if (decision === "APPROVED") approvals.add(1);
      else rejections.add(1);
    }
  });

  // Think time: 1–5 s (operator review pacing between decisions)
  sleep(1 + Math.random() * 4);
}

// ── Summary handler ───────────────────────────────────────────────────────────

export function handleSummary(data) {
  const dm = data.metrics["decision_latency_ms"];
  const p95 = dm?.values?.["p(95)"] ?? "N/A";
  const p99 = dm?.values?.["p(99)"] ?? "N/A";
  const total = data.metrics["decisions_submitted_total"]?.values?.count ?? 0;
  const approved = data.metrics["approvals_total"]?.values?.count ?? 0;
  const rejected = data.metrics["rejections_total"]?.values?.count ?? 0;

  console.log("\n── HITL Decision Load Test Summary ────────────────────");
  console.log(`  Total decisions:    ${total}`);
  console.log(
    `  Approvals:          ${approved}  (${total ? ((approved / total) * 100).toFixed(1) : 0}%)`,
  );
  console.log(
    `  Rejections:         ${rejected}  (${total ? ((rejected / total) * 100).toFixed(1) : 0}%)`,
  );
  console.log(
    `  Decision p95:       ${typeof p95 === "number" ? p95.toFixed(1) : p95} ms  (SLO: < 300 ms)`,
  );
  console.log(
    `  Decision p99:       ${typeof p99 === "number" ? p99.toFixed(1) : p99} ms  (SLO: < 500 ms)`,
  );
  console.log("────────────────────────────────────────────────────────\n");

  return { stdout: JSON.stringify(data, null, 2) };
}
