package com.yourorg.goldensignals.api;

import com.yourorg.goldensignals.api.AuditTrail.Entry;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * {@code GET /audit?limit=N} (FR-14). Returns the most recent audit records
 * (timestamp, endpoint, hashed key, trace id, status). Requires a valid API key
 * (enforced upstream by {@link ApiKeyAuthFilter}).
 */
@RestController
@RequestMapping("/audit")
public class AuditController {

    private static final int DEFAULT_LIMIT = 100;
    private static final int MAX_LIMIT = 1000;

    private final AuditTrail auditTrail;

    public AuditController(final AuditTrail auditTrail) {
        this.auditTrail = auditTrail;
    }

    @GetMapping
    public List<Entry> audit(
            @RequestParam(value = "limit", defaultValue = "100") final int limit) {
        final int effective = Math.min(Math.max(1, limit <= 0 ? DEFAULT_LIMIT : limit), MAX_LIMIT);
        return auditTrail.recent(effective);
    }
}
