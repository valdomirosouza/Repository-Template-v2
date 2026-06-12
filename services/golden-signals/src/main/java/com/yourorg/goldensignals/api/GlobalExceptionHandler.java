package com.yourorg.goldensignals.api;

import jakarta.validation.ConstraintViolationException;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

/**
 * Maps boundary failures to stable status codes without leaking PII or stack
 * traces into the response body (FR-01, CLAUDE.md §3.1/§3.2):
 * <ul>
 *   <li>Bean Validation failure / malformed JSON / unknown enum param → 422 (AC-02, E8).</li>
 *   <li>Missing required query param → 422.</li>
 *   <li>Store-unavailable → 503 (NFR-06).</li>
 * </ul>
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler({
            MethodArgumentNotValidException.class,
            ConstraintViolationException.class,
            HttpMessageNotReadableException.class,
            MissingServletRequestParameterException.class,
            MethodArgumentTypeMismatchException.class,
            IllegalArgumentException.class
    })
    @ResponseStatus(HttpStatus.UNPROCESSABLE_ENTITY)
    public Map<String, Object> handleUnprocessable(final Exception ex) {
        return body("unprocessable_entity", safeMessage(ex));
    }

    @ExceptionHandler(StoreUnavailableException.class)
    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    public Map<String, Object> handleStoreDown(final StoreUnavailableException ex) {
        return body("store_unavailable", ex.getMessage());
    }

    private static Map<String, Object> body(final String error, final String message) {
        return Map.of(
                "error", error,
                "message", message,
                "timestamp", Instant.now().toString());
    }

    /** Keep the message terse and free of any echoed payload (no PII leakage). */
    private static String safeMessage(final Exception ex) {
        if (ex instanceof MethodArgumentNotValidException manv) {
            final var fieldError = manv.getBindingResult().getFieldError();
            return fieldError != null ? fieldError.getDefaultMessage() : "validation failed";
        }
        if (ex instanceof ConstraintViolationException) {
            return "one or more entries failed validation";
        }
        if (ex instanceof MissingServletRequestParameterException mp) {
            return "missing required parameter: " + mp.getParameterName();
        }
        if (ex instanceof MethodArgumentTypeMismatchException tm) {
            return "invalid value for parameter: " + tm.getName();
        }
        if (ex instanceof IllegalArgumentException) {
            return ex.getMessage();
        }
        return "request body could not be processed";
    }
}
