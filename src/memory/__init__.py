"""Agent persistent memory — three-layer recall system.

Spec: specs/ai/agent-memory.md
ADR:  ADR-0017 (Agent Memory Architecture)
DPIA: docs/privacy/dpia/dpia-agent-memory.md — DPO sign-off required before merge.

Layers:
  VectorStore      — semantic search over specs, ADRs, sprint outcomes (pgvector)
  SessionMemory    — short-term key-value cache per session (Redis, 24 h TTL)
  BugHistoryStore  — HITL rejection patterns for agent recall (pgvector)

Privacy invariant: pii_filter.mask_text() MUST be applied before every write.
"""
