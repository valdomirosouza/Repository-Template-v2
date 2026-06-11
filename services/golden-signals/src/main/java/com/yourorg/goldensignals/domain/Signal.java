package com.yourorg.goldensignals.domain;

/**
 * The four Golden Signals (ADR-0068 §1). Wire/key tokens are lower-case
 * ({@code traffic|latency|error|saturation}) per the ADR-0068 key grammar §4.
 */
public enum Signal {
    TRAFFIC,
    LATENCY,
    ERROR,
    SATURATION;

    /** Key/wire token (lower-case) per ADR-0068 §4. */
    public String token() {
        return name().toLowerCase(java.util.Locale.ROOT);
    }

    /**
     * Parse a wire token to a {@link Signal}.
     *
     * @param token one of {@code traffic|latency|error|saturation}
     * @return the matching signal
     * @throws IllegalArgumentException if the token is not a known signal (maps to 422 at the API)
     */
    public static Signal fromToken(final String token) {
        if (token == null) {
            throw new IllegalArgumentException("signal is required");
        }
        return switch (token.toLowerCase(java.util.Locale.ROOT)) {
            case "traffic" -> TRAFFIC;
            case "latency" -> LATENCY;
            case "error" -> ERROR;
            case "saturation" -> SATURATION;
            default -> throw new IllegalArgumentException("unknown signal: " + token);
        };
    }
}
