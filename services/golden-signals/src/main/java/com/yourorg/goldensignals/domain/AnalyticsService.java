package com.yourorg.goldensignals.domain;

import com.yourorg.goldensignals.api.dto.AnalyticsResponse;
import com.yourorg.goldensignals.api.dto.AnalyticsResponse.BucketRow;
import com.yourorg.goldensignals.api.dto.AnalyticsResponse.GovernanceBlock;
import com.yourorg.goldensignals.api.dto.AnalyticsResponse.Summary;
import com.yourorg.goldensignals.infra.MetricStore;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.springframework.stereotype.Service;

/**
 * Read-side analytics (FR-07/08/12/13). Queries the {@link MetricStore} for a
 * {@code (path, signal, window)} range, computes P50/P95/P99 per bucket via
 * {@link PercentileCalculator} (FR-07), builds the cross-bucket summary, and
 * decorates the response with the {@code _governance} block whose
 * {@code recommended_action_mode} flips to HITL on a threshold breach (FR-12/13).
 */
@Service
public class AnalyticsService {

    private final MetricStore store;
    private final GovernanceEvaluator governanceEvaluator;

    public AnalyticsService(final MetricStore store, final GovernanceEvaluator governanceEvaluator) {
        this.store = store;
        this.governanceEvaluator = governanceEvaluator;
    }

    /**
     * Build the analytics response for a query.
     *
     * @param path   required request path
     * @param signal the signal
     * @param window the window
     * @param from   inclusive lower bound (nullable = open)
     * @param to     exclusive upper bound (nullable = open)
     * @return the analytics response (FR-07/12/13)
     */
    public AnalyticsResponse analyze(
            final String path, final Signal signal, final Window window,
            final Instant from, final Instant to) {
        final List<Bucket> buckets = store.query(path, signal, window, from, to);

        final List<BucketRow> rows = new ArrayList<>(buckets.size());
        long totalCount = 0;
        long totalErrors = 0;
        Double maxP99 = null;
        for (final Bucket b : buckets) {
            final PercentileCalculator.Percentiles p =
                    PercentileCalculator.compute(b.latencySamples());
            rows.add(new BucketRow(
                    b.epochBucket(), p.p50(), p.p95(), p.p99(),
                    b.count(), b.errorRate(), b.saturationPct()));
            totalCount += b.count();
            totalErrors += b.errors();
            if (p.p99() != null && (maxP99 == null || p.p99() > maxP99)) {
                maxP99 = p.p99();
            }
        }
        final double aggregateErrorRate = totalCount == 0 ? 0.0 : (double) totalErrors / totalCount;
        final Summary summary = new Summary(totalCount, aggregateErrorRate, maxP99, rows.size());

        final GovernanceDecision decision =
                governanceEvaluator.evaluate(maxP99, aggregateErrorRate);
        return new AnalyticsResponse(rows, summary, GovernanceBlock.from(decision));
    }

    /** Tracked paths (FR-08). */
    public Set<String> trackedPaths() {
        return store.trackedPaths();
    }

    /** Whether the store reports healthy (FR-09). */
    public boolean storeConnected() {
        return store.ping();
    }
}
