package com.yourorg.goldensignals.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** FR-05 — accumulator tallies count/errors/saturation and collects samples. */
class AggregateTest {

    private static SignalEvent event(final double ms, final boolean error, final boolean sat) {
        return new SignalEvent("/p", ms, error, sat, Instant.EPOCH);
    }

    @Test
    @DisplayName("folds count/errors/saturation and snapshots into an immutable bucket")
    void foldsAndSnapshots() {
        final Aggregate agg = new Aggregate("/p", Window.ONE_MINUTE, 60L);
        agg.add(event(10.0, false, false));
        agg.add(event(20.0, true, false));
        agg.add(event(30.0, true, true));

        final Bucket b = agg.toBucket();
        assertThat(b.count()).isEqualTo(3);
        assertThat(b.errors()).isEqualTo(2);
        assertThat(b.saturated()).isEqualTo(1);
        assertThat(b.latencySamples()).containsExactly(10.0, 20.0, 30.0);
        assertThat(b.errorRate()).isCloseTo(2.0 / 3.0, org.assertj.core.api.Assertions.within(1e-9));
        assertThat(b.saturationPct()).isCloseTo(100.0 / 3.0, org.assertj.core.api.Assertions.within(1e-9));
    }

    @Test
    @DisplayName("empty bucket reports zero rates without div-by-zero (E1)")
    void emptyNoDivByZero() {
        final Bucket b = new Aggregate("/p", Window.ONE_MINUTE, 60L).toBucket();
        assertThat(b.count()).isZero();
        assertThat(b.errorRate()).isZero();
        assertThat(b.saturationPct()).isZero();
    }

    @Test
    @DisplayName("snapshot is an immutable defensive copy")
    void snapshotImmutable() {
        final Aggregate agg = new Aggregate("/p", Window.ONE_MINUTE, 60L);
        agg.add(event(5.0, false, false));
        final Bucket b = agg.toBucket();
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> b.latencySamples().add(9.0))
                .isInstanceOf(UnsupportedOperationException.class);
    }
}
