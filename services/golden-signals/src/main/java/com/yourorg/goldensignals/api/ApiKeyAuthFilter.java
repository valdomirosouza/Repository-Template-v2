package com.yourorg.goldensignals.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * API-key authentication (FR-10). Requires a valid {@code X-API-Key} header on
 * {@code /ingestion}, {@code /analytics}, {@code /analytics/paths} and {@code /audit};
 * <strong>not</strong> on {@code /analytics/health} (the health probe is
 * unauthenticated, FR-10/AC-07). Missing or invalid key ⇒ 401.
 *
 * <p>Keys come from {@code GS_API_KEYS} (comma-separated, NFR-04) and are compared
 * in constant time (SHA-256 digest equality) to avoid timing side-channels.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public final class ApiKeyAuthFilter extends OncePerRequestFilter {

    /** Header carrying the API key. */
    public static final String API_KEY_HEADER = "X-API-Key";
    /** Request attribute exposing the presented key to the audit trail. */
    public static final String ATTR_API_KEY = "gs.apiKey";

    private final Set<byte[]> keyDigests = new HashSet<>();

    public ApiKeyAuthFilter(@Value("${gs.api-keys:}") final String apiKeysCsv) {
        if (apiKeysCsv != null && !apiKeysCsv.isBlank()) {
            for (final String raw : apiKeysCsv.split(",")) {
                final String key = raw.trim();
                if (!key.isEmpty()) {
                    keyDigests.add(sha256(key));
                }
            }
        }
    }

    @Override
    protected boolean shouldNotFilter(final HttpServletRequest request) {
        final String path = request.getRequestURI();
        // Health is unauthenticated (FR-10). Also skip actuator + non-protected paths.
        if (path.equals("/analytics/health") || path.startsWith("/actuator")) {
            return true;
        }
        return !(path.equals("/ingestion")
                || path.equals("/analytics")
                || path.equals("/analytics/paths")
                || path.equals("/audit"));
    }

    @Override
    protected void doFilterInternal(
            final HttpServletRequest request,
            final HttpServletResponse response,
            final FilterChain filterChain) throws ServletException, IOException {
        final String presented = request.getHeader(API_KEY_HEADER);
        if (presented == null || presented.isBlank() || !isValid(presented)) {
            reject(response);
            return;
        }
        request.setAttribute(ATTR_API_KEY, presented);
        filterChain.doFilter(request, response);
    }

    private boolean isValid(final String presented) {
        final byte[] presentedDigest = sha256(presented);
        boolean valid = false;
        // Iterate all keys (no early-exit) for constant-time-ish comparison.
        for (final byte[] known : keyDigests) {
            if (MessageDigest.isEqual(known, presentedDigest)) {
                valid = true;
            }
        }
        return valid;
    }

    private static void reject(final HttpServletResponse response) throws IOException {
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write("{\"error\":\"unauthorized\",\"message\":\"missing or invalid API key\"}");
    }

    private static byte[] sha256(final String s) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8));
        } catch (final java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    /** Number of configured keys (test/observability support). */
    int configuredKeyCount() {
        return keyDigests.size();
    }
}
