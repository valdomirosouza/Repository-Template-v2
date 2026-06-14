package com.yourorg.domainservice.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.yourorg.domainservice.infra.kafka.DomainEventProducer;
import com.yourorg.domainservice.observability.DomainEntityMetrics;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class DomainEntityServiceTest {

    @Mock
    private DomainEntityRepository repository;
    @Mock
    private DomainEventProducer eventProducer;

    private SimpleMeterRegistry registry;
    private DomainEntityService service;

    @BeforeEach
    void setUp() {
        registry = new SimpleMeterRegistry();
        service = new DomainEntityService(repository, eventProducer, new DomainEntityMetrics(registry));
    }

    @Test
    void create_savesEntityAndPublishesCreatedEvent() {
        DomainEntity saved = entityWithId("widget", "{}");
        when(repository.save(any(DomainEntity.class))).thenReturn(saved);

        DomainEntity result = service.create("widget", "{}");

        assertThat(result).isSameAs(saved);
        verify(eventProducer).publishCreated(saved.getId().toString(), "widget");
        assertThat(registry.get("domain_entity_created_total").counter().count()).isEqualTo(1.0);
    }

    @Test
    void activate_findsActivatesSavesAndPublishesUpdatedEvent() {
        DomainEntity entity = entityWithId("widget", "{}");
        UUID id = entity.getId();
        when(repository.findById(id)).thenReturn(Optional.of(entity));
        when(repository.save(entity)).thenReturn(entity);

        DomainEntity result = service.activate(id);

        assertThat(result.getStatus()).isEqualTo(EntityStatus.ACTIVE);
        verify(eventProducer).publishUpdated(id.toString(), "ACTIVE");
        assertThat(registry.get("domain_entity_activated_total").counter().count()).isEqualTo(1.0);
    }

    @Test
    void activate_missingEntity_throwsNotFound() {
        UUID id = UUID.randomUUID();
        when(repository.findById(id)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.activate(id)).isInstanceOf(EntityNotFoundException.class);
    }

    @Test
    void findById_returnsEntity() {
        DomainEntity entity = entityWithId("widget", "{}");
        when(repository.findById(entity.getId())).thenReturn(Optional.of(entity));

        assertThat(service.findById(entity.getId())).isSameAs(entity);
    }

    @Test
    void findById_missingEntity_throwsNotFound() {
        UUID id = UUID.randomUUID();
        when(repository.findById(id)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.findById(id)).isInstanceOf(EntityNotFoundException.class);
    }

    @Test
    void findByStatus_delegatesToRepository() {
        DomainEntity entity = entityWithId("widget", "{}");
        when(repository.findByStatus(EntityStatus.ACTIVE)).thenReturn(List.of(entity));

        assertThat(service.findByStatus(EntityStatus.ACTIVE)).containsExactly(entity);
    }

    private static DomainEntity entityWithId(final String name, final String payload) {
        DomainEntity entity = new DomainEntity(name, payload);
        ReflectionTestUtils.setField(entity, "id", UUID.randomUUID());
        return entity;
    }
}
