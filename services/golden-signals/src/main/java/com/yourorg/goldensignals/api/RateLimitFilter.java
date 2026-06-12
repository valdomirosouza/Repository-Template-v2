package com.yourorg.goldensignals.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Per-key sliding-window rate limiter on {@code POST /ingestion} (FR-11). Allows
 * up to {@code RATE_LIMIT_PER_MINUTE} (default 600) requests per API key in any
 * rolling 60-second window; over the cap ⇒ {@code 429} with a {@code Retry-After}
 * header. Runs after authentication so it limits per authenticated key.
 *
 * <p>Sliding window: a per-key timestamp deque is pruned to the last 60s on each
 * request; the request is admitted iff the pruned size is below the limit.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 20)
public class RateLimitFilter extends OncePerRequestFilter {

    private static final long WINDOW_MILLIS = 60_000L;

    private final int limitPerMinute;
    private final Map<String, Deque<Long>> hits = new ConcurrentHashMap<>();

    public RateLimitFilter(@Value("${gs.rate-limit-per-minute:600}") final int limitPerMinute) {
        this.limitPerMinute = limitPerMinute;
    }

    @Override
    protected boolean shouldNotFilter(final HttpServletRequest request) {
        return !("POST".equalsIgnoreCase(request.getMethod())
                && "/ingestion".equals(request.getRequestURI()));
    }

    @Override
    protected void doFilterInternal(
            final HttpServletRequest request,
            final HttpServletResponse response,
            final FilterChain filterChain) throws ServletException, IOException {
        final Object key = request.getAttribute(ApiKeyAuthFilter.ATTR_API_KEY);
        final String bucketKey = key != null ? key.toString() : "anonymous";
        final long now = System.currentTimeMillis();

        if (!admit(bucketKey, now)) {
            response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            response.setHeader(HttpHeaders.RETRY_AFTER, "60");
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.getWriter().write("{\"error\":\"rate_limited\",\"retry_after\":60}");
            return;
        }
        filterChain.doFilter(request, response);
    }

    private boolean admit(final String key, final long now) {
        final Deque<Long> deque = hits.computeIfAbsent(key, k -> new ArrayDeque<>());
        synchronized (deque) {
            final long cutoff = now - WINDOW_MILLIS;
            while (!deque.isEmpty() && deque.peekFirst() < cutoff) {
                deque.pollFirst();
            }
            if (deque.size() >= limitPerMinute) {
                return false;
            }
            deque.addLast(now);
            return true;
        }
    }
}
