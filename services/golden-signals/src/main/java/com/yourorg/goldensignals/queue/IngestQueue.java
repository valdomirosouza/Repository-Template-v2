package com.yourorg.goldensignals.queue;

import com.yourorg.goldensignals.domain.SignalEvent;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Bounded in-JVM work queue decoupling ingestion from processing (ADR-0069 §1/§2).
 * Wraps an {@link ArrayBlockingQueue} of fixed capacity {@code INGEST_QUEUE_CAPACITY}
 * (default 10000). The producer uses non-blocking {@link #offer(SignalEvent)}: on a
 * full queue the event is dropped, {@code gs_queue_dropped_total} is incremented,
 * and ingestion still returns 202 with the drop counted as {@code rejected}
 * (backpressure, never blocking the API thread — ADR-0069 §2, threat model D).
 */
@Component
public class IngestQueue {

    private final BlockingQueue<SignalEvent> queue;
    private final Counter droppedCounter;

    public IngestQueue(
            @Value("${gs.ingest-queue-capacity:10000}") final int capacity,
            final MeterRegistry meterRegistry) {
        this.queue = new ArrayBlockingQueue<>(capacity);
        this.droppedCounter = Counter.builder("gs_queue_dropped_total")
                .description("Signal events dropped because the ingest queue was full")
                .register(meterRegistry);
        // Golden Signal — saturation: live queue depth (bounded by capacity, no user-input label).
        Gauge.builder("gs_queue_depth", queue, java.util.concurrent.BlockingQueue::size)
                .description("Current ingest-queue depth (pipeline saturation indicator)")
                .register(meterRegistry);
    }

    /**
     * Non-blocking enqueue (ADR-0069 §2).
     *
     * @param event the extracted signal event
     * @return true if queued; false if the queue was full (event dropped, counter incremented)
     */
    public boolean offer(final SignalEvent event) {
        final boolean queued = queue.offer(event);
        if (!queued) {
            droppedCounter.increment();
        }
        return queued;
    }

    /**
     * Blocking dequeue for the worker (ADR-0069 §3); cheap on a virtual thread.
     *
     * @param timeout poll timeout
     * @param unit    timeout unit
     * @return the next event, or {@code null} if the timeout elapsed
     * @throws InterruptedException if the waiting thread is interrupted
     */
    public SignalEvent poll(final long timeout, final TimeUnit unit) throws InterruptedException {
        return queue.poll(timeout, unit);
    }

    /** Current depth (test/observability support). */
    public int size() {
        return queue.size();
    }
}
