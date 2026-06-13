package com.yourorg.domainservice.observability;

import static org.assertj.core.api.Assertions.assertThat;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** W2-11b (#229) — domain-entity business counters with bounded (empty) tag sets. */
class DomainEntityMetricsTest {

    @Test
    @DisplayName("created/activated counters increment independently")
    void countersIncrement() {
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final DomainEntityMetrics metrics = new DomainEntityMetrics(registry);

        metrics.recordCreated();
        metrics.recordCreated();
        metrics.recordActivated();

        assertThat(registry.get("domain_entity_created_total").counter().count()).isEqualTo(2.0);
        assertThat(registry.get("domain_entity_activated_total").counter().count()).isEqualTo(1.0);
    }

    @Test
    @DisplayName("counters carry no high-cardinality tags")
    void noTags() {
        final SimpleMeterRegistry registry = new SimpleMeterRegistry();
        final DomainEntityMetrics metrics = new DomainEntityMetrics(registry);

        metrics.recordCreated();

        assertThat(registry.get("domain_entity_created_total").counter().getId().getTags()).isEmpty();
    }
}
