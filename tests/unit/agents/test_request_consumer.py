"""Unit tests for src/workers/request_consumer.py.

Spec: specs/system/request-pipeline.md
ADR:  ADR-0003 (Async API Strategy), ADR-0011 (HITL/HOTL Model)
REM:  REM-012 (DLQ + safe offset commit), REM-013 (consumer heartbeat)

Kafka is mocked via unittest.mock — no real broker required.
AgentOrchestrator is replaced with AsyncMock so tests run without LLM calls.
All request_ids and request_text values are clearly synthetic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.request_store import InMemoryRequestStore, RequestState
from src.workers.request_consumer import RequestConsumer

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_broker() -> MagicMock:
    broker = MagicMock()
    broker.publish = AsyncMock()
    return broker


def _make_consumer(store=None, broker=None) -> RequestConsumer:
    if store is None:
        store = InMemoryRequestStore()
    if broker is None:
        broker = _make_broker()
    audit = MagicMock()
    audit.log_event = AsyncMock()
    hitl = MagicMock()
    return RequestConsumer(store=store, audit_logger=audit, hitl_gateway=hitl, broker=broker)


def _make_msg(payload: dict, trace_id: str | None = "trace-001") -> SimpleNamespace:
    envelope = {"trace_id": trace_id, "payload": payload}
    return SimpleNamespace(value=json.dumps(envelope).encode())


def _make_state(request_id: str, status: str = "queued") -> RequestState:
    now = datetime.now(UTC)
    return RequestState(
        request_id=request_id,
        status=status,
        created_at=now,
        updated_at=now,
    )


# ── stop() ────────────────────────────────────────────────────────────────────


class TestRequestConsumerStop:
    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self) -> None:
        consumer = _make_consumer()
        consumer._running = True
        await consumer.stop()
        assert consumer._running is False


# ── _handle() — parse errors ──────────────────────────────────────────────────


class TestRequestConsumerHandleParseErrors:
    @pytest.mark.asyncio
    async def test_invalid_json_returns_without_raising(self) -> None:
        consumer = _make_consumer()
        bad_msg = SimpleNamespace(value=b"not-valid-json")
        await consumer._handle(bad_msg)  # must not raise

    @pytest.mark.asyncio
    async def test_missing_request_id_returns_without_storing(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)
        msg = _make_msg({"request_text": "do something"})  # no request_id
        await consumer._handle(msg)
        assert await store.get("any-id") is None

    @pytest.mark.asyncio
    async def test_empty_payload_missing_request_id_skipped(self) -> None:
        consumer = _make_consumer()
        msg = _make_msg({})
        await consumer._handle(msg)  # must not raise

    @pytest.mark.asyncio
    async def test_non_dict_envelope_logs_error_and_returns(self) -> None:
        consumer = _make_consumer()
        bad_msg = SimpleNamespace(value=b'"just a string"')
        await consumer._handle(bad_msg)  # must not raise


# ── _handle() — idempotency ───────────────────────────────────────────────────


class TestRequestConsumerHandleIdempotency:
    @pytest.mark.asyncio
    async def test_non_queued_duplicate_skipped(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        existing = _make_state("req-dup-001", status="completed")
        await store.save(existing)

        msg = _make_msg({"request_id": "req-dup-001", "request_text": "retry"})

        with patch("src.workers.request_consumer.AgentOrchestrator") as MockOrch:
            await consumer._handle(msg)
            MockOrch.assert_not_called()

        result = await store.get("req-dup-001")
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_processing_status_duplicate_skipped(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        await store.save(_make_state("req-proc-001", status="processing"))

        msg = _make_msg({"request_id": "req-proc-001", "request_text": "again"})
        with patch("src.workers.request_consumer.AgentOrchestrator") as MockOrch:
            await consumer._handle(msg)
            MockOrch.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_status_duplicate_skipped(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        await store.save(_make_state("req-fail-001", status="failed"))

        msg = _make_msg({"request_id": "req-fail-001", "request_text": "again"})
        with patch("src.workers.request_consumer.AgentOrchestrator") as MockOrch:
            await consumer._handle(msg)
            MockOrch.assert_not_called()

    @pytest.mark.asyncio
    async def test_queued_status_is_reprocessed(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        await store.save(_make_state("req-queued-001", status="queued"))

        msg = _make_msg({"request_id": "req-queued-001", "request_text": "process me"})

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"output": "done"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        mock_orch.run.assert_called_once()


# ── _handle() — happy path ────────────────────────────────────────────────────


class TestRequestConsumerHandleHappyPath:
    @pytest.mark.asyncio
    async def test_new_request_transitions_to_completed(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"output": "analysis complete"})

        msg = _make_msg({"request_id": "req-new-001", "request_text": "analyse this"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        state = await store.get("req-new-001")
        assert state is not None
        assert state.status == "completed"

    @pytest.mark.asyncio
    async def test_result_dict_stored_directly(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"action": "read_file", "risk_score": 0.2})

        msg = _make_msg({"request_id": "req-dict-001", "request_text": "read file"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        state = await store.get("req-dict-001")
        assert state.result == {"action": "read_file", "risk_score": 0.2}

    @pytest.mark.asyncio
    async def test_non_dict_result_wrapped_in_output_key(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value="plain string result")

        msg = _make_msg({"request_id": "req-str-001", "request_text": "summarise"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        state = await store.get("req-str-001")
        assert state.result == {"output": "plain string result"}

    @pytest.mark.asyncio
    async def test_existing_queued_created_at_preserved(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        original_created_at = datetime(2026, 1, 1, tzinfo=UTC)
        existing = RequestState(
            request_id="req-ts-001",
            status="queued",
            created_at=original_created_at,
            updated_at=original_created_at,
        )
        await store.save(existing)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"output": "done"})

        msg = _make_msg({"request_id": "req-ts-001", "request_text": "go"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        state = await store.get("req-ts-001")
        assert state.created_at == original_created_at

    @pytest.mark.asyncio
    async def test_new_request_created_at_set_to_now(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"output": "ok"})

        before = datetime.now(UTC)
        msg = _make_msg({"request_id": "req-ts-002", "request_text": "go"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        state = await store.get("req-ts-002")
        assert state.created_at >= before

    @pytest.mark.asyncio
    async def test_trace_id_propagated_to_orchestrator(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={})

        msg = _make_msg(
            {"request_id": "req-trace-001", "request_text": "trace this"},
            trace_id="my-trace-xyz",
        )

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        mock_orch.run.assert_called_once_with(
            raw_input={"request_text": "trace this"},
            trace_id="my-trace-xyz",
        )

    @pytest.mark.asyncio
    async def test_request_text_propagated_to_orchestrator(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={})

        msg = _make_msg({"request_id": "req-text-001", "request_text": "specific task text"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        call_kwargs = mock_orch.run.call_args
        assert call_kwargs.kwargs["raw_input"]["request_text"] == "specific task text"

    @pytest.mark.asyncio
    async def test_missing_request_text_defaults_to_empty_string(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={})

        msg = _make_msg({"request_id": "req-notext-001"})  # no request_text

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        call_kwargs = mock_orch.run.call_args
        assert call_kwargs.kwargs["raw_input"]["request_text"] == ""

    @pytest.mark.asyncio
    async def test_success_does_not_publish_to_dlq(self) -> None:
        store = InMemoryRequestStore()
        broker = _make_broker()
        consumer = _make_consumer(store, broker)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"output": "done"})

        msg = _make_msg({"request_id": "req-nodlq-001", "request_text": "ok"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                await consumer._handle(msg)

        broker.publish.assert_not_called()


# ── _handle() — failure path ──────────────────────────────────────────────────


class TestRequestConsumerHandleFailure:
    @pytest.mark.asyncio
    async def test_orchestrator_exception_sets_failed_status(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        msg = _make_msg({"request_id": "req-err-001", "request_text": "will fail"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await consumer._handle(msg)

        state = await store.get("req-err-001")
        assert state.status == "failed"

    @pytest.mark.asyncio
    async def test_orchestrator_exception_stores_error_message(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=ValueError("timeout after 30s"))

        msg = _make_msg({"request_id": "req-err-002", "request_text": "will timeout"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await consumer._handle(msg)

        state = await store.get("req-err-002")
        assert "timeout after 30s" in state.error

    @pytest.mark.asyncio
    async def test_orchestrator_exception_does_not_raise(self) -> None:
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=Exception("unexpected"))

        msg = _make_msg({"request_id": "req-err-003", "request_text": "crash"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await consumer._handle(msg)  # must not propagate


# ── DLQ routing (REM-012) ─────────────────────────────────────────────────────


class TestRequestConsumerDLQ:
    @pytest.mark.asyncio
    async def test_dlq_published_after_exhausted_retries(self) -> None:
        """After max_retries+1 failures the envelope is published to the DLQ topic."""
        store = InMemoryRequestStore()
        broker = _make_broker()
        consumer = _make_consumer(store, broker)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=RuntimeError("permanent failure"))

        msg = _make_msg({"request_id": "req-dlq-001", "request_text": "always fails"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with patch("src.shared.config.settings.kafka_consumer_max_retries", 0):
                        await consumer._handle(msg)

        broker.publish.assert_called_once()
        topic_arg = broker.publish.call_args[0][0]
        assert topic_arg == "domain.request.dlq"

    @pytest.mark.asyncio
    async def test_dlq_envelope_contains_error_field(self) -> None:
        """The DLQ envelope carries a dlq_error field with the failure reason."""
        store = InMemoryRequestStore()
        broker = _make_broker()
        consumer = _make_consumer(store, broker)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=RuntimeError("disk full"))

        msg = _make_msg({"request_id": "req-dlq-002", "request_text": "fail me"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with patch("src.shared.config.settings.kafka_consumer_max_retries", 0):
                        await consumer._handle(msg)

        dlq_payload = broker.publish.call_args[0][1]
        assert "dlq_error" in dlq_payload
        assert "disk full" in dlq_payload["dlq_error"]

    @pytest.mark.asyncio
    async def test_dlq_envelope_keyed_by_request_id(self) -> None:
        """DLQ message is keyed by request_id for partition locality."""
        store = InMemoryRequestStore()
        broker = _make_broker()
        consumer = _make_consumer(store, broker)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=RuntimeError("fail"))

        msg = _make_msg({"request_id": "req-dlq-key-001", "request_text": "x"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with patch("src.shared.config.settings.kafka_consumer_max_retries", 0):
                        await consumer._handle(msg)

        key_arg = broker.publish.call_args[1].get("key") or broker.publish.call_args[0][2]
        assert key_arg == "req-dlq-key-001"

    @pytest.mark.asyncio
    async def test_request_set_to_failed_after_dlq_routing(self) -> None:
        """Request status is 'failed' after DLQ routing, with the error persisted."""
        store = InMemoryRequestStore()
        broker = _make_broker()
        consumer = _make_consumer(store, broker)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=RuntimeError("oops"))

        msg = _make_msg({"request_id": "req-dlq-003", "request_text": "x"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with patch("src.shared.config.settings.kafka_consumer_max_retries", 0):
                        await consumer._handle(msg)

        state = await store.get("req-dlq-003")
        assert state.status == "failed"
        assert "oops" in state.error

    @pytest.mark.asyncio
    async def test_dlq_publish_failure_does_not_raise(self) -> None:
        """If the DLQ broker publish itself fails, _handle must still return without raising."""
        store = InMemoryRequestStore()
        broker = _make_broker()
        broker.publish = AsyncMock(side_effect=RuntimeError("broker down"))
        consumer = _make_consumer(store, broker)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=RuntimeError("primary failure"))

        msg = _make_msg({"request_id": "req-dlq-004", "request_text": "x"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with patch("src.shared.config.settings.kafka_consumer_max_retries", 0):
                        await consumer._handle(msg)  # must not raise

        state = await store.get("req-dlq-004")
        assert state.status == "failed"


# ── Retry behaviour (REM-012) ─────────────────────────────────────────────────


class TestRequestConsumerRetry:
    @pytest.mark.asyncio
    async def test_transient_failure_retried_before_dlq(self) -> None:
        """Orchestrator fails twice then succeeds — no DLQ publish, status completed."""
        store = InMemoryRequestStore()
        broker = _make_broker()
        consumer = _make_consumer(store, broker)

        call_count = 0

        async def flaky(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient")
            return {"output": "recovered"}

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=flaky)

        msg = _make_msg({"request_id": "req-retry-001", "request_text": "flaky"})

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with patch("src.shared.config.settings.kafka_consumer_max_retries", 3):
                        await consumer._handle(msg)

        broker.publish.assert_not_called()
        state = await store.get("req-retry-001")
        assert state.status == "completed"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_uses_exponential_backoff(self) -> None:
        """asyncio.sleep is called with increasing delays between attempts."""
        store = InMemoryRequestStore()
        consumer = _make_consumer(store)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=RuntimeError("fail"))

        msg = _make_msg({"request_id": "req-backoff-001", "request_text": "x"})
        sleep_calls: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch):
            with patch("src.workers.request_consumer.AnthropicLLMClient"):
                with patch("asyncio.sleep", side_effect=capture_sleep):
                    with patch("src.shared.config.settings.kafka_consumer_max_retries", 2):
                        with patch(
                            "src.shared.config.settings.kafka_consumer_retry_backoff_seconds",
                            1.0,
                        ):
                            await consumer._handle(msg)

        # 2 retries → 2 sleep calls with delays 1.0 and 2.0
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(2.0)


# ── run() — Kafka lifecycle ────────────────────────────────────────────────────


async def _async_messages(*msgs):
    """Async generator that yields the given messages then stops."""
    for m in msgs:
        yield m


def _kafka_mock(*msgs):
    """Return a MagicMock that behaves like an AIOKafkaConsumer."""
    mock = MagicMock()
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.commit = AsyncMock()
    mock.__aiter__ = lambda self: _async_messages(*msgs)
    return mock


def _make_kafka_msg(
    payload: dict, topic: str = "domain.request.created", partition: int = 0, offset: int = 0
):
    """Simulate a real Kafka message with topic/partition/offset metadata."""
    envelope = {"trace_id": "trace-run", "payload": payload}
    msg = SimpleNamespace(
        value=json.dumps(envelope).encode(),
        topic=topic,
        partition=partition,
        offset=offset,
    )
    return msg


class TestRequestConsumerRun:
    @pytest.mark.asyncio
    async def test_run_starts_and_stops_kafka_consumer(self) -> None:
        consumer = _make_consumer()
        kafka = _kafka_mock()

        with patch("aiokafka.AIOKafkaConsumer", return_value=kafka):
            with patch("aiokafka.TopicPartition"):
                await consumer.run()

        kafka.start.assert_called_once()
        kafka.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_subscribes_to_correct_topic(self) -> None:
        consumer = _make_consumer()
        kafka = _kafka_mock()

        with patch("aiokafka.AIOKafkaConsumer", return_value=kafka) as MockKafka:
            with patch("aiokafka.TopicPartition"):
                await consumer.run()

        args, _ = MockKafka.call_args
        assert args[0] == "domain.request.created"

    @pytest.mark.asyncio
    async def test_run_uses_manual_offset_commit(self) -> None:
        """enable_auto_commit must be False — offset committed manually (REM-012)."""
        consumer = _make_consumer()
        kafka = _kafka_mock()

        with patch("aiokafka.AIOKafkaConsumer", return_value=kafka) as MockKafka:
            with patch("aiokafka.TopicPartition"):
                await consumer.run()

        _, kwargs = MockKafka.call_args
        assert kwargs.get("enable_auto_commit") is False

    @pytest.mark.asyncio
    async def test_run_commits_offset_after_each_message(self) -> None:
        """consumer.commit() is called once per processed message (REM-012)."""
        consumer = _make_consumer()
        msg = _make_kafka_msg({"request_id": "req-commit-001", "request_text": "x"})
        kafka = _kafka_mock(msg)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"output": "done"})

        with patch("aiokafka.AIOKafkaConsumer", return_value=kafka):
            with patch("aiokafka.TopicPartition", return_value="tp-stub"):
                with patch(
                    "src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch
                ):
                    with patch("src.workers.request_consumer.AnthropicLLMClient"):
                        await consumer.run()

        kafka.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_stops_consumer_even_if_handle_raises(self) -> None:
        consumer = _make_consumer()
        bad_msg = SimpleNamespace(
            value=b"not-json", topic="domain.request.created", partition=0, offset=0
        )
        kafka = _kafka_mock(bad_msg)

        with patch("aiokafka.AIOKafkaConsumer", return_value=kafka):
            with patch("aiokafka.TopicPartition"):
                await consumer.run()

        kafka.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_breaks_loop_when_stop_called(self) -> None:
        """stop() mid-loop: first message handled, second skipped."""
        consumer = _make_consumer()
        processed = []

        async def _handle_and_stop(msg):
            processed.append(msg)
            await consumer.stop()  # sets _running = False after first message

        consumer._handle = _handle_and_stop

        msg1 = SimpleNamespace(
            value=json.dumps(
                {"trace_id": None, "payload": {"request_id": "r1", "request_text": "first"}}
            ).encode(),
            topic="domain.request.created",
            partition=0,
            offset=0,
        )
        msg2 = SimpleNamespace(
            value=json.dumps(
                {"trace_id": None, "payload": {"request_id": "r2", "request_text": "second"}}
            ).encode(),
            topic="domain.request.created",
            partition=0,
            offset=1,
        )
        kafka = _kafka_mock(msg1, msg2)

        with patch("aiokafka.AIOKafkaConsumer", return_value=kafka):
            with patch("aiokafka.TopicPartition"):
                await consumer.run()

        assert len(processed) == 1
        assert processed[0] is msg1


# ── Consumer heartbeat (REM-013) ─────────────────────────────────────────────


class TestRequestConsumerHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_gauge_updated_after_successful_message(self) -> None:
        """CONSUMER_HEARTBEAT_TIMESTAMP is set to a non-zero epoch after a commit."""
        consumer = _make_consumer()
        msg = _make_kafka_msg({"request_id": "req-hb-001", "request_text": "x"})
        kafka = _kafka_mock(msg)

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"output": "ok"})

        with patch("aiokafka.AIOKafkaConsumer", return_value=kafka):
            with patch("aiokafka.TopicPartition", return_value="tp-stub"):
                with patch(
                    "src.workers.request_consumer.AgentOrchestrator", return_value=mock_orch
                ):
                    with patch("src.workers.request_consumer.AnthropicLLMClient"):
                        from src.observability.metrics import CONSUMER_HEARTBEAT_TIMESTAMP
                        from src.shared.config import settings

                        before = __import__("time").time()
                        await consumer.run()
                        after = __import__("time").time()

        # The gauge value should be between before and after
        gauge_value = CONSUMER_HEARTBEAT_TIMESTAMP.labels(
            settings.kafka_consumer_group
        )._value.get()
        assert before <= gauge_value <= after
