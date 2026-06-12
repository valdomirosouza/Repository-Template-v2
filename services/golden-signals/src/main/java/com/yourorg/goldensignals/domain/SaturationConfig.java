package com.yourorg.goldensignals.domain;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * Saturation threshold configuration (ADR-0068 §2): a global default with
 * optional per-path overrides. {@code bytesSent >= threshold ⇒ saturated}.
 *
 * <p>Default global threshold is 1 MiB ({@code 1048576}); the env
 * {@code SATURATION_BYTES_THRESHOLD} sets the global value and
 * {@code SATURATION_BYTES_THRESHOLD__<path>} sets a per-path override
 * (resolved in configuration, supplied here as a map).
 */
public final class SaturationConfig {

    /** ADR-0068 §2 default: 1 MiB. */
    public static final long DEFAULT_THRESHOLD_BYTES = 1_048_576L;

    private final long globalThreshold;
    private final Map<String, Long> perPathOverrides;

    public SaturationConfig(final long globalThreshold, final Map<String, Long> perPathOverrides) {
        this.globalThreshold = globalThreshold;
        this.perPathOverrides = perPathOverrides == null
                ? Collections.emptyMap()
                : Collections.unmodifiableMap(new HashMap<>(perPathOverrides));
    }

    /** Construct with only the global default and no overrides. */
    public SaturationConfig(final long globalThreshold) {
        this(globalThreshold, Collections.emptyMap());
    }

    /**
     * The effective threshold for a path: the per-path override if present,
     * else the global default (ADR-0068 §2).
     *
     * @param path the request path (raw, unencoded)
     * @return the byte threshold for this path
     */
    public long thresholdFor(final String path) {
        return perPathOverrides.getOrDefault(path, globalThreshold);
    }

    /** The global default threshold in bytes. */
    public long globalThreshold() {
        return globalThreshold;
    }
}
