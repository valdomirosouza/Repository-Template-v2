/**
 * k6 Load Test — POST /v1/requests (Request Submission)
 *
 * CUJ:  CUJ-001 (User Request Processing), CUJ-003 (Agent Autonomous Resolution)
 * SLO:  availability ≥ 99.9%; submit latency p99 ≤ 500 ms; status poll p99 ≤ 200 ms
 * ADR:  ADR-0003 (Async API Strategy)
 *
 * Scenarios:
 *   ramp_up   — linearly increase load to 50 VUs over 2 min (baseline check)
 *   sustained — hold at 50 VUs for 5 min (SLO validation window)
 *   spike     — surge to 200 VUs for 1 min then drop (resilience / rate-limit check)
 *
 * Run:
 *   k6 run tests/performance/k6/request-api-load.js
 *   BASE_URL=http://localhost:8000 k6 run tests/performance/k6/request-api-load.js
 *
 * Output: summary printed to stdout; use --out influxdb=... for Grafana integration.
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// ── Custom metrics ─────────────────────────────────────────────────────────────

const submitErrors = new Rate("submit_error_rate");
const pollErrors = new Rate("poll_error_rate");
const submitLatency = new Trend("submit_latency_ms", true);
const pollLatency = new Trend("poll_latency_ms", true);

// ── Configuration ─────────────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  scenarios: {
    ramp_up: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "1m", target: 25 }, // ramp to 25 VUs
        { duration: "1m", target: 50 }, // ramp to 50 VUs
      ],
      gracefulRampDown: "30s",
      tags: { scenario: "ramp_up" },
    },

    sustained: {
      executor: "constant-vus",
      vus: 50,
      duration: "5m",
      startTime: "2m30s", // starts after ramp_up finishes
      tags: { scenario: "sustained" },
    },

    spike: {
      executor: "ramping-vus",
      startVUs: 50,
      stages: [
        { duration: "30s", target: 200 }, // fast spike
        { duration: "1m", target: 200 }, // hold spike
        { duration: "30s", target: 50 }, // recover
      ],
      startTime: "8m", // starts after sustained finishes
      tags: { scenario: "spike" },
    },
  },

  // SLO-aligned thresholds — failure here is a CI gate failure
  thresholds: {
    // Submission latency: p99 ≤ 500 ms (CUJ-001 SLO)
    submit_latency_ms: ["p(99)<500", "p(95)<300"],

    // Status poll latency: p99 ≤ 200 ms (fast cache read)
    poll_latency_ms: ["p(99)<200", "p(95)<100"],

    // Error rates: < 0.5% for both submit and poll
    submit_error_rate: ["rate<0.005"],
    poll_error_rate: ["rate<0.005"],

    // Overall HTTP failure rate
    http_req_failed: ["rate<0.005"],

    // Rate-limited responses (429) are expected during the spike scenario —
    // they do not count toward error_rate but are tracked separately.
    "http_req_duration{expected_response:true}": ["p(99)<500"],
  },
};

// ── Request payloads (synthetic, no PII) ─────────────────────────────────────

const PAYLOADS = [
  { request_text: "summarise the Q4 operational report", priority: "normal" },
  {
    request_text: "classify the incoming support ticket category",
    priority: "high",
  },
  {
    request_text: "extract key entities from the meeting transcript",
    priority: "low",
  },
  {
    request_text: "analyse sentiment in the customer feedback batch",
    priority: "normal",
  },
  {
    request_text: "generate a one-paragraph executive summary",
    priority: "normal",
  },
];

// ── Main VU loop ──────────────────────────────────────────────────────────────

export default function () {
  const payload = PAYLOADS[Math.floor(Math.random() * PAYLOADS.length)];

  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  // ── Submit request ──────────────────────────────────────────────────────────

  const submitStart = Date.now();
  const submitRes = http.post(
    `${BASE_URL}/v1/requests`,
    JSON.stringify(payload),
    { headers, tags: { endpoint: "submit" } },
  );
  submitLatency.add(Date.now() - submitStart);

  const submitOk = check(submitRes, {
    "submit: status is 202": (r) => r.status === 202,
    "submit: body has request_id": (r) => {
      try {
        return JSON.parse(r.body).request_id !== undefined;
      } catch {
        return false;
      }
    },
    "submit: status field is queued": (r) => {
      try {
        return JSON.parse(r.body).status === "queued";
      } catch {
        return false;
      }
    },
  });

  // Track 429 (rate limited) separately — expected during spike scenario
  if (submitRes.status === 429) {
    // Rate-limited: honour the Retry-After header and back off
    const retryAfter = parseInt(submitRes.headers["Retry-After"] || "5", 10);
    sleep(retryAfter);
    return;
  }

  submitErrors.add(!submitOk);

  if (!submitOk || submitRes.status !== 202) {
    sleep(1);
    return;
  }

  // ── Poll status ─────────────────────────────────────────────────────────────

  let requestId;
  try {
    requestId = JSON.parse(submitRes.body).request_id;
  } catch {
    return;
  }

  sleep(0.1); // brief pause before first poll

  const pollStart = Date.now();
  const pollRes = http.get(`${BASE_URL}/v1/requests/${requestId}`, {
    headers: { Accept: "application/json" },
    tags: { endpoint: "poll" },
  });
  pollLatency.add(Date.now() - pollStart);

  const pollOk = check(pollRes, {
    "poll: status is 200": (r) => r.status === 200,
    "poll: request_id matches": (r) => {
      try {
        return JSON.parse(r.body).request_id === requestId;
      } catch {
        return false;
      }
    },
    "poll: status is a known value": (r) => {
      try {
        const s = JSON.parse(r.body).status;
        return [
          "queued",
          "processing",
          "completed",
          "failed",
          "pending_hitl",
        ].includes(s);
      } catch {
        return false;
      }
    },
  });

  pollErrors.add(!pollOk);

  // Think time: 0.5–2 s (simulates realistic operator pacing)
  sleep(0.5 + Math.random() * 1.5);
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

export function handleSummary(data) {
  // Print a concise SLO pass/fail table to stdout
  const thresholds = data.metrics;
  console.log("\n── SLO Threshold Summary ──────────────────────────────");

  const checks = [
    ["submit_latency_ms p(99)", "< 500 ms"],
    ["submit_latency_ms p(95)", "< 300 ms"],
    ["poll_latency_ms p(99)", "< 200 ms"],
    ["submit_error_rate", "< 0.5%"],
    ["poll_error_rate", "< 0.5%"],
  ];

  checks.forEach(([metric, threshold]) => {
    const passed =
      !data.metrics[metric]?.thresholds?.length ||
      Object.values(data.metrics[metric]?.thresholds || {}).every(Boolean);
    const icon = passed ? "✓" : "✗";
    console.log(`  ${icon}  ${metric.padEnd(35)} ${threshold}`);
  });

  console.log("───────────────────────────────────────────────────────\n");

  return {
    stdout: JSON.stringify(data, null, 2),
  };
}
