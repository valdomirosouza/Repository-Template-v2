package com.yourorg.domainservice.domain;

import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DomainEntityRepository extends JpaRepository<DomainEntity, UUID> {

    List<DomainEntity> findByStatus(EntityStatus status);
}
