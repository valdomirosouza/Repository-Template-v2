package com.yourorg.goldensignals.abuse;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.yourorg.goldensignals.api.ApiKeyAuthFilter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * DoS abuse case (ADR-0050, AC-07, FR-11): a dedicated Spring context with a low
 * {@code gs.rate-limit-per-minute=5} so the sliding-window rate limiter on
 * {@code POST /ingestion} can be exercised in isolation without interference from
 * the other abuse cases. Exceeding the per-key cap returns {@code 429} with a
 * {@code Retry-After} header.
 *
 * <p>Isolated in its own class because {@code RateLimitFilter} keeps per-key
 * sliding-window state across the shared context (CLAUDE.md §3.6 — no flaky sleeps,
 * deterministic count). Synthetic data only.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "gs.api-keys=rl-key-001",
        "gs.rate-limit-per-minute=5"
})
class RateLimitAbuseCaseTest {

    private static final String KEY = "rl-key-001";
    private static final String ONE_ENTRY =
            "[{\"path\":\"/api/rl\",\"statusCode\":200,\"responseTimeMs\":10.0,"
                    + "\"bytesSent\":256,\"clientIp\":\"192.0.2.5\",\"timestamp\":1700000600000}]";

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("exceeding rate limit ⇒ 429 + Retry-After (AC-07/FR-11)")
    void rateLimitExceededIs429() throws Exception {
        // Limit is 5/min; the first 5 POSTs in the window succeed.
        for (int i = 0; i < 5; i++) {
            mockMvc.perform(post("/ingestion")
                            .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(ONE_ENTRY))
                    .andExpect(status().isAccepted());
        }
        // The 6th in the same window is rejected with 429 + Retry-After (FR-11).
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ONE_ENTRY))
                .andExpect(status().isTooManyRequests())
                .andExpect(header().exists(HttpHeaders.RETRY_AFTER))
                .andExpect(header().string(HttpHeaders.RETRY_AFTER, "60"));
    }
}
