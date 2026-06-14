/**
 * Core Web Vitals reporting (#229 W3-5). Pure, framework-agnostic so it is unit-testable
 * without the Next.js runtime. The `WebVitals` client component wires Next's
 * `useReportWebVitals` hook to {@link reportWebVital}.
 *
 * Metrics are sent to NEXT_PUBLIC_WEB_VITALS_ENDPOINT via `navigator.sendBeacon` (falling back
 * to `fetch` with keepalive). With no endpoint configured it is a no-op — never throws, never
 * blocks navigation, and never carries PII (only the metric name/value/id/rating).
 */

/** Minimal shape of a web-vitals metric (subset of next/web-vitals' NextWebVitalsMetric). */
export interface WebVitalMetric {
  readonly name: string;
  readonly value: number;
  readonly id: string;
  readonly rating?: string;
  readonly navigationType?: string;
}

/** Serialise only the non-PII metric fields. */
export function serializeWebVital(metric: WebVitalMetric): string {
  return JSON.stringify({
    name: metric.name,
    value: metric.value,
    id: metric.id,
    rating: metric.rating ?? null,
    navigationType: metric.navigationType ?? null,
  });
}

/**
 * Report one web-vital to the configured endpoint. No-op (returns false) when no endpoint is
 * set or no transport is available. Returns true when the metric was dispatched.
 */
export function reportWebVital(
  metric: WebVitalMetric,
  endpoint: string | undefined = process.env.NEXT_PUBLIC_WEB_VITALS_ENDPOINT,
): boolean {
  if (!endpoint) {
    return false;
  }
  const body = serializeWebVital(metric);
  const nav = typeof navigator !== "undefined" ? navigator : undefined;
  if (nav?.sendBeacon) {
    return nav.sendBeacon(endpoint, body);
  }
  if (typeof fetch !== "undefined") {
    void fetch(endpoint, {
      method: "POST",
      body,
      keepalive: true,
      headers: { "Content-Type": "application/json" },
    });
    return true;
  }
  return false;
}
