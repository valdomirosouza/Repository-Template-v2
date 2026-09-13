package com.yourorg.__MODULE_NAME__;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Configuration validation + contract test (scaffold starter, W15-T5).
 *
 * A copied service must resolve its documented defaults from application.properties and expose
 * the probe/scrape endpoints every service in services.yaml promises.
 */
@SpringBootTest
@AutoConfigureMockMvc
class ConfigurationContractTest {

    @Autowired
    private Environment env;

    @Autowired
    private MockMvc mockMvc;

    @Test
    void documentedDefaultsResolve() {
        assertThat(env.getProperty("spring.application.name")).isEqualTo("__SERVICE_NAME__");
        assertThat(env.getProperty("server.port")).isEqualTo("8000"); // ${APP_PORT:8000}
        assertThat(env.getProperty("management.endpoints.web.exposure.include")).contains("prometheus");
    }

    @Test
    void probeAndScrapeEndpointsAreExposed() throws Exception {
        mockMvc.perform(get("/health")).andExpect(status().isOk());
        mockMvc.perform(get("/ready")).andExpect(status().isOk());
        mockMvc.perform(get("/actuator/prometheus")).andExpect(status().isOk());
    }
}
