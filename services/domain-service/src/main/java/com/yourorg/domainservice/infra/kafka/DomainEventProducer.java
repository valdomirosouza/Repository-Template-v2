package com.yourorg.domainservice.infra.kafka;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class DomainEventProducer {

    private static final Logger log = LoggerFactory.getLogger(DomainEventProducer.class);

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final String createdTopic;
    private final String updatedTopic;

    public DomainEventProducer(
            final KafkaTemplate<String, String> kafkaTemplate,
            @Value("${app.kafka.topics.entity-created}") final String createdTopic,
            @Value("${app.kafka.topics.entity-updated}") final String updatedTopic) {
        this.kafkaTemplate = kafkaTemplate;
        this.createdTopic = createdTopic;
        this.updatedTopic = updatedTopic;
    }

    public void publishCreated(final String entityId, final String name) {
        String payload = String.format("{\"entityId\":\"%s\",\"name\":\"%s\",\"event\":\"created\"}",
                entityId, name);
        kafkaTemplate.send(createdTopic, entityId, payload)
                .whenComplete((result, ex) -> {
                    if (ex != null) {
                        log.error("Failed to publish entity.created event for {}: {}", entityId, ex.getMessage());
                    } else {
                        log.debug("Published entity.created for {}", entityId);
                    }
                });
    }

    public void publishUpdated(final String entityId, final String status) {
        String payload = String.format("{\"entityId\":\"%s\",\"status\":\"%s\",\"event\":\"updated\"}",
                entityId, status);
        kafkaTemplate.send(updatedTopic, entityId, payload)
                .whenComplete((result, ex) -> {
                    if (ex != null) {
                        log.error("Failed to publish entity.updated event for {}: {}", entityId, ex.getMessage());
                    } else {
                        log.debug("Published entity.updated for {}", entityId);
                    }
                });
    }
}
