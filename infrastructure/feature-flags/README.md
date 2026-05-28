# infrastructure/feature-flags/

> **AI Agents Module dependency.** This directory contains flags that control AI agent autonomy
> levels. If your project does not use the AI Agents Module, this directory can be removed.
> See [`docs/optional-extensions/ai-agents/README.md`](../../docs/optional-extensions/ai-agents/README.md).

Feature flag configuration using [OpenFeature](https://openfeature.dev/) SDK + [flagd](https://flagd.dev/).

**ADR:** [ADR-0015 — Feature Flag Strategy](../../docs/adr/ADR-0015-feature-flag-strategy.md)

---

## Architecture

```
Application (src/shared/feature_flags.py)
    └── OpenFeature SDK  ──── gRPC/HTTP ───► flagd (K8s Deployment)
                                                  └── reads flags from ConfigMap
                                                      (flags/autonomous-mode.yaml)
```

- **No external SaaS dependency** — flagd runs inside the cluster, reads YAML from a mounted ConfigMap.
- **Vendor-neutral** — switching to LaunchDarkly or Unleash requires only changing the OpenFeature provider, not application code.
- **Fallback** — if flagd is unavailable, `is_autonomous_mode_enabled()` falls back to `settings.autonomous_mode_enabled` (env var, default `false`).

---

## Files

| File                         | Description                                                |
| ---------------------------- | ---------------------------------------------------------- |
| `flagd.yaml`                 | K8s ConfigMap (flag YAML) + Deployment + Service for flagd |
| `flags/autonomous-mode.yaml` | Flag definition for `autonomous-mode` (HITL/HOTL control)  |

---

## Flag Catalogue

| Flag Key          | Type    | Default | Values       | Effect                                                                    |
| ----------------- | ------- | ------- | ------------ | ------------------------------------------------------------------------- |
| `autonomous-mode` | boolean | `off`   | `on` / `off` | `on` → HOTL mode (agents act without HITL approval for high-risk actions) |

### Changing a flag

1. Edit `flags/<flag-name>.yaml` — change `defaultVariant`.
2. Apply the ConfigMap update:

   ```bash
   kubectl apply -f infrastructure/feature-flags/flagd.yaml
   ```

3. flagd reloads flags automatically (file watch on mounted volume) — no pod restart needed.

> **Governance:** Enabling `autonomous-mode` in production requires explicit approval from the AI Governance Lead. See `docs/ai-governance/autonomy-boundaries.md`.

---

## Adding a New Flag

1. Create `flags/<new-flag>.yaml`:

   ```yaml
   flags:
     my-new-feature:
       state: ENABLED
       variants:
         "on": true
         "off": false
       defaultVariant: "off"
       targeting: {}
   ```

2. Mount the new file in `flagd.yaml` ConfigMap data section.

3. Add an evaluation function in `src/shared/feature_flags.py`:

   ```python
   def is_my_new_feature_enabled() -> bool:
       try:
           from openfeature import api
           return api.get_client().get_boolean_value("my-new-feature", False)
       except Exception:
           return False
   ```

4. Write unit tests using `InMemoryProvider` (see `tests/unit/shared/test_feature_flags.py`).

---

## flagd Ports

| Port | Protocol | Use                       |
| ---- | -------- | ------------------------- |
| 8013 | gRPC     | OpenFeature gRPC provider |
| 8014 | HTTP     | OFREP (REST evaluation)   |

---

## Related

- Application wrapper: `src/shared/feature_flags.py`
- Unit tests: `tests/unit/shared/test_feature_flags.py`
- Orchestrator integration: `src/agents/orchestrator/orchestrator.py` (`is_autonomous_mode_enabled()`)
- HITL recovery runbook: `docs/runbooks/RB-003-hitl-recovery.md`
