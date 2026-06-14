package com.yourorg.goldensignals.domain;

import com.yourorg.goldensignals.api.dto.IngestionResponse;
import com.yourorg.goldensignals.api.dto.LogEntryDto;
import com.yourorg.goldensignals.observability.SignalMetrics;
import com.yourorg.goldensignals.queue.IngestQueue;
import java.time.Instant;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * Orchestrates the ingestion path for a validated batch (FR-01–04):
 * mask client IP (FR-02) ⇒ extract signals (FR-03) ⇒ enqueue (FR-04). A
 * queue-full drop is counted toward {@code rejected} but the batch still returns
 * 202 (ADR-0069 §2). The IP is masked <em>before</em> any persist or log
 * (CLAUDE.md §3.1) — only the masked value ever leaves this method.
 */
@Service
public class IngestionService {

    private static final Logger LOG = LoggerFactory.getLogger(IngestionService.class);

    private final IpMaskingService ipMasking;
    private final GoldenSignalExtractor extractor;
    private final IngestQueue queue;
    private final SignalMetrics metrics;

    public IngestionService(
            final IpMaskingService ipMasking,
            final GoldenSignalExtractor extractor,
            final IngestQueue queue,
            final SignalMetrics metrics) {
        this.ipMasking = ipMasking;
        this.extractor = extractor;
        this.queue = queue;
        this.metrics = metrics;
    }

    /**
     * Process a pre-validated batch.
     *
     * @param batch the validated log entries
     * @return the accepted/rejected tally (FR-01)
     */
    public IngestionResponse ingest(final List<LogEntryDto> batch) {
        int accepted = 0;
        int rejected = 0;
        for (final LogEntryDto dto : batch) {
            final String maskedIp = ipMasking.mask(dto.clientIp());
            final LogEntry entry = new LogEntry(
                    dto.path(),
                    dto.statusCode(),
                    dto.responseTimeMs(),
                    dto.bytesSent(),
                    maskedIp,
                    Instant.ofEpochMilli(dto.timestamp()));
            // Structured log carries ONLY the masked IP (FR-02, §3.1).
            LOG.debug("ingest path={} status={} maskedIp={}", entry.path(), entry.statusCode(), maskedIp);
            final SignalEvent event = extractor.extract(entry);
            if (queue.offer(event)) {
                accepted++;
                metrics.recordEvent(event); // Golden Signals: traffic/latency/errors/saturation
            } else {
                rejected++; // queue full ⇒ dropped (ADR-0069 §2), still 202
            }
        }
        return new IngestionResponse(accepted, rejected);
    }
}
