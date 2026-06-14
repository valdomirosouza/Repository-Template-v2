package com.yourorg.goldensignals.queue;

import static org.assertj.core.api.Assertions.assertThat;

import com.yourorg.goldensignals.domain.Bucket;
import com.yourorg.goldensignals.domain.SignalEvent;
import com.yourorg.goldensignals.domain.Window;
import com.yourorg.goldensignals.infra.InMemoryMetricStore;
import com.yourorg.goldensignals.observability.SignalMetrics;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * FR-04/05 / E6/E7 — queue + worker aggregation, driven deterministically via the
 * package-private {@code accumulate}/{@code flushAll} (no async timing in the unit test).
 */
class AggregationPipelineTest {

    private static SignalEvent event(final long epochSecond, final double ms, final boolean error) {
        return new SignalEvent("/p", ms, error, false, Instant.ofEpochSecond(epochSecond));
    }

    @Test
    @DisplayName("one event updates both its 1m and 5m bucket exactly once (E7)")
    void fansIntoBothWindows() {
        final InMemoryMetricStore store = new InMemoryMetricStore();
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final AggregationWorker worker = new AggregationWorker(
                new IngestQueue(10, registry), store, new SignalMetrics(registry));

        worker.accumulate(event(97, 10.0, false)); // 1m bucket 60, 5m bucket 0
        worker.flushAll();

        final List<Bucket> oneMin = store.query("/p", null, Window.ONE_MINUTE, null, null);
        final List<Bucket> fiveMin = store.query("/p", null, Window.FIVE_MINUTE, null, null);
        assertThat(oneMin).hasSize(1);
        assertThat(oneMin.get(0).epochBucket()).isEqualTo(60L);
        assertThat(oneMin.get(0).count()).isEqualTo(1);
        assertThat(fiveMin).hasSize(1);
        assertThat(fiveMin.get(0).epochBucket()).isEqualTo(0L);
        assertThat(fiveMin.get(0).count()).isEqualTo(1);
    }

    @Test
    @DisplayName("events in distinct 1m buckets stay separated (E3 boundary)")
    void separatesBuckets() {
        final InMemoryMetricStore store = new InMemoryMetricStore();
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final AggregationWorker worker = new AggregationWorker(
                new IngestQueue(10, registry), store, new SignalMetrics(registry));

        worker.accumulate(event(119, 5.0, false));  // bucket [60,120)
        worker.accumulate(event(120, 7.0, true));   // bucket [120,180) — RIGHT-open boundary
        worker.flushAll();

        final List<Bucket> buckets = store.query("/p", null, Window.ONE_MINUTE, null, null);
        assertThat(buckets).hasSize(2);
        assertThat(buckets.get(0).epochBucket()).isEqualTo(60L);
        assertThat(buckets.get(1).epochBucket()).isEqualTo(120L);
        assertThat(buckets.get(1).errors()).isEqualTo(1);
    }

    @Test
    @DisplayName("queue full ⇒ offer returns false and drop counter increments (E6)")
    void queueFullDrops() {
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final IngestQueue queue = new IngestQueue(1, registry);
        assertThat(queue.offer(event(0, 1.0, false))).isTrue();
        assertThat(registry.get("gs_queue_depth").gauge().value()).isEqualTo(1.0); // saturation gauge
        assertThat(queue.offer(event(0, 1.0, false))).isFalse(); // full
        assertThat(registry.get("gs_queue_dropped_total").counter().count()).isEqualTo(1.0);
    }
}
