package com.yourorg.goldensignals.config;

import com.yourorg.goldensignals.domain.GoldenSignalExtractor;
import com.yourorg.goldensignals.domain.GovernanceEvaluator;
import com.yourorg.goldensignals.domain.SaturationConfig;
import java.util.HashMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;

/**
 * Wires the pure domain components from env-backed configuration (NFR-04).
 * All values come from environment variables with the ADR/feature-spec §3
 * documented defaults.
 */
@Configuration
public class GoldenSignalsConfig {

    /**
     * Saturation thresholds (ADR-0068 §2): global default plus optional per-path
     * overrides bound from {@code gs.saturation-overrides.*} (env
     * {@code SATURATION_BYTES_THRESHOLD__<path>} is mapped to this prefix in
     * {@code application.yml}).
     *
     * @param globalThreshold the global default in bytes
     * @param environment     the Spring environment for binding the override map
     * @return the saturation config
     */
    @Bean
    public SaturationConfig saturationConfig(
            @Value("${gs.saturation-bytes-threshold:1048576}") final long globalThreshold,
            final Environment environment) {
        final Map<String, Long> overrides = Binder.get(environment)
                .bind("gs.saturation-overrides", Bindable.mapOf(String.class, Long.class))
                .orElseGet(HashMap::new);
        return new SaturationConfig(globalThreshold, overrides);
    }

    /**
     * The golden-signal extractor (FR-03).
     *
     * @param saturationConfig the saturation thresholds
     * @return the extractor
     */
    @Bean
    public GoldenSignalExtractor goldenSignalExtractor(final SaturationConfig saturationConfig) {
        return new GoldenSignalExtractor(saturationConfig);
    }

    /**
     * The governance evaluator (FR-12/13) with env-tuned HITL thresholds.
     *
     * @param p99LatencyMs   P99 latency HITL threshold (ms)
     * @param errorRate      error-rate HITL threshold
     * @return the evaluator
     */
    @Bean
    public GovernanceEvaluator governanceEvaluator(
            @Value("${gs.hitl-p99-latency-ms:1000}") final double p99LatencyMs,
            @Value("${gs.hitl-error-rate:0.05}") final double errorRate) {
        return new GovernanceEvaluator(p99LatencyMs, errorRate);
    }
}
