# ADR-0068 — Golden-Signal Extraction Rules, Window Semantics & Key Grammar

**Status:** Proposed
**Date:** 2026-06-11
**Authors:** Valdomiro Souza
**Reviewers:** Tech Lead
**Relates to:** [ADR-0066](ADR-0066-spec-lgs-001-runtime-stack-java-spring-boot.md) (Java runtime), [ADR-0067](ADR-0067-redis-as-timeseries-store.md) (store), [ADR-0012](ADR-0012-pii-masking-strategy.md) (PII)
**Scope:** `SPEC-LGS-001` only — **resolves source-spec §15-Q3** (exact saturation threshold + unit + scope) and pins §9.2 (key convention) and §13 (window-boundary reproducibility).

---

## Context

The source spec (§10) names the four Golden Signals and their derivation in prose, but leaves three
things under-specified that the ingestion service and the analytics service **must agree on
byte-for-byte** or they will read/write divergent data: (a) the saturation threshold and whether it
is per-path or global (§15-Q3, flagged as a risk in §13 "saturation as a `bytes_sent` proxy"),
(b) the window boundary semantics so percentiles are reproducible (§13 "window boundaries can split
bursty traffic"), and (c) the exact Redis key grammar (§9.2 says "define once… so both services
read/write identically"). This ADR fixes all three concretely.

## Decision

### 1. Signal extraction (per log entry → `(path, window)`)

| Signal     | Rule (exact)                                                                                                                          |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Traffic    | `count += 1` for the entry's `(path, window, bucket)`.                                                                                |
| Latency    | append `response_time_ms` (float) to the bucket's latency sample sorted set; P50/P95/P99 by rank interpolation at query time (FR-07). |
| Error      | `errors += 1` **iff** `status_code >= 400`; `error_rate = errors / count`.                                                            |
| Saturation | sample is "saturated" **iff** `bytes_sent >= SATURATION_BYTES_THRESHOLD`; `saturation_pct = saturated / count * 100`.                 |

### 2. Saturation threshold (resolves §15-Q3)

- **Proxy:** `bytes_sent >= SATURATION_BYTES_THRESHOLD`. Comparison is `>=` (strict-or-equal at the
  boundary counts as saturated).
- **Default:** `1048576` bytes = **1 MiB**, supplied via env `SATURATION_BYTES_THRESHOLD` (NFR-04).
- **Scope:** **per-path with a global default.** An optional per-path override env
  `SATURATION_BYTES_THRESHOLD__<path>` (path URL-encoded) takes precedence; absent that, the global
  default applies. This makes the proxy tunable for paths that legitimately return large payloads.
- **Honesty flag (source-spec §13):** this is an approximation of true resource saturation;
  `_governance.data_classification` and the saturation field carry no claim of exact resource use.

### 3. Window semantics (resolves §13 reproducibility)

- Two windows: **1m** (60s) and **5m** (300s), both **epoch-aligned**: `bucket_start =
floor(epoch_seconds / W) * W`.
- Boundaries are **LEFT-closed / RIGHT-open**: a sample with timestamp `t` belongs to bucket `b`
  iff `bucket_start <= t < bucket_start + W`. A sample at exactly `bucket_start + W` belongs to the
  **next** bucket. This single rule makes bucketing deterministic and reproducible across both
  services and removes the §13 "split bursty traffic" ambiguity.
- `epoch_bucket` in the key is the integer `bucket_start` (epoch seconds).

### 4. Key grammar (resolves §9.2 — both services use this verbatim)

```
gs:{signal}:{path}:{window}:{epoch_bucket}            # Redis hash: count, sum, min, max, errors, saturated
gs:{signal}:{path}:{window}:{epoch_bucket}:samples    # Redis sorted set: latency samples (score = value)
gs:paths                                              # Redis set: every tracked {path} (FR-08)
```

- `{signal}` ∈ `traffic|latency|error|saturation`; `{window}` ∈ `1m|5m`; `{epoch_bucket}` = integer.
- **`{path}` MUST be percent-encoded before insertion into any key.** This is the key-injection
  defence (CLAUDE.md §3.2): a raw path containing `:`, `*`, whitespace, newline, or a literal `gs:`
  prefix can otherwise forge or collide with another path's keys. Encoding makes the `:` field
  separators unambiguous and the path opaque. The same encoding is applied identically on write
  (ingestion/worker) and read (analytics), and is reversed only for the FR-08 `paths` listing.
- **Encoding standard (corrected — verified across THREE language re-implementations).** "URL-encoded
  (RFC 3986)" is too loose: every language's "URL encoder" disagrees. Verified divergence on the
  same path:

  | Encoder                                                      | space | `*`             | `& @ $ =`       |
  | ------------------------------------------------------------ | ----- | --------------- | --------------- |
  | Java `java.net.URLEncoder` (form-encoding, **not** RFC 3986) | `+`   | left raw        | percent-encoded |
  | JS `encodeURIComponent`                                      | `%20` | left raw        | percent-encoded |
  | Go `url.PathEscape`                                          | `%20` | percent-encoded | **left raw**    |

  So three conformant "URL-encoders" produce **three different keys** for the same path. Within a
  single service this is harmless (one encoder for both write and read ⇒ self-consistent keys, and
  the injection defence holds since `:` is always encoded). But the "byte-for-byte cross-language"
  guarantee is **false in three directions**. **Therefore the canonical encoder is mandated
  explicitly:** percent-encode **every** byte outside the RFC 3986 `unreserved` set
  (`A–Z a–z 0–9 - _ . ~`), upper-case hex, UTF-8 — i.e. the `encodeURIComponent` algorithm. A
  polyglot deployment sharing one Redis MUST use exactly this (Java: a custom RFC-3986 encoder, not
  `URLEncoder`; Go: `url.QueryEscape` is also wrong — hand-roll or post-process). Pin this, not a
  vague "URL-encoded".

## Consequences

### Positive

- Ingestion and analytics are guaranteed key-compatible — no silent read/write drift (§9.2 intent).
- Window math is reproducible: the same log replay yields identical buckets and percentiles (§13).
- URL-encoding closes the key-injection vector at the data-layer boundary (threat-model T/E entries).
- Saturation is tunable per noisy path without code change (NFR-04).

### Negative / Trade-offs

- `>=` saturation and the `bytes_sent` proxy remain approximations (source-spec §13) — documented,
  not hidden; surfaced honestly in responses.
- LEFT-closed/RIGHT-open means a burst straddling a boundary is split across buckets by design; this
  is accepted as the deterministic choice rather than a sliding window (which would be costlier).
- URL-encoding adds an encode/decode step on every key op; negligible vs Redis round-trip.

### Neutral

- Percentile interpolation method lives in the Java `PercentileCalculator` (feature-spec §1.2), not here.

## Alternatives Considered

- **Global-only saturation threshold** — simpler, but can't accommodate large-payload paths; rejected
  in favour of per-path-with-default.
- **Sliding/overlapping windows** — better burst smoothing, higher storage + compute; rejected for
  initial scope; epoch-aligned fixed windows are reproducible and cheap.
- **Raw (un-encoded) `{path}` in keys** — rejected: opens the key-injection vector in §3.2.
- **`>` (strict) saturation comparison** — rejected for symmetry with the documented `>=` definition;
  the boundary case is explicitly "at or above threshold = saturated."

## References

- `specs/system/SPEC-LGS-001-log-based-golden-signals.md` §10, §9.2, §13, §15-Q3
- `reports/CODE-DELIVERY-SPEC-LGS-001/specs/feature-spec.md` §1.2, §3, §5
- ADR-0067 (store + key usage), ADR-0012 (PII masking, applied before extraction)
