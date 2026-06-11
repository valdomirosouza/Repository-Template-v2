package com.yourorg.goldensignals.infra;

import static org.assertj.core.api.Assertions.assertThat;

import com.yourorg.goldensignals.domain.Signal;
import com.yourorg.goldensignals.domain.Window;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** ADR-0068 §4 — key grammar + path URL-encoding (key-injection defence, §3.2). */
class MetricKeysTest {

    @Test
    @DisplayName("aggregate key follows gs:{signal}:{path}:{window}:{epoch}")
    void aggregateKeyGrammar() {
        final String key = MetricKeys.aggregateKey(Signal.LATENCY, "/api/orders", Window.ONE_MINUTE, 60L);
        assertThat(key).isEqualTo("gs:latency:%2Fapi%2Forders:1m:60");
    }

    @Test
    @DisplayName("samples key appends :samples")
    void samplesKeyGrammar() {
        final String key = MetricKeys.samplesKey(Signal.LATENCY, "/p", Window.FIVE_MINUTE, 300L);
        assertThat(key).endsWith(":samples").startsWith("gs:latency:");
    }

    @Test
    @DisplayName("injection chars in path are URL-encoded — cannot forge another key (§3.2)")
    void keyInjectionDefence() {
        // A malicious path tries to inject a forged 'gs:traffic:victim' key with separators.
        final String evil = "gs:traffic:victim:1m:0";
        final String key = MetricKeys.aggregateKey(Signal.LATENCY, evil, Window.ONE_MINUTE, 60L);
        // The encoded path must not reintroduce raw ':' separators that could collide.
        final String encodedSegment = key.substring("gs:latency:".length(), key.indexOf(":1m:"));
        assertThat(encodedSegment).doesNotContain(":");
        assertThat(MetricKeys.decodePath(encodedSegment)).isEqualTo(evil);
    }

    @Test
    @DisplayName("whitespace/newline paths are encoded then round-trip exactly")
    void whitespaceRoundTrip() {
        final String path = "/a b\n/c";
        final String enc = MetricKeys.encodePath(path);
        assertThat(enc).doesNotContain(" ").doesNotContain("\n");
        assertThat(MetricKeys.decodePath(enc)).isEqualTo(path);
    }
}
