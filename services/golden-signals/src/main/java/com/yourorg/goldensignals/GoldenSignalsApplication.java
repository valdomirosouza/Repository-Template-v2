package com.yourorg.goldensignals;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Golden Signals service entry point (SPEC-LGS-001). Single Spring Boot
 * deployable hosting the four logical pipeline components (ingestion, queue,
 * worker/aggregation, analytics) decoupled in-JVM by the bounded queue
 * (ADR-0069). Virtual threads are enabled via {@code spring.threads.virtual.enabled}.
 */
@SpringBootApplication
public class GoldenSignalsApplication {

    public static void main(final String[] args) {
        SpringApplication.run(GoldenSignalsApplication.class, args);
    }
}
