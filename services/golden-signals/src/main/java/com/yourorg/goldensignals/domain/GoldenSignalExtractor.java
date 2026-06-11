package com.yourorg.goldensignals.domain;

/**
 * Extracts the four Golden Signals from a {@link LogEntry} into a
 * {@link SignalEvent} (FR-03, ADR-0068 §1):
 *
 * <ul>
 *   <li><b>Traffic</b> — every event contributes {@code count += 1} (implicit; the
 *       worker counts events).</li>
 *   <li><b>Latency</b> — {@code responseTimeMs} carried through as the sample.</li>
 *   <li><b>Error</b> — flagged iff {@code statusCode >= 400}.</li>
 *   <li><b>Saturation</b> — flagged iff {@code bytesSent >= thresholdFor(path)}
 *       (per-path with global default, {@code >=} at the boundary counts).</li>
 * </ul>
 *
 * <p>Pure / stateless — no Spring dependency.
 */
public final class GoldenSignalExtractor {

    /** ADR-0068 §1: an HTTP status at or above this is an error sample. */
    public static final int ERROR_STATUS_THRESHOLD = 400;

    private final SaturationConfig saturationConfig;

    public GoldenSignalExtractor(final SaturationConfig saturationConfig) {
        this.saturationConfig = saturationConfig;
    }

    /**
     * Extract a {@link SignalEvent} from a (validated, IP-masked) log entry.
     *
     * @param entry the log entry
     * @return the extracted signal event
     */
    public SignalEvent extract(final LogEntry entry) {
        final boolean error = entry.statusCode() >= ERROR_STATUS_THRESHOLD;
        final boolean saturated = entry.bytesSent() >= saturationConfig.thresholdFor(entry.path());
        return new SignalEvent(
                entry.path(),
                entry.responseTimeMs(),
                error,
                saturated,
                entry.timestamp());
    }
}
