# ADR-0088 — Provider-Neutral Terraform Layering

**Status:** Accepted
**Date:** 2026-09-12
**Authors:** DevOps Lead · SRE Lead (drafted with Claude Code, Wave 14 · W14-T8, issue #383)
**Spec:** specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md
**Supersedes:** None | **Superseded by:** None
**Relates to:** [ADR-0042](ADR-0042-kubernetes-probe-strategy.md), [ADR-0087](ADR-0087-marker-based-template-sync.md)

---

## Context

The Seven-Axis Review (2026-09-12) measured the infrastructure layer as AWS-only and hard: every
environment declares `provider "aws"` with EKS data sources, the S3 backend bucket
(`your-org-terraform-state`), region (`us-east-1`), lock table and cluster names are literals in
`main.tf`, and all eleven modules are pure `aws_*` resources. Porting to GCP, Azure or on-prem
means rewriting the tree. The counterweight already exists: the deploy path is plain
`helm`/`kubectl` from a kubeconfig, and Helm charts exist for all four services — the _runtime_
contract is cloud-agnostic; only the provisioning layer is not.

## Decision

We will separate the **interface** from the **implementation** in three steps, the first of
which lands in this ADR's PR:

1. **No literal account, region, bucket or cluster name in `.tf` files (now).** The S3 backend
   becomes a _partial_ configuration (`backend "s3" {}`) fed by
   `infrastructure/terraform/environments/<env>/backend.hcl` (gitignored) with a committed
   `backend.hcl.example`; region and cluster name are variables with per-environment defaults
   in `terraform.tfvars.example`. `terraform init -backend-config=backend.hcl` is documented.
2. **Interface = what the Helm layer consumes (now, documented).** The outputs every module tree
   must produce for the runtime layer are enumerated in
   `infrastructure/terraform/INTERFACE.md`: cluster endpoint + CA, kubeconfig secret name,
   Postgres/Redis/Kafka connection secrets, OTLP endpoint, image registry, and the four
   service-role identities. A provider implementation is complete when it emits those outputs.
3. **Implementation directories (next).** The current tree moves to
   `infrastructure/terraform/providers/aws/` and a GCP or Azure implementation is
   bring-your-own-provider against `INTERFACE.md`. This move is _deferred_: it touches every
   environment path and the Checkov/CI paths, and the portability targets of Wave 14 are met
   by steps 1–2. Tracked as a follow-up on issue #383.

## Consequences

### Positive

- An adopter can `terraform init` without editing `.tf` files; secrets and account-specific
  values live outside the synced tree (ADR-0087 excludes `backend.hcl`).
- The Helm/K8s layer is explicitly the portable contract; a second cloud has a checklist.

### Negative / Trade-offs

- Partial backend config is one more file to create on first run (`make template-init` seeds it).
- Step 3 is a large rename left for later; until then the directory name still says AWS.

## Alternatives Considered

- **Terragrunt / CDK for Terraform.** Rejected: new tooling for adopters; the same interface
  discipline is achievable with plain Terraform.
- **Keep literals, document them.** Rejected: SPEC-INFRA-001 §15 already marks them as
  illustrative; literals in `.tf` still get applied by mistake.

## Compliance & Risk

- **Controls affected:** ADR-0029 §1 Checkov stays green (no resource changes).
- **Data classification impact:** none. **Autonomy impact:** none.
- **Review/expiry:** revisit when step 3 lands.

---

## Related

- Seven-Axis Review §4 Portability (2026-09-12) · Template v2 Improvement Plan W14-T8
