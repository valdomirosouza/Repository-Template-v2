package com.yourorg.goldensignals.observability;

import static org.assertj.core.api.Assertions.assertThat;

import com.yourorg.goldensignals.domain.SignalEvent;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Instant;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Issue #230 — the four Golden Signals (traffic, errors, latency, saturation) are
 * exported as Prometheus meters, with request path deliberately absent from the
 * label set (bounded cardinality).
 */
class SignalMetricsTest {

    private static SignalEvent event(final double ms, final boolean error, final boolean saturated) {
        return new SignalEvent("/api/orders", ms, error, saturated, Instant.ofEpochSecond(100));
    }

    @Test
    @DisplayName("recordEvent increments traffic and records a latency sample")
    void trafficAndLatency() {
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final SignalMetrics metrics = new SignalMetrics(registry);

        metrics.recordEvent(event(120.0, false, false));
        metrics.recordEvent(event(80.0, false, false));

        assertThat(registry.get("gs_signal_events_total").counter().count()).isEqualTo(2.0);
        assertThat(registry.get("gs_signal_latency_ms").summary().count()).isEqualTo(2L);
        assertThat(registry.get("gs_signal_latency_ms").summary().totalAmount()).isEqualTo(200.0);
    }

    @Test
    @DisplayName("error and saturation counters increment only for flagged events")
    void errorsAndSaturation() {
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final SignalMetrics metrics = new SignalMetrics(registry);

        metrics.recordEvent(event(10.0, true, false));   // error only
        metrics.recordEvent(event(10.0, false, true));   // saturated only
        metrics.recordEvent(event(10.0, true, true));    // both
        metrics.recordEvent(event(10.0, false, false));  // neither

        assertThat(registry.get("gs_signal_errors_total").counter().count()).isEqualTo(2.0);
        assertThat(registry.get("gs_signal_saturated_total").counter().count()).isEqualTo(2.0);
        assertThat(registry.get("gs_signal_events_total").counter().count()).isEqualTo(4.0);
    }

    @Test
    @DisplayName("recordFlush increments the aggregation flush counter")
    void flushes() {
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final SignalMetrics metrics = new SignalMetrics(registry);

        metrics.recordFlush();
        metrics.recordFlush();

        assertThat(registry.get("gs_aggregation_flushes_total").counter().count()).isEqualTo(2.0);
    }

    @Test
    @DisplayName("path is not a meter tag (bounded cardinality)")
    void noPathLabel() {
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final SignalMetrics metrics = new SignalMetrics(registry);

        metrics.recordEvent(event(10.0, true, true));

        assertThat(registry.get("gs_signal_events_total").counter().getId().getTags()).isEmpty();
        assertThat(registry.get("gs_signal_errors_total").counter().getId().getTags()).isEmpty();
    }
}
