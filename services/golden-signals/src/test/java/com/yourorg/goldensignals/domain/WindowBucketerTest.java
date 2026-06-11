package com.yourorg.goldensignals.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** FR-05 / ADR-0068 §3 — epoch-aligned, LEFT-closed/RIGHT-open window bucketing. */
class WindowBucketerTest {

    @Test
    @DisplayName("1m bucket aligns to the minute floor")
    void oneMinuteAlignment() {
        // 1970-01-01T00:01:37Z = epoch 97s ⇒ 1m bucket start = 60s.
        final Instant t = Instant.ofEpochSecond(97);
        assertThat(WindowBucketer.bucketStartEpochSeconds(t, Window.ONE_MINUTE)).isEqualTo(60L);
    }

    @Test
    @DisplayName("5m bucket aligns to the 300s floor")
    void fiveMinuteAlignment() {
        // epoch 901s ⇒ 5m bucket start = 900s.
        final Instant t = Instant.ofEpochSecond(901);
        assertThat(WindowBucketer.bucketStartEpochSeconds(t, Window.FIVE_MINUTE)).isEqualTo(900L);
    }

    @Test
    @DisplayName("LEFT-closed: a sample at exactly the bucket start is IN that bucket")
    void leftClosed() {
        final Instant start = Instant.ofEpochSecond(60);
        assertThat(WindowBucketer.bucketStartEpochSeconds(start, Window.ONE_MINUTE)).isEqualTo(60L);
    }

    @Test
    @DisplayName("RIGHT-open: a sample at exactly bucket end belongs to the NEXT bucket (E3)")
    void rightOpen() {
        // 120s is the end of the [60,120) bucket ⇒ belongs to the [120,180) bucket.
        final Instant end = Instant.ofEpochSecond(120);
        assertThat(WindowBucketer.bucketStartEpochSeconds(end, Window.ONE_MINUTE)).isEqualTo(120L);
    }

    @Test
    @DisplayName("sub-second timestamps truncate to the containing second's bucket")
    void subSecond() {
        final Instant t = Instant.ofEpochSecond(119).plusMillis(999);
        assertThat(WindowBucketer.bucketStartEpochSeconds(t, Window.ONE_MINUTE)).isEqualTo(60L);
    }

    @Test
    @DisplayName("bucketStart returns the matching Instant")
    void bucketStartInstant() {
        final Instant t = Instant.ofEpochSecond(97);
        assertThat(WindowBucketer.bucketStart(t, Window.ONE_MINUTE))
                .isEqualTo(Instant.ofEpochSecond(60));
    }
}
