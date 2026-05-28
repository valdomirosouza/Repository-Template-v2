package com.yourorg.domainservice.api;

import com.yourorg.domainservice.domain.EntityNotFoundException;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(EntityNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Map<String, Object> handleNotFound(final EntityNotFoundException ex) {
        return Map.of(
                "error", "not_found",
                "message", ex.getMessage(),
                "timestamp", Instant.now().toString()
        );
    }
}
