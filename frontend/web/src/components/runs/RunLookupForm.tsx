"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function RunLookupForm() {
  const router = useRouter();
  const [requestId, setRequestId] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = requestId.trim();
    if (!id) return;
    router.push(`/runs/${encodeURIComponent(id)}`);
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", maxWidth: "480px" }}
    >
      <input
        type="text"
        value={requestId}
        onChange={(e) => setRequestId(e.target.value)}
        placeholder="Request id"
        aria-label="Request id"
        style={{
          flex: 1,
          padding: "0.5rem",
          borderRadius: "4px",
          border: "1px solid #d1d5db",
        }}
      />
      <button
        type="submit"
        disabled={!requestId.trim()}
        style={{
          padding: "0.5rem 1rem",
          background: "#2563eb",
          color: "#fff",
          border: "none",
          borderRadius: "4px",
          cursor: "pointer",
        }}
      >
        View trace
      </button>
    </form>
  );
}
