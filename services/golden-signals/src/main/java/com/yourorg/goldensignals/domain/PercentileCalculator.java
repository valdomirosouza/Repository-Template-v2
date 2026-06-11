package com.yourorg.goldensignals.domain;

import java.util.Arrays;
import java.util.List;

/**
 * Rank-based percentile calculator using linear interpolation between closest
 * ranks (FR-07, AC-06). No external statistics library.
 *
 * <p>Method (the documented "linear interpolation between closest ranks",
 * equivalent to NumPy's default / Excel {@code PERCENTILE.INC}):
 * for sorted samples {@code x[0..n-1]} and percentile {@code p in [0,100]},
 * the fractional rank is {@code h = (n - 1) * p / 100}; the value is
 * {@code x[floor(h)] + (h - floor(h)) * (x[floor(h)+1] - x[floor(h)])}.
 *
 * <p>Edge cases: a single sample yields {@code P50=P95=P99=}that sample (E2);
 * an empty sample set yields {@code null} for every percentile (E1).
 */
public final class PercentileCalculator {

    private PercentileCalculator() {
    }

    /**
     * Compute one percentile over a sample list.
     *
     * @param samples    the latency samples (need not be pre-sorted)
     * @param percentile the percentile in {@code [0, 100]} (e.g. 95.0 for P95)
     * @return the interpolated percentile value, or {@code null} if {@code samples} is empty
     * @throws IllegalArgumentException if {@code percentile} is outside {@code [0,100]}
     */
    public static Double percentile(final List<Double> samples, final double percentile) {
        if (percentile < 0.0 || percentile > 100.0) {
            throw new IllegalArgumentException("percentile must be in [0,100], got " + percentile);
        }
        if (samples == null || samples.isEmpty()) {
            return null;
        }
        final double[] sorted = samples.stream().mapToDouble(Double::doubleValue).sorted().toArray();
        return percentileSorted(sorted, percentile);
    }

    /**
     * Compute one percentile over an already-sorted primitive array.
     *
     * @param sorted     ascending-sorted samples
     * @param percentile the percentile in {@code [0,100]}
     * @return the interpolated value, or {@code null} if {@code sorted} is empty
     */
    public static Double percentileSorted(final double[] sorted, final double percentile) {
        if (sorted == null || sorted.length == 0) {
            return null;
        }
        final int n = sorted.length;
        if (n == 1) {
            return sorted[0];
        }
        final double h = (n - 1) * (percentile / 100.0);
        final int lower = (int) Math.floor(h);
        final int upper = (int) Math.ceil(h);
        if (lower == upper) {
            return sorted[lower];
        }
        final double weight = h - lower;
        return sorted[lower] + weight * (sorted[upper] - sorted[lower]);
    }

    /**
     * Convenience: P50/P95/P99 in one pass over a sorted copy of {@code samples}.
     *
     * @param samples the samples (need not be pre-sorted)
     * @return a {@link Percentiles} holder; all fields {@code null} if empty
     */
    public static Percentiles compute(final List<Double> samples) {
        if (samples == null || samples.isEmpty()) {
            return new Percentiles(null, null, null);
        }
        final double[] sorted = samples.stream().mapToDouble(Double::doubleValue).sorted().toArray();
        return new Percentiles(
                percentileSorted(sorted, 50.0),
                percentileSorted(sorted, 95.0),
                percentileSorted(sorted, 99.0));
    }

    /** P50/P95/P99 holder; values are {@code null} for an empty sample set (E1). */
    public record Percentiles(Double p50, Double p95, Double p99) {
        @Override
        public String toString() {
            return "Percentiles" + Arrays.asList(p50, p95, p99);
        }
    }
}
