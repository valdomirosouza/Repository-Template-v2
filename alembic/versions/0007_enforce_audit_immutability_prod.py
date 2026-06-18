"""Enforce audit_events immutability — hard-fail in production if the app role is missing.

Migration 0001 made `audit_events` immutable via `REVOKE UPDATE, DELETE` from the application
role, but its DO-block emits only a **WARNING** when the role is absent — so a misconfigured
production deploy would leave the SOX audit table mutable with no hard failure (ADR-0026 finding,
audit issue #338).

This migration re-asserts the REVOKE (idempotent) and makes the missing-role case **fail hard**
(`RAISE EXCEPTION`, aborting the migration) **only when APP_ENV=production**. In non-production
environments (CI, local dev, integration tests — where `app_user` legitimately may not exist) it
keeps the WARNING behaviour so test migrations are not broken. The original migration 0001 is left
untouched (append-only migration history).

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import os

from alembic import context, op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    role = context.config.get_main_option("db_app_role", "app_user")
    # role comes from alembic.ini (a config file, not user input).
    # Hard-fail only in production; warn elsewhere so CI/dev migrations (no app_user) still run.
    is_production = os.environ.get("APP_ENV", "development").lower() == "production"
    on_missing = "RAISE EXCEPTION" if is_production else "RAISE WARNING"
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
            REVOKE UPDATE, DELETE ON audit_events FROM {role};
          ELSE
            {on_missing}
              'DB role {role} not found — audit_events immutability NOT enforced;'
              ' SOX audit trail would be mutable. Create the role / set db_app_role.';
          END IF;
        END
        $$"""
    )


def downgrade() -> None:
    # No-op: downgrading must not re-grant UPDATE/DELETE on the audit trail (that is what 0001's
    # downgrade controls). This migration only strengthens enforcement; reversing it simply returns
    # to 0001's WARNING-on-missing-role behaviour, which requires no schema change.
    pass
