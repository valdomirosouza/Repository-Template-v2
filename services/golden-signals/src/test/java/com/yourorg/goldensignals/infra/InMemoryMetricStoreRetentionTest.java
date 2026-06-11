package com.yourorg.goldensignals.infra;

import static org.assertj.core.api.Assertions.assertThat;

import com.yourorg.goldensignals.domain.Bucket;
import com.yourorg.goldensignals.domain.Signal;
import com.yourorg.goldensignals.domain.Window;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * FR-06 retention behaviour for {@link InMemoryMetricStore}. Retention is <b>data-relative</b>
 * (measured against the newest ingested bucket per window, not server wall-clock) so that
 * historical log replay is reproducible — a wall-clock implementation would silently evict the
 * spec's own AC fixtures (dated 2023). Found via the Node comparative re-implementation.
 */
class InMemoryMetricStoreRetentionTest {

    private static final String PATH = "/api/orders";
    private static final long RET_1M = 7200L; // default 1m horizon (2h), see application.yml

    private static Bucket bucket(final long epoch) {
        return new Bucket(PATH, Window.ONE_MINUTE, epoch, 1, 0, 0, List.of(12.0));
    }

    @Test
    void evictsBucketsOlderThanTheHorizonRelativeToTheNewestIngested() {
        final InMemoryMetricStore store = new InMemoryMetricStore(); // defaults 7200 / 86400
        final long base = 1_700_000_000L;
        store.persist(bucket(base));                  // becomes "old"
        store.persist(bucket(base + RET_1M + 1000));  // newest; horizon = newest - 7200 > base

        final List<Bucket> result =
                store.query(PATH, Signal.LATENCY, Window.ONE_MINUTE, null, null);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).epochBucket()).isEqualTo(base + RET_1M + 1000);
    }

    @Test
    void preservesClusteredHistoricalReplayDataWallClockWouldDestroy() {
        final InMemoryMetricStore store = new InMemoryMetricStore();
        final long base = 1_700_000_000L; // 2023-11 — >2y before any 2026 wall-clock
        store.persist(bucket(base));
        store.persist(bucket(base + 3000));
        store.persist(bucket(base + 6000)); // all within the 7200s horizon of each other

        final List<Bucket> result =
                store.query(PATH, Signal.LATENCY, Window.ONE_MINUTE, null, null);

        // Data-relative retention keeps all three; a wall-clock impl would have evicted everything.
        assertThat(result).hasSize(3);
    }

    @Test
    void retainsEverythingWithinHorizon() {
        final InMemoryMetricStore store = new InMemoryMetricStore();
        final long base = 1_700_000_000L;
        store.persist(bucket(base));
        store.persist(bucket(base + RET_1M)); // exactly at the horizon edge — kept (>= horizon)

        assertThat(store.query(PATH, Signal.LATENCY, Window.ONE_MINUTE, null, null)).hasSize(2);
    }
}
