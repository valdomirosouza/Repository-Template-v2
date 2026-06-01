# Team Topology

> **Status:** Active · **Version:** 1.0 · **Last updated:** 2026-05-31
> **Owner:** Tech Lead
> **Spec:** TT-001 · **Related:** `docs/governance/raci-matrix.md` · `.github/CODEOWNERS` · `services.yaml`

This document defines how engineering teams are structured, how they interact, and which team owns which part of this system. Based on the Team Topologies framework (Skelton & Pais, 2019).

---

## 1. Team Types

Four fundamental team types. Every team in your organization maps to exactly one.

### 1.1 Stream-Aligned Team

Aligned to a flow of business value (a product, user journey, or service domain). Owns its services end-to-end: design → build → run.

**Characteristics:**

- Full-stack capability (or cross-functional membership)
- Owns SLOs for its services
- Deploys independently without waiting for other teams
- Closest to the customer/user

**Example in this monorepo:** A team owning `services/domain-service/` and the corresponding frontend feature in `frontend/`.

### 1.2 Enabling Team

Helps stream-aligned teams adopt new capabilities or practices. Does not own production services long-term — teaches, then steps back.

**Characteristics:**

- Deep expertise in a specific domain (e.g., observability, security, AI governance)
- Works with stream-aligned teams for a bounded period (2–4 weeks)
- Produces templates, runbooks, and tooling that stream teams self-serve

**Example in this monorepo:** The team that built and maintains `skills/`, `docs/runbooks/`, and the AI agents extension.

### 1.3 Platform Team

Provides a curated, self-service internal platform that reduces cognitive load for stream-aligned teams. Treats stream-aligned teams as customers.

**Characteristics:**

- Owns shared infrastructure: CI/CD, observability stack, K8s clusters, feature flags
- Provides stable, versioned APIs (not ad-hoc help)
- SLO on platform reliability (platform downtime = all stream teams blocked)

**Example in this monorepo:** The team owning `.github/workflows/`, `infrastructure/`, and `Makefile` targets.

### 1.4 Complicated-Subsystem Team

Owns a component that requires deep specialist knowledge (e.g., ML model serving, cryptographic key management, custom Kafka connectors). Exists to prevent that complexity from leaking into stream-aligned teams.

**Characteristics:**

- Small; highly specialized
- Provides a well-defined interface to other teams
- Does NOT own user-facing features

**Example in this monorepo:** A team owning `src/agents/` (AI/HITL subsystem) when it exceeds stream-team cognitive capacity.

---

## 2. Interaction Modes

Three modes govern how any two teams interact at any point in time.

| Mode               | Description                                                                                           | Duration               | Trigger                                                          |
| ------------------ | ----------------------------------------------------------------------------------------------------- | ---------------------- | ---------------------------------------------------------------- |
| **Collaboration**  | Two teams work jointly on a problem with high uncertainty. High bandwidth; daily contact.             | Time-boxed (2–4 weeks) | New capability, architectural decision, or novel integration     |
| **X-as-a-Service** | One team consumes a well-defined service from another with minimal interaction. Low bandwidth; async. | Ongoing                | Platform or complicated-subsystem is mature enough to self-serve |
| **Facilitating**   | An enabling team coaches a stream-aligned team to improve capability. Moderate bandwidth.             | Time-boxed (1–4 weeks) | Skill gap identified; new tooling adoption                       |

> **Anti-pattern:** Collaboration that never transitions to X-as-a-Service signals unclear interfaces. Set a deadline to reach X-as-a-Service for every collaboration.

---

## 3. Squad Ownership Map

Map each top-level path in the monorepo to the team that owns it. Update when ownership changes; sync with `.github/CODEOWNERS`.

| Path                       | Owning Team                     | Team Type             | On-Call                     |
| -------------------------- | ------------------------------- | --------------------- | --------------------------- |
| `src/api/`                 | Stream Team — API               | Stream-Aligned        | `@your-org/stream-api`      |
| `src/agents/`              | Complicated-Subsystem Team — AI | Complicated-Subsystem | `@your-org/ai-team`         |
| `src/guardrails/`          | Complicated-Subsystem Team — AI | Complicated-Subsystem | `@your-org/ai-team`         |
| `src/workers/`             | Stream Team — API               | Stream-Aligned        | `@your-org/stream-api`      |
| `src/memory/`              | Complicated-Subsystem Team — AI | Complicated-Subsystem | `@your-org/ai-team`         |
| `src/observability/`       | Platform Team                   | Platform              | `@your-org/platform`        |
| `src/shared/`              | Platform Team                   | Platform              | `@your-org/platform`        |
| `frontend/`                | Stream Team — Frontend          | Stream-Aligned        | `@your-org/stream-frontend` |
| `services/domain-service/` | Stream Team — Domain            | Stream-Aligned        | `@your-org/stream-domain`   |
| `services/event-worker/`   | Stream Team — Domain            | Stream-Aligned        | `@your-org/stream-domain`   |
| `infrastructure/`          | Platform Team                   | Platform              | `@your-org/platform`        |
| `.github/workflows/`       | Platform Team                   | Platform              | `@your-org/platform`        |
| `specs/`                   | Tech Lead + Product Owner       | —                     | —                           |
| `docs/adr/`                | Tech Lead                       | —                     | —                           |
| `docs/privacy/`            | DPO                             | —                     | —                           |

> **Keep in sync:** This table must match `.github/CODEOWNERS`. Run `make validate-ownership` (or a manual diff) after every team ownership change.

---

## 4. Team API Definition Template

Every team publishes a Team API so other teams know how to interact with it. Fill in one card per team.

```
## Team API — <Team Name>

**Type:** [ ] Stream-Aligned  [ ] Platform  [ ] Enabling  [ ] Complicated-Subsystem
**Mission:** <one sentence — what value this team delivers>
**Members:** <size and roles, e.g., "4 engineers + 1 SRE">

### Services owned
- <service name> — <brief description> — SLO: <availability target>

### What we provide (X-as-a-Service)
- <API / platform feature / tooling> — <how to consume it, link to docs>

### How to engage us
| Mode | When | Channel | SLA |
|---|---|---|---|
| Async request | Non-urgent, well-defined | GitHub Issue + `@team-slug` | 2 business days |
| Collaboration | Novel integration / uncertainty | Slack `#team-channel` + calendar invite | Schedule within 1 week |
| Incident | Production impact on shared infra | PagerDuty + Slack `#incidents` | 15 min acknowledgement |

### What we need from you
- <upstream dependency or expectation, e.g., "Spec before implementation request">
- <interface constraint, e.g., "Use our Helm chart; do not fork it">

### Office hours
<day and time, e.g., "Tuesdays 14:00–15:00 UTC — open Q&A on platform tooling">
```

---

## 5. Interaction Mode Map

Document the current interaction mode between each pair of teams. Review quarterly — modes should evolve toward X-as-a-Service as interfaces mature.

| Team A                 | Team B               | Current Mode   | Target Mode    | Review Date |
| ---------------------- | -------------------- | -------------- | -------------- | ----------- |
| Stream Team — API      | Platform Team        | X-as-a-Service | X-as-a-Service | 2026-08-31  |
| Stream Team — API      | AI Team              | Collaboration  | X-as-a-Service | 2026-07-31  |
| Stream Team — Frontend | Stream Team — API    | X-as-a-Service | X-as-a-Service | 2026-08-31  |
| Platform Team          | All stream teams     | X-as-a-Service | X-as-a-Service | 2026-08-31  |
| Enabling Team (SRE)    | Stream Team — Domain | Facilitating   | X-as-a-Service | 2026-06-30  |

---

## 6. Relationship to RACI and CODEOWNERS

| Artefact                         | Purpose                              | Sync requirement                                                         |
| -------------------------------- | ------------------------------------ | ------------------------------------------------------------------------ |
| This document (team-topology.md) | Who teams are and how they interact  | Update when team ownership or interaction mode changes                   |
| `docs/governance/raci-matrix.md` | Who is accountable for each process  | Review when team structure changes; RACI roles must map to real teams    |
| `.github/CODEOWNERS`             | Who must approve PRs touching a path | Must match Squad Ownership Map (§3) exactly; divergence = governance gap |
| `services.yaml`                  | Canonical service registry           | `owner` field in each entry must match the owning team slug in this doc  |

> **Divergence rule:** If this document, RACI, and CODEOWNERS disagree on ownership, CODEOWNERS governs for PR approvals; this document governs for incident escalation and quarterly planning.

---

## 7. Customizing for Your Organization

When adopting this template:

1. **Replace placeholder team slugs** (`@your-org/stream-api` etc.) with your actual GitHub team slugs throughout this document and in `.github/CODEOWNERS`.
2. **Identify your team types** — most organizations start with one platform team and two to three stream-aligned teams. Add complicated-subsystem teams only when complexity genuinely warrants it.
3. **Start all interactions as Collaboration** on new integrations, then explicitly schedule the transition to X-as-a-Service within four weeks.
4. **Delete rows** from the Squad Ownership Map that don't apply (e.g., remove `src/agents/` rows if the AI Agents Module is not activated).
5. **Publish Team API cards** (§4) in your internal wiki or as `docs/governance/team-api-<team-slug>.md` files in this repo.
