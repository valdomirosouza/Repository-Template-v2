package com.yourorg.domainservice.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class DomainEntityTest {

    @Test
    void newEntity_hasStatusPending() {
        DomainEntity entity = new DomainEntity("test-entity", "{\"key\":\"value\"}");

        assertThat(entity.getStatus()).isEqualTo(EntityStatus.PENDING);
        assertThat(entity.getName()).isEqualTo("test-entity");
        assertThat(entity.getCreatedAt()).isNotNull();
    }

    @Test
    void activate_changesStatusToActive() {
        DomainEntity entity = new DomainEntity("test-entity", null);

        entity.activate();

        assertThat(entity.getStatus()).isEqualTo(EntityStatus.ACTIVE);
        assertThat(entity.getUpdatedAt()).isNotNull();
    }

    @Test
    void archive_changesStatusToArchived() {
        DomainEntity entity = new DomainEntity("test-entity", null);
        entity.activate();

        entity.archive();

        assertThat(entity.getStatus()).isEqualTo(EntityStatus.ARCHIVED);
    }
}
