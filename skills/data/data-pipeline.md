# Skill — Data Pipeline

**Owner:** Tech Lead | **Status:** Active | **Last updated:** 2026-06-05
**Issue:** #10

Activate this skill for any data science, analytics, or data engineering workflow —
ingestion, transformation, validation, or output.

---

## 1. Ingestion Patterns

### Pandas (small-to-medium datasets, < 1 GB)

```python
import pandas as pd
from src.observability.logger import get_logger

log = get_logger("pipeline.ingest")

def read_csv_safe(path: str, schema: dict) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=schema, parse_dates=["created_at"])
    log.info("ingested", rows=len(df), path=path)
    return df
```

- Always specify `dtype` to prevent silent type coercion
- Always log row count and source path for auditability
- Use `chunksize=` for files > 100 MB

### Polars (large datasets, lazy evaluation)

```python
import polars as pl

def read_parquet_lazy(path: str) -> pl.LazyFrame:
    return pl.scan_parquet(path)  # no I/O until .collect()
```

- Prefer `LazyFrame` over `DataFrame` — defer `.collect()` to the last step
- Use `.filter()` before `.collect()` to push predicates to the scan

---

## 2. PII Classification for Analytical Datasets

Before processing any dataset, classify each column using the L1–L4 scale
(`docs/privacy/pii-inventory.md`):

| Column type               | Level | Required treatment                       |
| ------------------------- | ----- | ---------------------------------------- |
| Name, email, phone        | L1    | Mask or pseudonymise before analysis     |
| ID that links to a person | L2    | Hash with HMAC-SHA256 (stable pseudonym) |
| Demographic aggregate     | L3    | k-anonymity ≥ 5 before output            |
| Fully anonymised          | L4    | No restriction                           |

```python
from src.guardrails.pii_filter import mask_dict

# Mask before writing to any log or output file
safe_row = mask_dict(row)
```

Never write L1/L2 columns to:

- Log files
- Vector stores
- Analytical output shared outside the organisation
- Test fixtures (use `faker` instead)

---

## 3. OTel Instrumentation for Pipelines

Instrument every pipeline stage with a span and record row-count metrics:

```python
from opentelemetry import trace
from src.observability.metrics import record_session_task

tracer = trace.get_tracer("data-pipeline")

def transform_stage(df: pd.DataFrame, stage_name: str) -> pd.DataFrame:
    with tracer.start_as_current_span(f"pipeline.{stage_name}") as span:
        result = _apply_transform(df)
        span.set_attribute("rows.in", len(df))
        span.set_attribute("rows.out", len(result))
        record_session_task(task_type="planned", outcome="completed")
        return result
```

Minimum instrumentation per pipeline:

| Point                | What to record                                             |
| -------------------- | ---------------------------------------------------------- |
| Source read          | `rows_read`, `source_path`, `schema_version`               |
| Each transform stage | `rows_in`, `rows_out`, `stage_name`                        |
| Validation           | `rows_valid`, `rows_rejected`, `rejection_reason` (no PII) |
| Output write         | `rows_written`, `destination`, `file_size_bytes`           |

---

## 4. Output Validation and Schema Contracts

Every pipeline output must be validated before writing:

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class PipelineOutputSchema:
    required_columns: list[str]
    non_null_columns: list[str]
    min_rows: int = 1

def validate_output(df: pd.DataFrame, schema: PipelineOutputSchema) -> None:
    missing = [c for c in schema.required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Output missing required columns: {missing}")

    nulls = [c for c in schema.non_null_columns if df[c].isna().any()]
    if nulls:
        raise ValueError(f"Unexpected nulls in columns: {nulls}")

    if len(df) < schema.min_rows:
        raise ValueError(f"Output has {len(df)} rows; expected ≥ {schema.min_rows}")
```

- Define the schema contract in `specs/data/<pipeline-name>.md` before implementation
- Validation failures must raise — never silently write partial output
- Log validation summary (row count, null counts) but never log cell values that may contain PII

---

## 5. Testing Data Pipelines

```python
# tests/unit/data/test_<pipeline>.py
import pandas as pd
from faker import Faker

fake = Faker("pt_BR")  # or "en_US"

def make_fixture(n: int = 100) -> pd.DataFrame:
    """Synthetic dataset — never use real data in tests."""
    return pd.DataFrame({
        "name": [fake.name() for _ in range(n)],
        "email": [fake.email() for _ in range(n)],
        "amount": fake.random_elements([10.0, 50.0, 100.0], length=n),
    })
```

Test requirements:

- All fixtures use `faker` — never real names, emails, or IDs
- Test at the stage boundary, not just end-to-end
- Include a test for schema validation failure (assert `ValueError` raised)
- Mark with `@pytest.mark.unit` — no I/O, no external services

---

## 6. Related

- `skills/privacy/pii.md` — Full PII classification and masking rules
- `docs/privacy/pii-inventory.md` — L1–L4 column registry
- `specs/automation/automation-spec-template.md` — Spec template for data automations
- `src/observability/metrics.py` — `agent_session_tasks_total`, `agent_cycle_time_seconds`
