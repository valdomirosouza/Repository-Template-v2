package com.yourorg.goldensignals.infra;

import com.yourorg.goldensignals.domain.Signal;
import com.yourorg.goldensignals.domain.Window;
import java.nio.charset.StandardCharsets;
import java.net.URLDecoder;
import java.net.URLEncoder;

/**
 * Key grammar for the time-series store (ADR-0068 §4). The {@code path} is
 * URL-encoded (RFC 3986 percent-encoding) before insertion into any key — this
 * is the key-injection defence (CLAUDE.md §3.2, ADR-0068): a raw path containing
 * {@code :}, {@code *}, whitespace, newline, or a literal {@code gs:} prefix
 * cannot forge or collide with another path's keys.
 *
 * <pre>
 * gs:{signal}:{path}:{window}:{epoch_bucket}            # aggregate fields
 * gs:{signal}:{path}:{window}:{epoch_bucket}:samples    # latency samples
 * gs:paths                                              # tracked paths set
 * </pre>
 *
 * <p>The same encoding is applied identically on write and read, and reversed
 * only for the FR-08 {@code paths} listing.
 */
public final class MetricKeys {

    /** Set key holding every tracked (URL-encoded) path (FR-08). */
    public static final String PATHS_KEY = "gs:paths";

    private static final String PREFIX = "gs";
    private static final String SEP = ":";
    private static final String SAMPLES_SUFFIX = "samples";

    private MetricKeys() {
    }

    /**
     * URL-encode a raw path for safe key embedding (ADR-0068 §4).
     *
     * @param path the raw request path
     * @return the percent-encoded path token
     */
    public static String encodePath(final String path) {
        return URLEncoder.encode(path, StandardCharsets.UTF_8);
    }

    /**
     * Reverse {@link #encodePath(String)} for the FR-08 paths listing.
     *
     * @param encoded the percent-encoded path token
     * @return the original raw path
     */
    public static String decodePath(final String encoded) {
        return URLDecoder.decode(encoded, StandardCharsets.UTF_8);
    }

    /**
     * Aggregate hash key {@code gs:{signal}:{path}:{window}:{epoch_bucket}}.
     *
     * @param signal      the signal
     * @param path        raw path (encoded internally)
     * @param window      the window
     * @param epochBucket epoch-second bucket start
     * @return the aggregate key
     */
    public static String aggregateKey(
            final Signal signal, final String path, final Window window, final long epochBucket) {
        return String.join(SEP,
                PREFIX, signal.token(), encodePath(path), window.token(), Long.toString(epochBucket));
    }

    /**
     * Latency-samples key {@code gs:{signal}:{path}:{window}:{epoch_bucket}:samples}.
     *
     * @param signal      the signal (typically {@link Signal#LATENCY})
     * @param path        raw path (encoded internally)
     * @param window      the window
     * @param epochBucket epoch-second bucket start
     * @return the samples key
     */
    public static String samplesKey(
            final Signal signal, final String path, final Window window, final long epochBucket) {
        return aggregateKey(signal, path, window, epochBucket) + SEP + SAMPLES_SUFFIX;
    }
}
