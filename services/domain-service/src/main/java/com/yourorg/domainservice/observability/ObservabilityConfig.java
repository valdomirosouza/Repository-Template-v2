package com.yourorg.domainservice.observability;

import io.micrometer.core.aop.TimedAspect;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Enables the {@link io.micrometer.core.annotation.Timed @Timed} annotation on Spring
 * beans by registering the {@link TimedAspect} (W2-11b, #229). Distributed tracing
 * (Micrometer Tracing → OTel over OTLP) is wired by Spring Boot auto-configuration from
 * {@code management.tracing.*} / {@code management.otlp.tracing.*} in {@code application.yml}.
 */
@Configuration
public class ObservabilityConfig {

    @Bean
    public TimedAspect timedAspect(final MeterRegistry registry) {
        return new TimedAspect(registry);
    }
}
