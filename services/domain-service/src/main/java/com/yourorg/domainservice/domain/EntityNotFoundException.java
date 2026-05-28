package com.yourorg.domainservice.domain;

import java.util.UUID;

public class EntityNotFoundException extends RuntimeException {

    public EntityNotFoundException(final UUID id) {
        super("DomainEntity not found: " + id);
    }
}
