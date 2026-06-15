/**
 * Next.js instrumentation hook (auto-loaded at server startup). Registers OpenTelemetry
 * for the HITL operator UI so server-side spans export over OTLP, giving parity with the
 * backend services (event-worker W2-11a, domain-service W2-11b, golden-signals). #229 W3-5.
 *
 * Export target is controlled by the standard OTel env vars (e.g. OTEL_EXPORTER_OTLP_ENDPOINT);
 * with none set @vercel/otel is a safe no-op, so local dev needs no collector.
 */
import { registerOTel } from "@vercel/otel";

export function register(): void {
  registerOTel({
    serviceName: process.env.OTEL_SERVICE_NAME ?? "frontend-hitl-ui",
  });
}
