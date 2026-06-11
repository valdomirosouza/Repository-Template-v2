package com.yourorg.goldensignals.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Records an immutable audit entry for every protected request after the chain
 * completes (FR-14, ADR-0026). Runs after auth/rate-limit so it captures the
 * presented (hashed) key and the final status. {@code /analytics/health} and
 * actuator paths are not audited (unauthenticated probes).
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 30)
public class AuditRecordingFilter extends OncePerRequestFilter {

    private final AuditTrail auditTrail;

    public AuditRecordingFilter(final AuditTrail auditTrail) {
        this.auditTrail = auditTrail;
    }

    @Override
    protected boolean shouldNotFilter(final HttpServletRequest request) {
        final String path = request.getRequestURI();
        return path.equals("/analytics/health") || path.startsWith("/actuator");
    }

    @Override
    protected void doFilterInternal(
            final HttpServletRequest request,
            final HttpServletResponse response,
            final FilterChain filterChain) throws ServletException, IOException {
        try {
            filterChain.doFilter(request, response);
        } finally {
            final Object key = request.getAttribute(ApiKeyAuthFilter.ATTR_API_KEY);
            final Object traceId = request.getAttribute(TraceIdFilter.ATTR_TRACE_ID);
            auditTrail.record(
                    request.getMethod() + " " + request.getRequestURI(),
                    key != null ? key.toString() : null,
                    traceId != null ? traceId.toString() : null,
                    response.getStatus());
        }
    }
}
