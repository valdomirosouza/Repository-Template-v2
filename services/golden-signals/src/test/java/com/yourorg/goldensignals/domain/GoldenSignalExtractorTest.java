package com.yourorg.goldensignals.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** FR-03 / ADR-0068 §1 — golden-signal extraction rules. */
class GoldenSignalExtractorTest {

    private final GoldenSignalExtractor extractor =
            new GoldenSignalExtractor(new SaturationConfig(SaturationConfig.DEFAULT_THRESHOLD_BYTES));

    private static LogEntry entry(final int status, final double ms, final long bytes) {
        return new LogEntry("/api/orders", status, ms, bytes, "203.0.113.0", Instant.EPOCH);
    }

    @Test
    @DisplayName("latency sample carried through; non-error, non-saturated baseline")
    void baseline() {
        final SignalEvent e = extractor.extract(entry(200, 12.5, 1000));
        assertThat(e.responseTimeMs()).isEqualTo(12.5);
        assertThat(e.error()).isFalse();
        assertThat(e.saturated()).isFalse();
        assertThat(e.path()).isEqualTo("/api/orders");
    }

    @Test
    @DisplayName("error flagged iff status >= 400 (boundary 399/400)")
    void errorBoundary() {
        assertThat(extractor.extract(entry(399, 1, 0)).error()).isFalse();
        assertThat(extractor.extract(entry(400, 1, 0)).error()).isTrue();
        assertThat(extractor.extract(entry(503, 1, 0)).error()).isTrue();
    }

    @Test
    @DisplayName("saturated iff bytes >= threshold (>= at boundary counts, ADR-0068 §2)")
    void saturationBoundary() {
        final long t = SaturationConfig.DEFAULT_THRESHOLD_BYTES;
        assertThat(extractor.extract(entry(200, 1, t - 1)).saturated()).isFalse();
        assertThat(extractor.extract(entry(200, 1, t)).saturated()).isTrue();      // boundary == saturated
        assertThat(extractor.extract(entry(200, 1, t + 1)).saturated()).isTrue();
    }

    @Test
    @DisplayName("per-path override takes precedence over the global default (ADR-0068 §2)")
    void perPathOverride() {
        final GoldenSignalExtractor withOverride = new GoldenSignalExtractor(
                new SaturationConfig(1_048_576L, Map.of("/api/orders", 100L)));
        // 500 bytes is below the global 1 MiB default but above the per-path 100-byte override.
        final SignalEvent e = withOverride.extract(entry(200, 1, 500));
        assertThat(e.saturated()).isTrue();
    }
}
