package com.yourorg.goldensignals.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.yourorg.goldensignals.api.ApiKeyAuthFilter;
import java.time.Duration;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * Governance flip (AC-08, FR-13) and immutable audit trail (AC-09, FR-14) over the
 * real Spring context with the in-memory store. A flood of high-latency entries must
 * flip {@code recommended_action_mode} to {@code HITL} and {@code human_approval_required}
 * to {@code true}; {@code GET /audit?limit=N} must return the last N records with a
 * hashed key (never the raw key).
 *
 * <p>Synthetic data only (CLAUDE.md §3.1).
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "gs.api-keys=gov-key-001",
        "gs.rate-limit-per-minute=100000",
        "gs.hitl-p99-latency-ms=1000",
        "gs.hitl-error-rate=0.05"
})
class GovernanceAndAuditIntegrationTest {

    private static final String KEY = "gov-key-001";
    private static final long BUCKET_EPOCH_MS = 1_700_000_300_000L;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("high-latency flood flips recommended_action_mode to HITL + approval required (AC-08/FR-13)")
    void highLatencyFlipsGovernanceToHitl() throws Exception {
        // Seed 200 entries all at 5000ms (> 1000ms HITL threshold) into one bucket.
        final ArrayNode batch = objectMapper.createArrayNode();
        for (int i = 0; i < 200; i++) {
            final ObjectNode e = objectMapper.createObjectNode();
            e.put("path", "/api/slow");
            e.put("statusCode", 200);
            e.put("responseTimeMs", 5000.0);
            e.put("bytesSent", 1024L);
            e.put("clientIp", "192.0.2.10");
            e.put("timestamp", BUCKET_EPOCH_MS);
            batch.add(e);
        }
        ingest(batch);

        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(200)).untilAsserted(() -> {
            final JsonNode gov = analytics("/api/slow").get("_governance");
            assertThat(gov.get("recommended_action_mode").asText()).isEqualTo("HITL");
            assertThat(gov.get("human_approval_required").asBoolean()).isTrue();
            assertThat(gov.get("pii_sanitized").asBoolean()).isTrue();
        });
    }

    @Test
    @DisplayName("normal-latency data stays HOTL, no approval required (FR-13 negative)")
    void normalLatencyStaysHotl() throws Exception {
        final ArrayNode batch = objectMapper.createArrayNode();
        for (int i = 0; i < 50; i++) {
            final ObjectNode e = objectMapper.createObjectNode();
            e.put("path", "/api/fast");
            e.put("statusCode", 200);
            e.put("responseTimeMs", 25.0);
            e.put("bytesSent", 256L);
            e.put("clientIp", "192.0.2.11");
            e.put("timestamp", BUCKET_EPOCH_MS);
            batch.add(e);
        }
        ingest(batch);

        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(200)).untilAsserted(() -> {
            final JsonNode root = analytics("/api/fast");
            assertThat(root.get("summary").get("total_count").asLong()).isPositive();
            final JsonNode gov = root.get("_governance");
            assertThat(gov.get("recommended_action_mode").asText()).isEqualTo("HOTL");
            assertThat(gov.get("human_approval_required").asBoolean()).isFalse();
        });
    }

    @Test
    @DisplayName("GET /audit?limit=N returns last N with hashed keys, never the raw key (AC-09/FR-14)")
    void auditReturnsHashedKeysOnly() throws Exception {
        // Generate several audited interactions.
        for (int i = 0; i < 5; i++) {
            mockMvc.perform(get("/analytics/paths")
                            .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY))
                    .andExpect(status().isOk());
        }

        final String json = mockMvc.perform(get("/audit")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .param("limit", "3"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();

        final JsonNode arr = objectMapper.readTree(json);
        assertThat(arr.isArray()).isTrue();
        assertThat(arr.size()).isEqualTo(3); // last N (AC-09)
        // The raw key must never appear anywhere in the audit body (§3.1/§3.2).
        assertThat(json).doesNotContain(KEY);
        for (final JsonNode entry : arr) {
            final String hashed = entry.get("hashedKey").asText();
            assertThat(hashed).isNotEqualTo(KEY);
            // SHA-256 hex digest is 64 lowercase hex chars (never the 9-char raw key).
            assertThat(hashed).matches("[0-9a-f]{64}");
            assertThat(entry.hasNonNull("ts")).isTrue();
            assertThat(entry.hasNonNull("endpoint")).isTrue();
            assertThat(entry.get("status").asInt()).isEqualTo(200);
        }
    }

    private void ingest(final ArrayNode batch) throws Exception {
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(batch)))
                .andExpect(status().isAccepted());
    }

    private JsonNode analytics(final String path) throws Exception {
        final String json = mockMvc.perform(get("/analytics")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .param("path", path)
                        .param("signal", "latency")
                        .param("window", "1m"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return objectMapper.readTree(json);
    }
}
