package com.yourorg.domainservice.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreateEntityRequest(
        @NotBlank @Size(max = 255) String name,
        @Size(max = 10000) String payload
) {
}
