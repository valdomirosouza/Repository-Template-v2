package com.yourorg.goldensignals.infra;

import com.yourorg.goldensignals.domain.Bucket;
import com.yourorg.goldensignals.domain.Signal;
import com.yourorg.goldensignals.domain.Window;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/**
 * Thread-safe in-memory {@link MetricStore} (ADR-0067) — the default profile
 * implementation, used for unit/integration tests and local dev so the core
 * logic stays Redis-free (NFR-05). Keyed by the ADR-0068 grammar via
 * {@link MetricKeys}; the {@code path} is URL-encoded inside the key exactly as
 * the Redis backend does, so the two are key-compatible.
 *
 * <p>Concurrency: a {@link ConcurrentHashMap} per aggregate key, each value an
 * append-only {@link MutableBucket} guarded by its own monitor. The single
 * virtual-thread worker is the only writer (ADR-0069), but the store is made
 * fully thread-safe so it is safe under the integration-test SpringBoot context.
 */
@Component
@Profile("!redis")
public class InMemoryMetricStore implements MetricStore {

    private final ConcurrentMap<String, MutableBucket> store = new ConcurrentHashMap<>();
    private final Set<String> paths = ConcurrentHashMap.newKeySet();

    @Override
    public void persist(final Bucket bucket) {
        // Track samples under the LATENCY-keyed aggregate; the same bucket carries
        // count/errors/saturated for all four signals (one row per (path,window,epoch)).
        final String key = MetricKeys.aggregateKey(
                Signal.LATENCY, bucket.path(), bucket.window(), bucket.epochBucket());
        store.compute(key, (k, existing) -> {
            final MutableBucket target = existing != null
                    ? existing
                    : new MutableBucket(bucket.path(), bucket.window(), bucket.epochBucket());
            target.merge(bucket);
            return target;
        });
        paths.add(MetricKeys.encodePath(bucket.path()));
    }

    @Override
    public List<Bucket> query(
            final String path, final Signal signal, final Window window,
            final Instant from, final Instant to) {
        final long fromEpoch = from == null ? Long.MIN_VALUE : from.getEpochSecond();
        final long toEpoch = to == null ? Long.MAX_VALUE : to.getEpochSecond();
        final List<Bucket> result = new ArrayList<>();
        for (final MutableBucket mb : store.values()) {
            if (!mb.path.equals(path) || mb.window != window) {
                continue;
            }
            // LEFT-closed / RIGHT-open on the query range by bucket start.
            if (mb.epochBucket >= fromEpoch && mb.epochBucket < toEpoch) {
                result.add(mb.snapshot());
            }
        }
        result.sort(Comparator.comparingLong(Bucket::epochBucket));
        return result;
    }

    @Override
    public Set<String> trackedPaths() {
        final Set<String> decoded = ConcurrentHashMap.newKeySet();
        for (final String enc : paths) {
            decoded.add(MetricKeys.decodePath(enc));
        }
        return decoded;
    }

    @Override
    public boolean ping() {
        return true;
    }

    /** Clear all state (test support). */
    public void clear() {
        store.clear();
        paths.clear();
    }

    /** Append-only mutable bucket guarded by its own monitor. */
    private static final class MutableBucket {
        private final String path;
        private final Window window;
        private final long epochBucket;
        private long count;
        private long errors;
        private long saturated;
        private final List<Double> samples = new ArrayList<>();

        MutableBucket(final String path, final Window window, final long epochBucket) {
            this.path = path;
            this.window = window;
            this.epochBucket = epochBucket;
        }

        synchronized void merge(final Bucket b) {
            this.count += b.count();
            this.errors += b.errors();
            this.saturated += b.saturated();
            this.samples.addAll(b.latencySamples());
        }

        synchronized Bucket snapshot() {
            return new Bucket(path, window, epochBucket, count, errors, saturated,
                    new ArrayList<>(samples));
        }
    }
}
