package com.yourorg.goldensignals.api;

/**
 * Raised when the {@link com.yourorg.goldensignals.infra.MetricStore} is not
 * reachable, mapped to a 503 by {@link GlobalExceptionHandler} (NFR-06, FR-09).
 */
public class StoreUnavailableException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public StoreUnavailableException(final String message) {
        super(message);
    }
}
