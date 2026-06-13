"use client";

import { useReportWebVitals } from "next/web-vitals";

import { reportWebVital } from "@/lib/observability/web-vitals";

/**
 * Subscribes to Core Web Vitals (LCP, CLS, INP, FCP, TTFB) and forwards each to the
 * configured beacon endpoint via {@link reportWebVital}. Renders nothing; mount once in the
 * root layout. #229 W3-5.
 */
export function WebVitals(): null {
  useReportWebVitals((metric) => {
    reportWebVital(metric);
  });
  return null;
}
