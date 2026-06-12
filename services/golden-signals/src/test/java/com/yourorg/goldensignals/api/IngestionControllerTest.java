package com.yourorg.goldensignals.api;

import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.yourorg.goldensignals.api.dto.IngestionResponse;
import com.yourorg.goldensignals.domain.IngestionService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * WebMvc slice test for {@code POST /ingestion} (FR-01/10): 202 happy path,
 * 422 on validation failure (AC-02), and 401 on missing/invalid API key (AC-07).
 * The auth/rate-limit/trace/audit filters are imported so the security boundary
 * is exercised end-to-end through the slice.
 */
@WebMvcTest(IngestionController.class)
@Import({ApiKeyAuthFilter.class, RateLimitFilter.class, TraceIdFilter.class,
        AuditRecordingFilter.class, AuditTrail.class, GlobalExceptionHandler.class})
@TestPropertySource(properties = {
        "gs.api-keys=test-key-001",
        "gs.rate-limit-per-minute=600"
})
class IngestionControllerTest {

    private static final String VALID_BODY =
            "[{\"path\":\"/api/orders\",\"statusCode\":200,\"responseTimeMs\":12.5,"
                    + "\"bytesSent\":1024,\"clientIp\":\"203.0.113.42\",\"timestamp\":1700000000000}]";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private IngestionService ingestionService;

    @Test
    @DisplayName("valid batch with a valid key ⇒ 202 {accepted, rejected}")
    void validBatchReturns202() throws Exception {
        when(ingestionService.ingest(anyList())).thenReturn(new IngestionResponse(1, 0));

        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "test-key-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_BODY))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.accepted").value(1))
                .andExpect(jsonPath("$.rejected").value(0));
    }

    @Test
    @DisplayName("per-entry validation failure (blank path) ⇒ 422 (AC-02)")
    void validationFailureReturns422() throws Exception {
        final String badBody =
                "[{\"path\":\"\",\"statusCode\":200,\"responseTimeMs\":1.0,"
                        + "\"bytesSent\":1,\"timestamp\":1700000000000}]";

        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "test-key-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(badBody))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    @DisplayName("malformed JSON (not an array) ⇒ 422")
    void malformedJsonReturns422() throws Exception {
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "test-key-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"not\":\"an array\"}"))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    @DisplayName("missing API key ⇒ 401 (AC-07)")
    void missingKeyReturns401() throws Exception {
        mockMvc.perform(post("/ingestion")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_BODY))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("invalid API key ⇒ 401 (AC-07)")
    void invalidKeyReturns401() throws Exception {
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "wrong-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_BODY))
                .andExpect(status().isUnauthorized());
    }
}
