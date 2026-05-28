package com.yourorg.domainservice.domain;

import com.yourorg.domainservice.infra.kafka.DomainEventProducer;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DomainEntityService {

    private final DomainEntityRepository repository;
    private final DomainEventProducer eventProducer;

    public DomainEntityService(
            final DomainEntityRepository repository,
            final DomainEventProducer eventProducer) {
        this.repository = repository;
        this.eventProducer = eventProducer;
    }

    @Transactional
    public DomainEntity create(final String name, final String payload) {
        DomainEntity entity = repository.save(new DomainEntity(name, payload));
        eventProducer.publishCreated(entity.getId().toString(), entity.getName());
        return entity;
    }

    @Transactional
    public DomainEntity activate(final UUID id) {
        DomainEntity entity = repository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException(id));
        entity.activate();
        DomainEntity saved = repository.save(entity);
        eventProducer.publishUpdated(saved.getId().toString(), saved.getStatus().name());
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
