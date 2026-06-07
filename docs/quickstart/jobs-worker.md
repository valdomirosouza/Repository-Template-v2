# Quickstart — Scheduled Jobs & Batch Workers

> **Stack:** Python 3.13 · APScheduler or Celery · asyncpg · aiokafka · OpenTelemetry
> **Service types:** Nightly batch processor, scheduled cleanup job, data pipeline worker
> **Read first:** [docs/quickstart/README.md](README.md) for shared governance rules.

---

## Prerequisites

| Tool             | Version | Install                                                                 |
| ---------------- | ------- | ----------------------------------------------------------------------- |
| Python           | 3.13+   | [python.org](https://www.python.org/downloads/) or `pyenv install 3.13` |
| uv               | latest  | `curl -LsSf https://astral.sh/uv/install.sh \| sh`                      |
| Docker & Compose | 24+     | [docker.com](https://www.docker.com/products/docker-desktop/)           |
| make             | any     | pre-installed on macOS/Linux                                            |

---

## Which files are yours

```
src/jobs/
├── <your-job>/
│   ├── __init__.py
│   ├── job.py          ← main job logic — implements BaseJob interface
│   ├── config.py       ← job-specific config (extends shared settings)
│   └── README.md       ← job purpose, schedule, SLA, owner
└── scheduler.py        ← APScheduler bootstrap (register your job here)

tests/
├── unit/jobs/<your-job>/
└── integration/jobs/<your-job>/
```

**Files you do NOT own (shared contracts — read-only):**

```
docs/api/asyncapi/    ← Kafka contract — if your job publishes events, match this spec
infrastructure/message-broker/schema-registry/avro/  ← Avro schemas for published events
```

---

## Setup

```bash
# 1. Install Python dependencies
uv sync

# 2. Copy and configure environment
cp .env.example .env
# Required fields for jobs:
#   DATABASE_URL       postgresql+asyncpg://user:password@localhost:5432/dbname
#   REDIS_URL          redis://localhost:6379/0  (for Celery broker if used)
#   JOB_SCHEDULE_CRON  0 2 * * *                (default: 2am daily)

# 3. Start shared infrastructure
docker compose up -d

# 4. Run database migrations (jobs share the main DB)
uv run alembic upgrade head

# 5. Confirm baseline is green
make test-python
```

---

## Daily workflow

```bash
make test-python          # unit + integration tests with coverage
make test-unit-python     # unit only (fast, no Docker required)
make lint-python          # ruff + mypy + detect-secrets
make format-python        # auto-format with ruff
make run-job JOB=<name>   # run a single job execution immediately (for manual testing)
```

---

## Implementing a job

All jobs implement the `BaseJob` interface:

```python
from src.jobs.base import BaseJob, JobResult
from src.shared.config import settings
from src.observability.logger import get_logger

logger = get_logger("my-batch-job")

class MyBatchJob(BaseJob):
    name = "my-batch-job"
    schedule = "0 2 * * *"  # cron expression — document in job README.md

    async def run(self) -> JobResult:
        logger.info("starting batch job run")
        processed = 0
        failed = 0

        async for batch in self._fetch_batches():
            try:
                await self._process_batch(batch)
                processed += len(batch)
            except Exception as exc:
                logger.error("batch processing failed",
                    error=str(exc), batch_size=len(batch))
                failed += len(batch)

        return JobResult(processed=processed, failed=failed)
```

### Register your job

```python
# src/jobs/scheduler.py
from src.jobs.my_batch_job.job import MyBatchJob

scheduler.add_job(
    MyBatchJob().run,
    trigger=CronTrigger.from_crontab(MyBatchJob.schedule),
    id=MyBatchJob.name,
    replace_existing=True,
    misfire_grace_time=300,  # 5-minute grace window for missed triggers
)
```

---

## Key architectural patterns

### Config — never hardcode values

```python
from src.shared.config import settings

# Job-specific settings extend the shared settings
class MyJobConfig(settings.__class__):
    job_batch_size: int = 500
    job_max_retries: int = 3
```

### PII — mask before logging and publishing

```python
from src.guardrails.pii_filter import mask_dict

# Before any log write:
safe_record = mask_dict(raw_record)
logger.info("processing record", **safe_record)

# Before publishing to Kafka:
safe_event = mask_dict(event_payload)
await producer.send(topic, value=safe_event)
```

### Resilience — idempotency and checkpointing

Jobs **must** be idempotent — they must produce the same result if run multiple times:

```python
async def _process_batch(self, batch: list[Record]) -> None:
    async with db.transaction():
        for record in batch:
            # Use INSERT ... ON CONFLICT DO NOTHING or upsert
            await db.execute(
                "INSERT INTO processed_records (id, processed_at) "
                "VALUES ($1, NOW()) ON CONFLICT (id) DO NOTHING",
                record.id,
            )
```

Checkpoint progress so a restart resumes from the last safe point — never re-processes completed work.

### Agent actions — always route through HITL

If your job triggers agent actions with real-world effects:

```python
from src.agents.hitl_gateway import HITLGateway, HITLRequest

# Do NOT bypass HITL even in batch context
await hitl_gateway.submit(HITLRequest(
    action="bulk-email-send",
    payload=safe_payload,
    risk_score=0.8,
))
```

### Structured logging with job context

```python
logger = get_logger("my-batch-job")

# Always include job_run_id for correlation
job_run_id = str(uuid.uuid4())
logger.info("job started", job_run_id=job_run_id, schedule=self.schedule)
# ... job work ...
logger.info("job completed",
    job_run_id=job_run_id,
    processed=result.processed,
    failed=result.failed,
    duration_seconds=elapsed)
```

---

## Observability

Emit Golden Signals for every job execution:

```python
from src.observability.metrics import JOB_RUNS_COUNTER, JOB_DURATION

# Record outcome
JOB_RUNS_COUNTER.labels(job=self.name, outcome="success").inc()
JOB_DURATION.labels(job=self.name).observe(elapsed_seconds)
```

Set up an alert in `infrastructure/monitoring/prometheus/rules/` if the job
misses its SLA window or has a failure rate above 1%.

---

## Testing conventions

```python
# Unit test — mock DB and external calls
@pytest.mark.unit
async def test_my_job_processes_batch(monkeypatch):
    job = MyBatchJob()
    monkeypatch.setattr(job, "_fetch_batches", mock_batches)
    result = await job.run()
    assert result.processed == 10
    assert result.failed == 0

# Integration test — real DB via docker-compose.test.yml
@pytest.mark.integration
async def test_my_job_idempotent():
    job = MyBatchJob()
    result1 = await job.run()
    result2 = await job.run()
    # Second run should process 0 records (already done)
    assert result2.processed == 0
```

Coverage must be ≥ 80% before merge. CI enforces this.

---

## Job documentation requirements

Every job **must** have a `README.md` in its directory covering:

| Section      | Required content                                          |
| ------------ | --------------------------------------------------------- |
| Purpose      | What business problem this job solves                     |
| Schedule     | Cron expression + timezone + SLA (must complete within X) |
| Owner        | Team and on-call rotation                                 |
| Inputs       | Data sources (tables, topics, external APIs)              |
| Outputs      | Side effects (DB writes, Kafka events, emails)            |
| Failure mode | What happens if the job fails — manual recovery steps     |
| Monitoring   | Alert name + Grafana dashboard link                       |

---

## Deployment

Jobs run as Kubernetes CronJobs:

```bash
# Build image (same image as the API — jobs are a separate entry point)
make build-python

# Apply CronJob manifest
kubectl apply -f infrastructure/k8s/cronjob-<your-job>.yaml

# Trigger a manual run for testing
kubectl create job --from=cronjob/<your-job> <your-job>-manual-$(date +%s)

# Check logs
kubectl logs -l job-name=<your-job> --tail=100
```

---

## Key ADRs for jobs and worker developers

| ADR                                                       | Why it matters to you                           |
| --------------------------------------------------------- | ----------------------------------------------- |
| [ADR-0002](../adr/ADR-0002-technology-stack-selection.md) | Python rationale for batch/job workloads        |
| [ADR-0003](../adr/ADR-0003-async-api-strategy.md)         | When jobs should publish Kafka events vs REST   |
| [ADR-0013](../adr/ADR-0013-data-retention-policy.md)      | Data retention rules — jobs that purge old data |
| [ADR-0011](../adr/ADR-0011-hitl-hotl-model.md)            | HITL requirement even in batch/autonomous flows |
