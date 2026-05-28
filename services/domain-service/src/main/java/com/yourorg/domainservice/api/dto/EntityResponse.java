package com.yourorg.domainservice.api.dto;

import com.yourorg.domainservice.domain.DomainEntity;
import java.time.Instant;
import java.util.UUID;

public record EntityResponse(
        UUID id,
        String name,
        String status,
        Instant createdAt,
        Instant updatedAt
) {
    public static EntityResponse from(final DomainEntity entity) {
        return new EntityResponse(
                entity.getId(),
                entity.getName(),
                entity.getStatus().name(),
                entity.getCreatedAt(),
                entity.getUpdatedAt()
        );
    }
}
