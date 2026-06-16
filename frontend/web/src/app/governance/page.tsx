"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorBudgetPanel } from "@/components/governance/ErrorBudgetPanel";
import { Configuration, GovernanceApi, type SLOStatusResponse } from "@/lib/api";

const api = new GovernanceApi(
  new Configuration({ basePath: process.env.NEXT_PUBLIC_API_BASE_URL }),
);

export default function GovernancePage() {
  const [status, setStatus] = useState<SLOStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getSloStatus();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load SLO status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  if (loading && status === null) {
    return <p style={{ padding: "2rem" }}>Loading SLO status…</p>;
  }

  if (error) {
    return <p style={{ padding: "2rem", color: "red" }}>Error: {error}</p>;
  }

  if (!status) {
    return null;
  }

  return (
    <main style={{ padding: "2rem", maxWidth: "900px", margin: "0 auto" }}>
      <h1>SLO &amp; Error Budget</h1>
      <p style={{ color: "#6b7280", marginTop: "0.5rem", fontSize: "0.875rem" }}>
        Targets are the real configured SLO definitions. Observed values are shown only where a real
        in-process sample exists; everywhere else an honest &ldquo;no live data&rdquo; badge is
        rendered (no number is fabricated — CLAUDE.md §3.6, SPEC-API-004).
      </p>
      <p style={{ color: "#9ca3af", marginTop: "0.25rem", fontSize: "0.75rem" }}>
        {status.sourceVersion ? `source version ${status.sourceVersion} · ` : ""}
        generated {new Date(status.generatedAt).toLocaleString()}
      </p>
      <div style={{ marginTop: "1.5rem" }}>
        <ErrorBudgetPanel status={status} />
      </div>
    </main>
  );
}
