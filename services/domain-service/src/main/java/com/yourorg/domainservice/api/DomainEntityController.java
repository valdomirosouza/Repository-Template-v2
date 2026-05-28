package com.yourorg.domainservice.api;

import com.yourorg.domainservice.api.dto.CreateEntityRequest;
import com.yourorg.domainservice.api.dto.EntityResponse;
import com.yourorg.domainservice.domain.DomainEntityService;
import com.yourorg.domainservice.domain.EntityStatus;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/v1/entities")
public class DomainEntityController {

    private final DomainEntityService service;

    public DomainEntityController(final DomainEntityService service) {
        this.service = service;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public EntityResponse create(@Valid @RequestBody final CreateEntityRequest request) {
        return EntityResponse.from(service.create(request.name(), request.payload()));
    }

    @GetMapping("/{id}")
    public EntityResponse getById(@PathVariable final UUID id) {
        return EntityResponse.from(service.findById(id));
    }

    @GetMapping
    public List<EntityResponse> listByStatus(
            @RequestParam(defaultValue = "PENDING") final EntityStatus status) {
        return service.findByStatus(status).stream()
                .map(EntityResponse::from)
                .toList();
    }

    @PostMapping("/{id}/activate")
    public EntityResponse activate(@PathVariable final UUID id) {
        return EntityResponse.from(service.activate(id));
    }
}
