# Org Migration Runbook (Phase 3 — RFC-0018)

> Moves `Repository-Template-v2` from a personal namespace into a GitHub **org** so CODEOWNERS
> reviews and dual-approval are **enforced**, and the release-please PR merges without `--admin`.
> **Legend:** 🧑 = human-only (account/ownership) · 🤖 = an agent can do it after the org exists.

Plan a low-traffic window. The old URL auto-redirects, but announce the change.

---

## 0. Pre-flight 🧑

- [ ] Decide the **org name** (`<ORG>`).
- [ ] Decide the **review policy** (RFC-0018 §2a): enforce review everywhere (recommended) vs keep
      docs auto-merge via a path-targeted laxer ruleset.
- [ ] Ensure you (and reviewers) have org seats.

## 1. Create the org + Teams 🧑

- [ ] Create the GitHub org `<ORG>`.
- [ ] Create these **7 Teams** (names must match `.github/CODEOWNERS`) and add members:
      `ai-governance`, `devops-team`, `platform-team`, `privacy-team`, `security-team`,
      `sre-team`, `tech-leads`.
- [ ] Enable org setting **"Allow GitHub Actions to create and approve pull requests"** (parity
      with the current repo setting).

## 2. Transfer the repo 🧑

- [ ] `gh api -X POST repos/valdomirosouza/Repository-Template-v2/transfer -f new_owner=<ORG>`
      (or Settings → Danger Zone → Transfer). Irreversible-ish (can transfer back).
- [ ] Re-add repo secrets/variables if not inherited: `CODECOV_TOKEN`, `RELEASE_PLEASE_TOKEN`
      (RFC-0014), and the `CONTAINER_REGISTRY=ghcr.io` variable (RFC-0010).

## 3. Swap placeholders + owner references 🤖 (after transfer)

- [ ] CODEOWNERS teams: `make template-init` already maps `@your-org/` → `@<ORG>/`; or:
      `grep -rl '@your-org/' .github/CODEOWNERS | xargs sed -i '' 's|@your-org/|@<ORG>/|g'`.
- [ ] Owner/URL references (RFC-0018 §5 list): replace `valdomirosouza` → `<ORG>` in
      `README.md`, `CLAUDE_SESSION_INIT.md`, `.github/workflows/template-init.yml`,
      `.github/workflows/template-sync.yml`, `docs/governance/owner-onboarding.md`,
      `docs/quickstart/agent-onboarding.md`, `docs/compliance/iso27001-annex-a-control-matrix.md`,
      `specs/system/SPEC-LGS-001-*.md`, and `ghcr.io/valdomirosouza/*` image paths.
      (Leave historical `CHANGELOG.md` / `docs/adr/*` / `docs/change-management/rfc/*` records.)
- [ ] Verify the governance gate's CODEOWNERS placeholder check still passes
      (`Validate CODEOWNERS has no @org/ placeholder teams`, REM-009).
- [ ] Open these as a normal PR; confirm CI green.

## 4. Enforce protection via ruleset 🤖

- [ ] Delete the personal-repo ruleset:
      `gh api repos/<ORG>/Repository-Template-v2/rulesets` → find id →
      `gh api -X DELETE repos/<ORG>/Repository-Template-v2/rulesets/<id>`.
- [ ] Apply the org ruleset:
      `gh api -X POST repos/<ORG>/Repository-Template-v2/rulesets --input docs/governance/org-protection-ruleset.json`
      (same 9 checks + force-push/deletion block, **plus** `require_code_owner_review`,
      `required_approving_review_count: 1`, **OrganizationAdmin bypass**).
- [ ] **SOX paths:** add a second path-targeted ruleset requiring **2** approvals on
      `src/**`, `services/**`, `infrastructure/**` (ADR-0026 segregation of duties).
- [ ] If keeping docs auto-merge (§2a option B): add a laxer `docs/**`-only ruleset at 0 reviews.

## 5. Reconcile docs 🤖

- [ ] Update **RFC-0013** (reviews 0→1, code-owner review now true) and **RFC-0014** (the
      `OrganizationAdmin` bypass now resolves → release PR merges without `--admin`; PAT optional).
- [ ] Note the new GHCR path `ghcr.io/<ORG>/repository-template-v2` in release/SBOM docs.

## 6. Verify 🤖

- [ ] `gh api repos/<ORG>/Repository-Template-v2/rules/branches/main` as a **non-admin** shows the
      4 rules; as an **OrganizationAdmin** shows the release path can bypass.
- [ ] Open a trivial PR touching a CODEOWNERS-owned path → confirm it **requires** the owning
      team's review before merge.
- [ ] Confirm the next release-please PR merges via a normal (org-admin) merge — no `--admin`.
- [ ] `make check-control-bindings`, `make check-action-pins`, full CI green.

## Rollback 🧑🤖

Transfer the repo back to the personal account; delete the org ruleset and re-apply the RFC-0013
personal-repo ruleset (its JSON is in RFC-0013 §2).
