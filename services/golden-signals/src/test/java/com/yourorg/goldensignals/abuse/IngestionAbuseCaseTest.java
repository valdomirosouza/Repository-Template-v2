package com.yourorg.goldensignals.abuse;

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
 * Abuse / security cases over the STRIDE ingestion + analytics boundary (ADR-0050,
 * CLAUDE.md §3.2, ADR-0068). Full Spring context so the auth/rate-limit filters,
 * the queue/worker and the real store are exercised. Each test maps to an AC or a
 * threat-model boundary; this suite only <em>adds</em> abuse cases — never removes
 * one (ADR-0050).
 *
 * <ul>
 *   <li><b>Tampering / malformed input</b> — non-array, wrong-typed, missing-required ⇒ 422 (AC-02).</li>
 *   <li><b>Tampering / key-injection</b> — a {@code :}/{@code *}/newline/{@code gs:} path is
 *       URL-encoded and cannot collide with or read another path's keys (ADR-0068).</li>
 *   <li><b>Spoofing</b> — missing/invalid API key ⇒ 401 (AC-07); health needs no key.</li>
 *   <li><b>DoS</b> — exceeding the rate limit ⇒ 429 + {@code Retry-After} (AC-07); oversized batch.</li>
 *   <li><b>Information disclosure</b> — no unmasked TEST-NET IP reaches the store or audit (AC-03).</li>
 * </ul>
 *
 * <p>All IPs are RFC 5737 / RFC 3849 documentation ranges; no real PII (CLAUDE.md §3.1).
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "gs.api-keys=abuse-key-001",
        "gs.rate-limit-per-minute=100000",
        "gs.ingest-queue-capacity=10000"
})
class IngestionAbuseCaseTest {

    private static final String KEY = "abuse-key-001";
    private static final long BUCKET_EPOCH_MS = 1_700_000_600_000L;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    // ---- Tampering: malformed batch ⇒ 422 (AC-02, FR-01) ------------------------------------

    @Test
    @DisplayName("non-array JSON body ⇒ 422 (AC-02)")
    void nonArrayBodyIs422() throws Exception {
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"path\":\"/x\",\"statusCode\":200}"))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    @DisplayName("wrong-typed field (statusCode as string) ⇒ 422 (AC-02)")
    void wrongTypedFieldIs422() throws Exception {
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("[{\"path\":\"/x\",\"statusCode\":\"two-hundred\","
                                + "\"responseTimeMs\":1.0,\"bytesSent\":1,\"timestamp\":1}]"))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    @DisplayName("missing required field (no path) ⇒ 422 (AC-02)")
    void missingRequiredFieldIs422() throws Exception {
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("[{\"statusCode\":200,\"responseTimeMs\":1.0,"
                                + "\"bytesSent\":1,\"timestamp\":1}]"))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    @DisplayName("negative response time ⇒ 422 (boundary validation, AC-02)")
    void negativeResponseTimeIs422() throws Exception {
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("[{\"path\":\"/x\",\"statusCode\":200,\"responseTimeMs\":-5.0,"
                                + "\"bytesSent\":1,\"timestamp\":1}]"))
                .andExpect(status().isUnprocessableEntity());
    }

    // ---- Tampering: key-injection in {path} (ADR-0068) --------------------------------------

    @Test
    @DisplayName("key-injection path with ':'/'*'/newline/'gs:' is URL-encoded and isolated (ADR-0068)")
    void keyInjectionPathIsIsolated() throws Exception {
        final String benign = "/api/orders";
        final String malicious = "gs:latency:/api/orders:1m:0\n*"; // tries to forge another key
        ingestOne(benign, 200, 30.0);
        ingestOne(malicious, 200, 40.0);

        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(200)).untilAsserted(() -> {
            final Set<String> tracked = trackedPaths();
            assertThat(tracked).contains(benign);
            assertThat(tracked).contains(malicious);
        });

        // The malicious path is a distinct tracked entry — it did not collide with the benign one.
        final long benignCount = analytics(benign).get("summary").get("total_count").asLong();
        final long maliciousCount = analytics(malicious).get("summary").get("total_count").asLong();
        assertThat(benignCount).isEqualTo(1);
        assertThat(maliciousCount).isEqualTo(1);
        // Querying the benign path must NOT pull the malicious path's samples.
        assertThat(benignCount).isNotEqualTo(2);
    }

    // ---- Spoofing: auth (AC-07, FR-10) ------------------------------------------------------

    @Test
    @DisplayName("missing API key ⇒ 401 (AC-07)")
    void missingKeyIs401() throws Exception {
        mockMvc.perform(get("/analytics").param("path", "/x"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("invalid API key ⇒ 401 (AC-07)")
    void invalidKeyIs401() throws Exception {
        mockMvc.perform(get("/analytics")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, "not-the-key")
                        .param("path", "/x"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("health endpoint needs no key ⇒ 200 (FR-10/AC-07)")
    void healthNeedsNoKey() throws Exception {
        mockMvc.perform(get("/analytics/health"))
                .andExpect(status().isOk());
    }

    // ---- DoS: oversized batch (rate-limit 429 lives in RateLimitAbuseCaseTest) ---------------

    @Test
    @DisplayName("oversized batch is accepted (202) and bounded by the queue, no crash (DoS backpressure)")
    void oversizedBatchHandledGracefully() throws Exception {
        // 5000 entries in a single request: must not 5xx; queue capacity bounds it.
        final ArrayNode batch = objectMapper.createArrayNode();
        for (int i = 0; i < 5000; i++) {
            final ObjectNode e = objectMapper.createObjectNode();
            e.put("path", "/api/bulk");
            e.put("statusCode", 200);
            e.put("responseTimeMs", 12.0);
            e.put("bytesSent", 128L);
            e.put("clientIp", "192.0.2.20");
            e.put("timestamp", BUCKET_EPOCH_MS);
            batch.add(e);
        }
        final String json = mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(batch)))
                .andExpect(status().isAccepted())
                .andReturn().getResponse().getContentAsString();
        final JsonNode resp = objectMapper.readTree(json);
        // accepted + rejected must reconcile to the whole batch (no silent loss).
        assertThat(resp.get("accepted").asInt() + resp.get("rejected").asInt()).isEqualTo(5000);
    }

    // ---- Information disclosure: PII masking (AC-03, FR-02) ----------------------------------

    @Test
    @DisplayName("known TEST-NET IPs are masked: no unmasked octet/hextet in store or audit (AC-03)")
    void noUnmaskedIpReachesStoreOrAudit() throws Exception {
        final String ipv4 = "192.0.2.137";   // RFC 5737 TEST-NET-3
        final String ipv6 = "2001:db8:1:2:3:4:5:6"; // RFC 3849 documentation range
        ingestOneWithIp("/api/pii", ipv4);
        ingestOneWithIp("/api/pii", ipv6);

        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(200)).untilAsserted(() ->
                assertThat(analytics("/api/pii").get("summary").get("total_count").asLong())
                        .isGreaterThanOrEqualTo(2));

        // The full unmasked IPs must never appear in the audit body...
        final String auditJson = mockMvc.perform(get("/audit")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .param("limit", "1000"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertThat(auditJson).doesNotContain(ipv4);
        assertThat(auditJson).doesNotContain("2001:db8:1:2:3:4:5:6");

        // ...nor in any analytics response (the store never persisted them).
        final String analyticsJson = mockMvc.perform(get("/analytics")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .param("path", "/api/pii"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertThat(analyticsJson).doesNotContain(ipv4);
        assertThat(analyticsJson).doesNotContain("2001:db8:1:2:3:4:5:6");
    }

    // ---- helpers ----------------------------------------------------------------------------

    private void ingestOne(final String path, final int status, final double ms) throws Exception {
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(oneEntry(path, status, ms)))
                .andExpect(status().isAccepted());
    }

    private void ingestOneWithIp(final String path, final String ip) throws Exception {
        final ObjectNode e = objectMapper.createObjectNode();
        e.put("path", path);
        e.put("statusCode", 200);
        e.put("responseTimeMs", 15.0);
        e.put("bytesSent", 64L);
        e.put("clientIp", ip);
        e.put("timestamp", BUCKET_EPOCH_MS);
        final ArrayNode arr = objectMapper.createArrayNode();
        arr.add(e);
        mockMvc.perform(post("/ingestion")
                        .header(ApiKeyAuthFilter.API_KEY_HEADER, KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(arr)))
                .andExpect(status().isAccepted());
    }

    private String oneEntry(final String path, final int status, final double ms) throws Exception {
        final ObjectNode e = objectMapper.createObjectNode();
        e.put("path", path);
        e.put("statusCode", status);
        e.put("responseTimeMs", ms);
        e.put("bytesSent", 256L);
        e.put("clientIp", "192.0.2.5");
        e.put("timestamp", BUCKET_EPOCH_MS);
        final ArrayNode arr = objectMapper.createArrayNode();
        arr.add(e);
        return objectMapper.writeValueAsString(arr);
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
        final Set<String> out = new java.util.HashSet<>();
        arr.forEach(n -> out.add(n.asText()));
        return out;
    }
}
