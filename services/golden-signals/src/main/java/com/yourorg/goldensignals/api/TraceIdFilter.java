package com.yourorg.goldensignals.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Reads or generates the {@code X-Trace-Id} header, echoes it on the response and
 * places it in the SLF4J MDC for structured JSON logs (NFR-03). Runs first so
 * downstream filters and the audit trail can attach the trace id.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TraceIdFilter extends OncePerRequestFilter {

    /** Request/response header carrying the trace id. */
    public static final String TRACE_ID_HEADER = "X-Trace-Id";
    /** MDC key for the trace id. */
    public static final String MDC_TRACE_ID = "trace_id";
    /** Request attribute exposing the resolved trace id to controllers. */
    public static final String ATTR_TRACE_ID = "gs.traceId";

    @Override
    protected void doFilterInternal(
            final HttpServletRequest request,
            final HttpServletResponse response,
            final FilterChain filterChain) throws ServletException, IOException {
        String traceId = request.getHeader(TRACE_ID_HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = UUID.randomUUID().toString();
        }
        request.setAttribute(ATTR_TRACE_ID, traceId);
        response.setHeader(TRACE_ID_HEADER, traceId);
        MDC.put(MDC_TRACE_ID, traceId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_TRACE_ID);
        }
    }
}
