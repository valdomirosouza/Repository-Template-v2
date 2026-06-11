package com.yourorg.goldensignals.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * FR-07 / AC-06 — rank-based linear-interpolation percentiles against a known
 * dataset. For {@code 1..10} (n=10), with fractional rank {@code h=(n-1)*p/100}:
 * <ul>
 *   <li>P50: h=4.5 ⇒ 5 + 0.5*(6-5) = 5.5</li>
 *   <li>P95: h=8.55 ⇒ 9 + 0.55*(10-9) = 9.55</li>
 *   <li>P99: h=8.91 ⇒ 9 + 0.91*(10-9) = 9.91</li>
 * </ul>
 */
class PercentileCalculatorTest {

    private static final List<Double> ONE_TO_TEN = List.of(
            1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0);

    @Test
    @DisplayName("known dataset 1..10 yields the documented interpolated percentiles (AC-06)")
    void knownDataset() {
        final PercentileCalculator.Percentiles p = PercentileCalculator.compute(ONE_TO_TEN);
        assertThat(p.p50()).isCloseTo(5.5, within(1e-9));
        assertThat(p.p95()).isCloseTo(9.55, within(1e-9));
        assertThat(p.p99()).isCloseTo(9.91, within(1e-9));
    }

    @Test
    @DisplayName("unsorted input is sorted before interpolation")
    void unsortedInputSorted() {
        final List<Double> shuffled = List.of(10.0, 1.0, 7.0, 3.0, 5.0, 2.0, 9.0, 4.0, 8.0, 6.0);
        assertThat(PercentileCalculator.percentile(shuffled, 50.0)).isCloseTo(5.5, within(1e-9));
    }

    @Test
    @DisplayName("single sample ⇒ P50=P95=P99=that value, no div-by-zero (E2)")
    void singleSample() {
        final PercentileCalculator.Percentiles p = PercentileCalculator.compute(List.of(42.0));
        assertThat(p.p50()).isEqualTo(42.0);
        assertThat(p.p95()).isEqualTo(42.0);
        assertThat(p.p99()).isEqualTo(42.0);
    }

    @Test
    @DisplayName("empty sample set ⇒ all percentiles null (E1)")
    void emptySamples() {
        final PercentileCalculator.Percentiles p = PercentileCalculator.compute(List.of());
        assertThat(p.p50()).isNull();
        assertThat(p.p95()).isNull();
        assertThat(p.p99()).isNull();
        assertThat(PercentileCalculator.percentile(List.of(), 95.0)).isNull();
    }

    @Test
    @DisplayName("P0 and P100 return the min and max")
    void boundaries() {
        assertThat(PercentileCalculator.percentile(ONE_TO_TEN, 0.0)).isEqualTo(1.0);
        assertThat(PercentileCalculator.percentile(ONE_TO_TEN, 100.0)).isEqualTo(10.0);
    }

    @Test
    @DisplayName("percentile outside [0,100] is rejected")
    void outOfRangeRejected() {
        assertThatThrownBy(() -> PercentileCalculator.percentile(ONE_TO_TEN, 101.0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> PercentileCalculator.percentile(ONE_TO_TEN, -1.0))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
