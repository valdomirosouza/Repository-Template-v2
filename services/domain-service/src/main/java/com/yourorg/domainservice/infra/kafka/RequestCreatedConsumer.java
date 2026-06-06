package com.yourorg.domainservice.infra.kafka;

import com.yourorg.domainservice.domain.DomainEntityService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class RequestCreatedConsumer {

    private static final Logger LOG = LoggerFactory.getLogger(RequestCreatedConsumer.class);

    private final DomainEntityService entityService;

    public RequestCreatedConsumer(final DomainEntityService entityService) {
        this.entityService = entityService;
    }

    @KafkaListener(topics = "${app.kafka.topics.request-created}", groupId = "${spring.kafka.consumer.group-id}")
    public void onRequestCreated(final String message) {
        LOG.info("Received request.created event: {}", message);
        // TODO: parse message and trigger domain processing
        // Example: entityService.create(name, payload) after extracting fields
    }
}
