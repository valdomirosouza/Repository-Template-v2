package com.yourorg.domainservice.infra.kafka;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;

@ExtendWith(MockitoExtension.class)
class DomainEventProducerTest {

    private static final String CREATED_TOPIC = "domain.entity.created.v1";
    private static final String UPDATED_TOPIC = "domain.entity.updated.v1";

    @Mock
    private KafkaTemplate<String, String> kafkaTemplate;

    private DomainEventProducer producer;

    @BeforeEach
    void setUp() {
        producer = new DomainEventProducer(kafkaTemplate, CREATED_TOPIC, UPDATED_TOPIC);
    }

    @Test
    void publishCreated_sendsCreatedPayloadToCreatedTopic() {
        when(kafkaTemplate.send(anyString(), anyString(), anyString())).thenReturn(completed());

        producer.publishCreated("e1", "widget");

        ArgumentCaptor<String> payload = ArgumentCaptor.forClass(String.class);
        verify(kafkaTemplate).send(eq(CREATED_TOPIC), eq("e1"), payload.capture());
        assertThat(payload.getValue()).contains("\"event\":\"created\"").contains("widget");
    }

    @Test
    void publishUpdated_sendsUpdatedPayloadToUpdatedTopic() {
        when(kafkaTemplate.send(anyString(), anyString(), anyString())).thenReturn(completed());

        producer.publishUpdated("e2", "ACTIVE");

        ArgumentCaptor<String> payload = ArgumentCaptor.forClass(String.class);
        verify(kafkaTemplate).send(eq(UPDATED_TOPIC), eq("e2"), payload.capture());
        assertThat(payload.getValue()).contains("\"event\":\"updated\"").contains("ACTIVE");
    }

    @Test
    void publishCreated_failedSend_isHandledWithoutThrowing() {
        when(kafkaTemplate.send(anyString(), anyString(), anyString())).thenReturn(failed());

        assertThatNoException().isThrownBy(() -> producer.publishCreated("e1", "widget"));
    }

    @Test
    void publishUpdated_failedSend_isHandledWithoutThrowing() {
        when(kafkaTemplate.send(anyString(), anyString(), anyString())).thenReturn(failed());

        assertThatNoException().isThrownBy(() -> producer.publishUpdated("e2", "ACTIVE"));
    }

    private static CompletableFuture<SendResult<String, String>> completed() {
        return CompletableFuture.completedFuture(null);
    }

    private static CompletableFuture<SendResult<String, String>> failed() {
        return CompletableFuture.failedFuture(new IllegalStateException("kafka unavailable"));
    }
}
