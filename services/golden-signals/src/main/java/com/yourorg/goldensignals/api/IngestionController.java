package com.yourorg.goldensignals.api;

import com.yourorg.goldensignals.api.dto.IngestionResponse;
import com.yourorg.goldensignals.api.dto.LogEntryDto;
import com.yourorg.goldensignals.domain.IngestionService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code POST /ingestion} (FR-01). Binds a JSON array of {@link LogEntryDto},
 * Bean-Validation enforces the per-entry contract (violations → 422 via
 * {@link GlobalExceptionHandler}, AC-02), and on success returns
 * {@code 202 {accepted, rejected}}. Auth (FR-10) and rate-limit (FR-11) are
 * applied by upstream filters before this controller runs.
 */
@RestController
@RequestMapping("/ingestion")
@Validated
public class IngestionController {

    private final IngestionService ingestionService;

    public IngestionController(final IngestionService ingestionService) {
        this.ingestionService = ingestionService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.ACCEPTED)
    public IngestionResponse ingest(@RequestBody @Valid final List<@Valid LogEntryDto> batch) {
        return ingestionService.ingest(batch);
    }
}
