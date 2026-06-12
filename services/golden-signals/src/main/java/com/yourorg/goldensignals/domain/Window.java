package com.yourorg.goldensignals.domain;

import java.util.Locale;

/**
 * Aggregation windows: 1-minute (60s) and 5-minute (300s), both epoch-aligned
 * (ADR-0068 §3). Key/wire tokens are {@code 1m|5m}.
 */
public enum Window {
    ONE_MINUTE("1m", 60L),
    FIVE_MINUTE("5m", 300L);

    private final String token;
    private final long seconds;

    Window(final String token, final long seconds) {
        this.token = token;
        this.seconds = seconds;
    }

    /** Key/wire token ({@code 1m} or {@code 5m}). */
    public String token() {
        return token;
    }

    /** Window length in seconds (60 or 300). */
    public long seconds() {
        return seconds;
    }

    /**
     * Parse a wire token to a {@link Window}.
     *
     * @param token {@code 1m} or {@code 5m}
     * @return the matching window
     * @throws IllegalArgumentException if the token is unknown (maps to 422 at the API)
     */
    public static Window fromToken(final String token) {
        if (token == null) {
            throw new IllegalArgumentException("window is required");
        }
        return switch (token.toLowerCase(Locale.ROOT)) {
            case "1m" -> ONE_MINUTE;
            case "5m" -> FIVE_MINUTE;
            default -> throw new IllegalArgumentException("unknown window: " + token);
        };
    }
}
