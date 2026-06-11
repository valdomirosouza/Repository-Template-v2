package com.yourorg.goldensignals.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.yourorg.goldensignals.api.dto.AnalyticsResponse;
import com.yourorg.goldensignals.api.dto.AnalyticsResponse.GovernanceBlock;
import com.yourorg.goldensignals.api.dto.AnalyticsResponse.Summary;
import com.yourorg.goldensignals.domain.AnalyticsService;
import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/** FR-07/08/09/10/12 — analytics read endpoints + auth boundary (health exempt). */
@WebMvcTest(AnalyticsController.class)
@Import({ApiKeyAuthFilter.class, TraceIdFilter.class, AuditRecordingFilter.class,
        AuditTrail.class, GlobalExceptionHandler.class})
@TestPropertySource(properties = "gs.api-keys=test-key-001")
class AnalyticsControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private AnalyticsService analyticsService;

    private static AnalyticsResponse sample() {
        return new AnalyticsResponse(
                List.of(),
                new Summary(0, 0.0, null, 0),
                new GovernanceBlock("telemetry-L2", true, "1m:2h,5m:24h", "/audit", "HOTL", false));
    }

    @Test
    @DisplayName("health needs no key and returns 200 with store fields (FR-09)")
    void healthNoKey() throws Exception {
        when(analyticsService.storeConnected()).thenReturn(true);
        when(analyticsService.trackedPaths()).thenReturn(Set.of("/a", "/b"));

        mockMvc.perform(get("/analytics/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ok"))
                .andExpect(jsonPath("$.store_connected").value(true))
                .andExpect(jsonPath("$.tracked_paths").value(2));
    }

    @Test
    @DisplayName("health returns 503 when store is down (NFR-06)")
    void healthStoreDown503() throws Exception {
        when(analyticsService.storeConnected()).thenReturn(false);
        when(analyticsService.trackedPaths()).thenReturn(Set.of());

        mockMvc.perform(get("/analytics/health"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.store_connected").value(false));
    }

    @Test
    @DisplayName("analytics requires a key ⇒ 401 without it (FR-10)")
    void analyticsNeedsKey() throws Exception {
        mockMvc.perform(get("/analytics").param("path", "/api/orders"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("analytics with key returns _governance block (FR-12)")
    void analyticsGovernanceBlock() throws Exception {
        when(analyticsService.analyze(eq("/api/orders"), any(), any(), any(), any()))
                .thenReturn(sample());

        mockMvc.perform(get("/analytics")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "test-key-001")
                        .param("path", "/api/orders")
                        .param("signal", "latency")
                        .param("window", "1m"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$._governance.recommended_action_mode").value("HOTL"))
                .andExpect(jsonPath("$._governance.pii_sanitized").value(true));
    }

    @Test
    @DisplayName("unknown signal param ⇒ 422 (E8)")
    void unknownSignal422() throws Exception {
        mockMvc.perform(get("/analytics")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "test-key-001")
                        .param("path", "/api/orders")
                        .param("signal", "bogus"))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    @DisplayName("missing required path param ⇒ 422")
    void missingPath422() throws Exception {
        mockMvc.perform(get("/analytics")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "test-key-001"))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    @DisplayName("paths endpoint returns sorted tracked paths (FR-08)")
    void pathsSorted() throws Exception {
        when(analyticsService.trackedPaths()).thenReturn(Set.of("/b", "/a", "/c"));

        mockMvc.perform(get("/analytics/paths")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "test-key-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0]").value("/a"))
                .andExpect(jsonPath("$[2]").value("/c"));
    }
}
