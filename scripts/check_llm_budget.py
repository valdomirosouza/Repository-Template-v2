"""LLM CI spend budget circuit breaker.

Reads the current month's LLM spend from the environment variable
LLM_CI_CURRENT_MONTH_SPEND_USD (set by llm-budget-tracker.yml) and
compares it to the configured monthly cap (LLM_CI_MONTHLY_BUDGET_USD,
default 50.0).

Exit codes:
  0 — budget is available; model contract tests may proceed
  1 — budget exhausted or environment misconfigured; tests should be skipped

GitHub Actions output:
  budget_ok=true|false  — written to GITHUB_OUTPUT if the env var is set

Spec: ADR-0051 (model behavioral contracts, Q5 — non-blocking budget gate)
"""

from __future__ import annotations

import os
import sys


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(
            f"[budget-check] WARNING: {name}={raw!r} is not a valid float; using default {default}",
            file=sys.stderr,
        )
        return default


def _write_github_output(key: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{key}={value}\n")


def main() -> int:
    monthly_budget = _float_env("LLM_CI_MONTHLY_BUDGET_USD", 50.0)
    current_spend = _float_env("LLM_CI_CURRENT_MONTH_SPEND_USD", 0.0)

    remaining = monthly_budget - current_spend
    budget_ok = remaining > 0

    print(f"[budget-check] Monthly budget: ${monthly_budget:.2f}")
    print(f"[budget-check] Current spend:  ${current_spend:.2f}")
    print(f"[budget-check] Remaining:      ${remaining:.2f}")
    print(f"[budget-check] Budget OK:      {budget_ok}")

    _write_github_output("budget_ok", "true" if budget_ok else "false")
    _write_github_output("remaining_usd", f"{remaining:.2f}")

    if not budget_ok:
        print(
            f"[budget-check] BUDGET EXHAUSTED — skipping model contract tests. "
            f"Monthly cap ${monthly_budget:.2f} reached (spent ${current_spend:.2f}). "
            "Tests will resume next calendar month.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
