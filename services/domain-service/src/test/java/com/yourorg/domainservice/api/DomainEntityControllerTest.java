package com.yourorg.domainservice.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.yourorg.domainservice.domain.DomainEntity;
import com.yourorg.domainservice.domain.DomainEntityService;
import com.yourorg.domainservice.domain.EntityNotFoundException;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(DomainEntityController.class)
class DomainEntityControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private DomainEntityService service;

    @Test
    void create_returnsCreated() throws Exception {
        DomainEntity entity = new DomainEntity("my-entity", "{}");
        when(service.create(anyString(), anyString())).thenReturn(entity);

        mockMvc.perform(post("/v1/entities")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"my-entity\",\"payload\":\"{}\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.name").value("my-entity"))
                .andExpect(jsonPath("$.status").value("PENDING"));
    }

    @Test
    void create_withBlankName_returnsBadRequest() throws Exception {
        mockMvc.perform(post("/v1/entities")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void getById_notFound_returns404() throws Exception {
        UUID id = UUID.randomUUID();
        when(service.findById(any())).thenThrow(new EntityNotFoundException(id));

        mockMvc.perform(get("/v1/entities/" + id))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("not_found"));
    }

    @Test
    void listByStatus_returnsEntities() throws Exception {
        when(service.findByStatus(any())).thenReturn(List.of());

        mockMvc.perform(get("/v1/entities").param("status", "PENDING"))
                .andExpect(status().isOk());
    }
}
