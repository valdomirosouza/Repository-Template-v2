package com.yourorg.domainservice.observability;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

/**
 * Business metrics for the domain-entity lifecycle, exported on
 * {@code /actuator/prometheus} (W2-11b, tracking #229). HTTP latency/throughput are
 * already covered by the actuator's auto-configured {@code http.server.requests}
 * timer; this adds the domain-level counters that timer cannot express.
 *
 * <p>No high-cardinality labels: entity id and free-text name are never used as tags.
 */
@Component
public class DomainEntityMetrics {

    private final Counter createdTotal;
    private final Counter activatedTotal;

    public DomainEntityMetrics(final MeterRegistry registry) {
        this.createdTotal = Counter.builder("domain_entity_created_total")
                .description("Domain entities created")
                .register(registry);
        this.activatedTotal = Counter.builder("domain_entity_activated_total")
                .description("Domain entities transitioned to ACTIVE")
                .register(registry);
    }

    /** Record one entity creation. */
    public void recordCreated() {
        createdTotal.increment();
    }

    /** Record one entity activation. */
    public void recordActivated() {
        activatedTotal.increment();
    }
}
