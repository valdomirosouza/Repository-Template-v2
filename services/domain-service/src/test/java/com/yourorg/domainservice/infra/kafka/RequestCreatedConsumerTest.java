package com.yourorg.domainservice.infra.kafka;

import static org.assertj.core.api.Assertions.assertThatNoException;

import com.yourorg.domainservice.domain.DomainEntityService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RequestCreatedConsumerTest {

    @Mock
    private DomainEntityService entityService;

    @Test
    void onRequestCreated_handlesMessageWithoutThrowing() {
        RequestCreatedConsumer consumer = new RequestCreatedConsumer(entityService);

        assertThatNoException().isThrownBy(() -> consumer.onRequestCreated("{\"request\":\"x\"}"));
    }
}
