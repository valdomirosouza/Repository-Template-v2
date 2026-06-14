package com.yourorg.goldensignals.observability;

import com.yourorg.goldensignals.domain.SignalEvent;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.DistributionSummary;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

/**
 * Exports the four Golden Signals — traffic, errors, latency, saturation — as
 * Prometheus meters on {@code /actuator/prometheus} (NFR-03; issue #230, tracking
 * #229 W2-11c). Before this, the service computed the signals only on-query in
 * {@code AnalyticsService} and emitted just {@code gs_queue_dropped_total}, leaving
 * operators blind to the ingestion critical path in real time.
 *
 * <p><strong>Cardinality.</strong> Request {@code path} is deliberately <em>not</em>
 * a meter tag: it is user-influenced and effectively unbounded, so tagging by it
 * would explode series count (skills/observability/otel-instrumentation.md — "keep
 * cardinality bounded; never use user IDs or free-text as labels"). Per-path
 * breakdown stays in the on-query analytics API, not in the metric label set. The
 * API key is never used as a label.
 */
@Component
public class SignalMetrics {

    private final Counter eventsTotal;
    private final Counter errorsTotal;
    private final Counter saturatedTotal;
    private final Counter flushesTotal;
    private final DistributionSummary latencyMs;

    public SignalMetrics(final MeterRegistry registry) {
        this.eventsTotal = Counter.builder("gs_signal_events_total")
                .description("Golden Signal — traffic: signal events accepted into the pipeline")
                .register(registry);
        this.errorsTotal = Counter.builder("gs_signal_errors_total")
                .description("Golden Signal — errors: accepted events with status code >= 400")
                .register(registry);
        this.saturatedTotal = Counter.builder("gs_signal_saturated_total")
                .description("Golden Signal — saturation: accepted events over the bytes-sent threshold")
                .register(registry);
        this.flushesTotal = Counter.builder("gs_aggregation_flushes_total")
                .description("Aggregation flush cycles that persisted >= 1 open window to the store")
                .register(registry);
        this.latencyMs = DistributionSummary.builder("gs_signal_latency_ms")
                .description("Golden Signal — latency: per-request response time")
                .baseUnit("milliseconds")
                .publishPercentileHistogram()
                // SLO-aligned buckets; 1000ms is the default HITL P99 latency threshold (FR-13).
                .serviceLevelObjectives(50, 100, 250, 500, 1000, 2500)
                .register(registry);
    }

    /**
     * Record one accepted signal event across the traffic, errors, latency, and
     * saturation signals. Called once per event that is successfully queued
     * (drops are already visible via {@code gs_queue_dropped_total}).
     *
     * @param event the extracted signal event
     */
    public void recordEvent(final SignalEvent event) {
        eventsTotal.increment();
        latencyMs.record(event.responseTimeMs());
        if (event.error()) {
            errorsTotal.increment();
        }
        if (event.saturated()) {
            saturatedTotal.increment();
        }
    }

    /** Record one aggregation flush cycle that persisted at least one open window. */
    public void recordFlush() {
        flushesTotal.increment();
    }
}
