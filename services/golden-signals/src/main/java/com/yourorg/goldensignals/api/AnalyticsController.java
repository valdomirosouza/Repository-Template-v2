package com.yourorg.goldensignals.api;

import com.yourorg.goldensignals.api.dto.AnalyticsResponse;
import com.yourorg.goldensignals.api.dto.HealthResponse;
import com.yourorg.goldensignals.domain.AnalyticsService;
import com.yourorg.goldensignals.domain.Signal;
import com.yourorg.goldensignals.domain.Window;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Read endpoints (FR-07/08/09).
 * <ul>
 *   <li>{@code GET /analytics} — P50/P95/P99 per bucket + summary + {@code _governance} (FR-07/12/13).</li>
 *   <li>{@code GET /analytics/paths} — sorted tracked paths (FR-08).</li>
 *   <li>{@code GET /analytics/health} — {status, store_connected, tracked_paths}; 503 if store down (FR-09).</li>
 * </ul>
 * {@code signal}/{@code window} outside their enum ⇒ 422 (E8) via the enum
 * {@code fromToken} parsers and {@link GlobalExceptionHandler}.
 */
@RestController
@RequestMapping("/analytics")
public class AnalyticsController {

    private final AnalyticsService analyticsService;

    public AnalyticsController(final AnalyticsService analyticsService) {
        this.analyticsService = analyticsService;
    }

    @GetMapping
    public AnalyticsResponse analytics(
            @RequestParam("path") final String path,
            @RequestParam(value = "signal", defaultValue = "latency") final String signal,
            @RequestParam(value = "window", defaultValue = "1m") final String window,
            @RequestParam(value = "from", required = false) final Long fromEpochSeconds,
            @RequestParam(value = "to", required = false) final Long toEpochSeconds) {
        final Signal sig = Signal.fromToken(signal);     // unknown ⇒ IllegalArgumentException ⇒ 422
        final Window win = Window.fromToken(window);      // unknown ⇒ 422
        final Instant from = fromEpochSeconds == null ? null : Instant.ofEpochSecond(fromEpochSeconds);
        final Instant to = toEpochSeconds == null ? null : Instant.ofEpochSecond(toEpochSeconds);
        return analyticsService.analyze(path, sig, win, from, to);
    }

    @GetMapping("/paths")
    public List<String> paths() {
        final List<String> sorted = new ArrayList<>(analyticsService.trackedPaths());
        sorted.sort(Comparator.naturalOrder());
        return sorted;
    }

    @GetMapping("/health")
    public ResponseEntity<HealthResponse> health() {
        final boolean connected = analyticsService.storeConnected();
        final int trackedPaths = analyticsService.trackedPaths().size();
        final HealthResponse body = new HealthResponse(
                connected ? "ok" : "degraded", connected, trackedPaths);
        return connected
                ? ResponseEntity.ok(body)
                : ResponseEntity.status(503).body(body);
    }
}
