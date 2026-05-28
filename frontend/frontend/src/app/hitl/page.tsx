"use client";

import { useEffect, useState } from "react";
import { ApprovalCard } from "@/components/hitl/ApprovalCard";
import type { HITLRequest } from "@/lib/api/types";
import { fetchPendingRequests, submitDecision } from "@/lib/api/hitl";

export default function HITLQueuePage() {
  const [requests, setRequests] = useState<HITLRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      const data = await fetchPendingRequests();
      setRequests(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 15_000);
    return () => clearInterval(interval);
  }, []);

  const handleDecision = async (id: string, approved: boolean, rationale: string) => {
    await submitDecision(id, approved, rationale);
    setRequests((prev) => prev.filter((r) => r.id !== id));
  };

  if (loading && requests.length === 0) {
    return <p style={{ padding: "2rem" }}>Loading approval queue…</p>;
  }

  if (error) {
    return <p style={{ padding: "2rem", color: "red" }}>Error: {error}</p>;
  }

  return (
    <main style={{ padding: "2rem", maxWidth: "900px", margin: "0 auto" }}>
      <h1>HITL Approval Queue</h1>
      <p style={{ color: "#6b7280", marginTop: "0.5rem" }}>
        {requests.length} pending request{requests.length !== 1 ? "s" : ""}
      </p>
      <div style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
        {requests.length === 0 ? (
          <p style={{ color: "#6b7280" }}>No pending requests.</p>
        ) : (
          requests.map((req) => (
            <ApprovalCard key={req.id} request={req} onDecision={handleDecision} />
          ))
        )}
      </div>
    </main>
  );
}
