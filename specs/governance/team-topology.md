# Spec TT-001: Team Topology Document

**Spec ID:** TT-001
**Version:** 1.0.0
**Date:** 2026-05-31
**Status:** Accepted
**Author:** Valdomiro Souza

---

## 1. Problem Statement

The repository has a RACI matrix (`docs/governance/raci-matrix.md`) defining
accountability per process, and CODEOWNERS defining file ownership — but no
document describes how engineering teams are structured, how they interact,
or which team owns which service.

Teams adopting this template face the following gaps:

- No standard squad ownership map template
- No definition of team types and interaction modes
- No Team API definition format for inter-team coordination
- No guidance for applying the Team Topologies framework

## 2. Solution

Deliver `docs/governance/team-topology.md` — a team topology guide based on
the Team Topologies framework (Skelton & Pais, 2019) that provides:

- Definitions of the four team types
- Definitions of the three interaction modes
- A squad ownership map template (services × team)
- A Team API definition template
- Customization guidance for adopters of this monorepo template

## 3. Scope

### In scope

- Four team types: stream-aligned, enabling, platform, complicated-subsystem
- Three interaction modes: collaboration, X-as-a-Service, facilitating
- Squad ownership map template (adaptable per organization)
- Team API definition template
- Relationship to RACI matrix and CODEOWNERS

### Out of scope

- Hiring, reporting lines, or org chart tooling
- Agile ceremony cadence (covered by individual team norms)
- Performance management

## 4. Acceptance Criteria

- [ ] `docs/governance/team-topology.md` present and follows repo doc style
- [ ] All four team types defined with examples relevant to this monorepo
- [ ] All three interaction modes defined with triggering conditions
- [ ] Squad ownership map template covers all top-level service paths
- [ ] Team API definition template present with ≥ 5 fields
- [ ] References to RACI matrix and CODEOWNERS included
- [ ] CHANGELOG.md updated

## 5. References

- Team Topologies (Skelton & Pais, 2019): https://teamtopologies.com
- `docs/governance/raci-matrix.md`
- `.github/CODEOWNERS`
- `services.yaml` — canonical service registry
