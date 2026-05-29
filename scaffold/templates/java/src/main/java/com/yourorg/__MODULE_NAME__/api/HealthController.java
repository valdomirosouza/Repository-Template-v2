package com.yourorg.__MODULE_NAME__.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class HealthController {

    @Value("${spring.application.name:__SERVICE_NAME__}")
    private String serviceName;

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok", "service", serviceName);
    }

    @GetMapping("/ready")
    public Map<String, String> ready() {
        // TODO: add dependency checks (DB, Redis, etc.)
        return Map.of("status", "ready");
    }
}
