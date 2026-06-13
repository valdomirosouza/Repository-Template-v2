package com.yourorg.goldensignals.queue;

import com.yourorg.goldensignals.domain.Aggregate;
import com.yourorg.goldensignals.domain.SignalEvent;
import com.yourorg.goldensignals.domain.Window;
import com.yourorg.goldensignals.domain.WindowBucketer;
import com.yourorg.goldensignals.infra.MetricStore;
import com.yourorg.goldensignals.observability.SignalMetrics;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Single virtual-thread worker draining {@link IngestQueue} into 1m/5m aggregates
 * and flushing them to the {@link MetricStore} (FR-05, ADR-0069 §3). Each event
 * fans into <em>both</em> its 1m and 5m bucket exactly once (E7, no cross-window
 * leakage). Aggregates flush on a periodic timer and on shutdown so partial
 * windows are not lost.
 *
 * <p>Uses {@link Executors#newVirtualThreadPerTaskExecutor()} — the Loom
 * equivalent of the asyncio worker NFR-02 originally specified (ADR-0066/0069).
 */
@Component
public class AggregationWorker {

    private static final Logger LOG = LoggerFactory.getLogger(AggregationWorker.class);
    private static final long POLL_TIMEOUT_MS = 200L;
    private static final long FLUSH_INTERVAL_MS = 1_000L;

    private final IngestQueue queue;
    private final MetricStore store;
    private final SignalMetrics metrics;
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
    private volatile boolean running = true;

    /** Live accumulators keyed by (window, epochBucket, path). Owned by the worker thread. */
    private final Map<String, Aggregate> open = new HashMap<>();
    private volatile long lastFlush = System.currentTimeMillis();

    public AggregationWorker(
            final IngestQueue queue, final MetricStore store, final SignalMetrics metrics) {
        this.queue = queue;
        this.store = store;
        this.metrics = metrics;
    }

    /** Start the drain loop on a virtual thread (ADR-0069 §3). */
    @PostConstruct
    public void start() {
        executor.submit(this::runLoop);
    }

    private void runLoop() {
        while (running) {
            try {
                final SignalEvent event = queue.poll(POLL_TIMEOUT_MS, TimeUnit.MILLISECONDS);
                if (event != null) {
                    accumulate(event);
                }
                if (System.currentTimeMillis() - lastFlush >= FLUSH_INTERVAL_MS) {
                    flushAll();
                }
            } catch (final InterruptedException ex) {
                Thread.currentThread().interrupt();
                break;
            } catch (final RuntimeException ex) {
                LOG.warn("aggregation worker error: {}", ex.getMessage());
            }
        }
        flushAll();
    }

    /**
     * Fold one event into both window accumulators. Package-private so a unit
     * test can drive aggregation deterministically without the async loop.
     *
     * @param event the extracted signal event
     */
    void accumulate(final SignalEvent event) {
        for (final Window window : Window.values()) {
            final long bucket = WindowBucketer.bucketStartEpochSeconds(event.timestamp(), window);
            final String key = window.token() + ":" + bucket + ":" + event.path();
            open.computeIfAbsent(key, k -> new Aggregate(event.path(), window, bucket)).add(event);
        }
    }

    /**
     * Flush all open accumulators to the store and reset. Package-private for
     * deterministic test invocation.
     */
    synchronized void flushAll() {
        if (!open.isEmpty()) {
            for (final Aggregate agg : open.values()) {
                store.persist(agg.toBucket());
            }
            open.clear();
            metrics.recordFlush();
        }
        lastFlush = System.currentTimeMillis();
    }

    /** Stop the worker, flushing any open windows (ADR-0069 §3). */
    @PreDestroy
    public void stop() {
        running = false;
        executor.shutdown();
        try {
            if (!executor.awaitTermination(2, TimeUnit.SECONDS)) {
                executor.shutdownNow();
            }
        } catch (final InterruptedException ex) {
            Thread.currentThread().interrupt();
            executor.shutdownNow();
        }
        flushAll();
    }
}
