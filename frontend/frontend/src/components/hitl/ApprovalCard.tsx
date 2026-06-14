"use client";

import { useState } from "react";
import type { HITLRequestSummary } from "@/lib/api";

interface Props {
  request: HITLRequestSummary;
  onDecision: (id: string, approved: boolean, rationale: string) => Promise<void>;
}

export function ApprovalCard({ request, onDecision }: Props) {
  const [rationale, setRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handle = async (approved: boolean) => {
    if (!rationale.trim()) return;
    setSubmitting(true);
    try {
      await onDecision(request.requestId, approved, rationale);
    } finally {
      setSubmitting(false);
    }
  };

  const riskColor =
    request.riskScore >= 0.7 ? "red" : request.riskScore >= 0.4 ? "orange" : "green";

  return (
    <article
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: "8px",
        padding: "1.25rem",
        background: "#fff",
      }}
    >
      <header
        style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}
      >
        <div>
          <strong>{request.actionType}</strong>
          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", color: "#6b7280" }}>
            {request.agentId}
          </span>
        </div>
        <span style={{ color: riskColor, fontWeight: 600, fontSize: "0.875rem" }}>
          risk {(request.riskScore * 100).toFixed(0)}%
        </span>
      </header>

      <pre
        style={{
          marginTop: "0.75rem",
          padding: "0.75rem",
          background: "#f3f4f6",
          borderRadius: "4px",
          fontSize: "0.8rem",
          overflow: "auto",
          whiteSpace: "pre-wrap",
        }}
      >
        {request.contextSummary}
      </pre>

      <p style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#9ca3af" }}>
        Expires: {new Date(request.expiresAt).toLocaleString()}
      </p>

      <div style={{ marginTop: "1rem" }}>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Rationale (required)"
          rows={2}
          style={{
            width: "100%",
            padding: "0.5rem",
            borderRadius: "4px",
            border: "1px solid #d1d5db",
          }}
        />
        <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
          <button
            onClick={() => handle(true)}
            disabled={submitting || !rationale.trim()}
            style={{
              padding: "0.5rem 1rem",
              background: "#16a34a",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            Approve
          </button>
          <button
            onClick={() => handle(false)}
            disabled={submitting || !rationale.trim()}
            style={{
              padding: "0.5rem 1rem",
              background: "#dc2626",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            Reject
          </button>
        </div>
      </div>
    </article>
  );
}
