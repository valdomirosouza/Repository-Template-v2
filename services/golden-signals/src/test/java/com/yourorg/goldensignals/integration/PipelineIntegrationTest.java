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
import java.util.HashSet;
import java.util.Set;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

/**
 * Full-pipeline integration (AC-04/05/10, FR-04/05/07/08): the real Spring context
 * with the in-memory {@code MetricStore} profile, the bounded queue and the live
 * virtual-thread {@code AggregationWorker}. Seeds ~1k synthetic entries across ≥5
 * paths over {@code POST /ingestion}, lets the async worker drain and flush, then
 * asserts {@code GET /analytics} returns non-empty numeric P50/P95/P99 and the
 * observed error rate is within ±2% of the injected rate.
 *
 * <p>Synthetic only — IPs are RFC 5737 TEST-NET-3 ({@code 192.0.2.0/24}); no real
 * PII (CLAUDE.md §3.1).
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "gs.api-keys=integ-key-001",
        "gs.rate-limit-per-minute=100000",
        "gs.hitl-p99-latency-ms=1000",
        "gs.hitl-error-rate=0.05"
})
class PipelineIntegrationTest {

    private static final String KEY = "integ-key-001";
    private static final String[] PATHS = {
            "/api/orders", "/api/users", "/api/products", "/api/cart", "/api/checkout"
    };
    private static final int ENTRIES = 1000;
    /** Deterministic injected error fraction: every 10th entry is a 500 ⇒ 10%. */
    private static final int ERROR_EVERY = 10;
    private static final double INJECTED_ERROR_RATE = 1.0 / ERROR_EVERY;
    private static final long BUCKET_EPOCH_MS = 1_700_000_000_000L; // fixed ⇒ one 1m bucket per path

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("seed ~1k entries → drain → /analytics has numeric P50/P95/P99 and ±2% error rate (AC-04/10)")
    void fullPipelineProducesPercentilesAndErrorRate() throws Exception {
        final int seededErrors = seedBatch();

        // Drain: poll the analytics endpoint until the worker has flushed all entries.
        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(200)).untilAsserted(() -> {
            final long total = totalCount("/api/orders");
            assertThat(total).isPositive();
        });

        // AC-04: non-empty numeric P50/P95/P99 on a seeded path.
        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(200)).untilAsserted(() -> {
            final JsonNode root = analytics("/api/orders");
            final JsonNode buckets = root.get("buckets");
            assertThat(buckets).isNotNull();
            assertThat(buckets.size()).isPositive();
            final JsonNode b = buckets.get(0);
            assertThat(b.get("p50").isNumber()).isTrue();
            assertThat(b.get("p95").isNumber()).isTrue();
            assertThat(b.get("p99").isNumber()).isTrue();
            assertThat(b.get("p50").asDouble()).isPositive();
            assertThat(b.get("p99").asDouble()).isGreaterThanOrEqualTo(b.get("p50").asDouble());
        });

        // AC-10: aggregate error rate across all seeded paths within ±2% of injected.
        long observedTotal = 0;
        long observedErrors = 0;
        for (final String path : PATHS) {
            final JsonNode root = analytics(path);
            final JsonNode summary = root.get("summary");
            final long count = summary.get("total_count").asLong();
            final double rate = summary.get("error_rate").asDouble();
            observedTotal += count;
            observedErrors += Math.round(rate * count);
        }
        assertThat(observedTotal).isEqualTo(ENTRIES);
        final double observedRate = (double) observedErrors / observedTotal;
        assertThat(observedRate).isCloseTo(INJECTED_ERROR_RATE,
                org.assertj.core.data.Offset.offset(0.02));
        // Cross-check the seeded count matches the deterministic injection.
        assertThat(observedErrors).isEqualTo(seededErrors);
    }

    @Test
    @DisplayName("/analytics/paths lists every seeded path (AC-05)")
    void analyticsPathsListsEverySeededPath() throws Exception {
        seedBatch();
        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(200)).untilAsserted(() -> {
            final Set<String> tracked = trackedPaths();
            for (final String p : PATHS) {
                assertThat(tracked).contains(p);
            }
        });
    }

    /** Seed one batch of ENTRIES entries round-robin across PATHS; returns injected error count. */
    private int seedBatch() throws Exception {
        final ArrayNode batch = objectMapper.createArrayNode();
        int errors = 0;
        for (int i = 0; i < ENTRIES; i++) {
            final String path = PATHS[i % PATHS.length];
            final boolean isError = (i % ERROR_EVERY) == 0;
            if (isError) {
                errors++;
            }
            final ObjectNode e = objectMapper.createObjectNode();
            e.put("path", path);
            e.put("statusCode", isError ? 500 : 200);
            e.put("responseTimeMs", 10.0 + (i % 100));     // deterministic spread 10..109ms
            e.put("bytesSent", 2048L);
            e.put("clientIp", "192.0.2." + (i % 254 + 1)); // RFC 5737 TEST-NET-3
            e.put("timestamp", BUCKET_EPOCH_MS);           // all into one 1m bucket per path
            batch.add(e);
        }
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(batch)))
                .andExpect(status().isAccepted());
        return errors;
    }

    private long totalCount(final String path) throws Exception {
        return analytics(path).get("summary").get("total_count").asLong();
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

    private Set<String> trackedPaths() throws Exception {
        final String json = mockMvc.perform(get("/analytics/paths")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        final JsonNode arr = objectMapper.readTree(json);
        final Set<String> out = new HashSet<>();
        arr.forEach(n -> out.add(n.asText()));
        return out;
    }
}
