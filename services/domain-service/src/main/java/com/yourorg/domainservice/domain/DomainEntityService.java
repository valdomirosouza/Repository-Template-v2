package com.yourorg.domainservice.domain;

import com.yourorg.domainservice.infra.kafka.DomainEventProducer;
import com.yourorg.domainservice.observability.DomainEntityMetrics;
import io.micrometer.core.annotation.Timed;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DomainEntityService {

    private final DomainEntityRepository repository;
    private final DomainEventProducer eventProducer;
    private final DomainEntityMetrics metrics;

    public DomainEntityService(
            final DomainEntityRepository repository,
            final DomainEventProducer eventProducer,
            final DomainEntityMetrics metrics) {
        this.repository = repository;
        this.eventProducer = eventProducer;
        this.metrics = metrics;
    }

    @Timed(value = "domain_entity_create_seconds", description = "Time to create a domain entity")
    @Transactional
    public DomainEntity create(final String name, final String payload) {
        DomainEntity entity = repository.save(new DomainEntity(name, payload));
        eventProducer.publishCreated(entity.getId().toString(), entity.getName());
        metrics.recordCreated();
        return entity;
    }

    @Timed(value = "domain_entity_activate_seconds", description = "Time to activate a domain entity")
    @Transactional
    public DomainEntity activate(final UUID id) {
        DomainEntity entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException(id));
        entity.activate();
        DomainEntity saved = repository.save(entity);
        eventProducer.publishUpdated(saved.getId().toString(), saved.getStatus().name());
        metrics.recordActivated();
        return saved;
    }

    @Transactional(readOnly = true)
    public List<DomainEntity> findByStatus(final EntityStatus status) {
        return repository.findByStatus(status);
    }

    @Transactional(readOnly = true)
    public DomainEntity findById(final UUID id) {
        return repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException(id));
    }
}
