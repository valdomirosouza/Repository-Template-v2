"use client";

import { use, useCallback, useEffect, useState } from "react";

import { TraceTimeline } from "@/components/runs/TraceTimeline";
import {
  Configuration,
  ResponseError,
  RunsApi,
  RunTraceResponseTimelineAssociationEnum,
  type RunTraceResponse,
} from "@/lib/api";

const api = new RunsApi(new Configuration({ basePath: process.env.NEXT_PUBLIC_API_BASE_URL }));

interface PageProps {
  params: Promise<{ requestId: string }>;
}

export default function RunTracePage({ params }: PageProps) {
  const { requestId } = use(params);
  const [trace, setTrace] = useState<RunTraceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setNotFound(false);
      const data = await api.getRunTrace({ requestId });
      setTrace(data);
    } catch (err) {
      if (err instanceof ResponseError && err.response.status === 404) {
        setNotFound(true);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load run trace");
      }
    } finally {
      setLoading(false);
    }
  }, [requestId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && trace === null) {
    return <p style={{ padding: "2rem" }}>Loading run trace…</p>;
  }

  if (notFound) {
    return (
      <main style={{ padding: "2rem", maxWidth: "900px", margin: "0 auto" }}>
        <h1>Run not found</h1>
        <p style={{ color: "#6b7280", marginTop: "0.5rem" }}>
          No request with id <code>{requestId}</code> exists.
        </p>
      </main>
    );
  }

  if (error) {
    return <p style={{ padding: "2rem", color: "red" }}>Error: {error}</p>;
  }

  if (!trace) {
    return null;
  }

  const statusColor =
    trace.status === "failed" ? "#dc2626" : trace.status === "completed" ? "#16a34a" : "#6b7280";

  const associationNone =
    trace.timelineAssociation === RunTraceResponseTimelineAssociationEnum.None;

  return (
    <main style={{ padding: "2rem", maxWidth: "900px", margin: "0 auto" }}>
      <h1>Run trace</h1>
      <p style={{ color: "#6b7280", marginTop: "0.25rem", fontFamily: "monospace" }}>
        {trace.requestId}
      </p>

      <section
        style={{
          marginTop: "1.5rem",
          border: "1px solid #e5e7eb",
          borderRadius: "8px",
          padding: "1.25rem",
          background: "#fff",
        }}
      >
        <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
          <span>
            <strong>Status:</strong>{" "}
            <span style={{ color: statusColor, fontWeight: 600 }}>{trace.status}</span>
          </span>
          <span>
            <strong>Created:</strong> {new Date(trace.createdAt).toLocaleString()}
          </span>
          <span>
            <strong>Updated:</strong> {new Date(trace.updatedAt).toLocaleString()}
          </span>
        </div>

        {trace.error && (
          <p style={{ marginTop: "0.75rem", color: "#dc2626" }}>
            <strong>Error:</strong> {trace.error}
          </p>
        )}

        {trace.result && (
          <div style={{ marginTop: "0.75rem" }}>
            <strong>Result:</strong>
            <pre
              style={{
                marginTop: "0.5rem",
                padding: "0.75rem",
                background: "#f3f4f6",
                borderRadius: "4px",
                fontSize: "0.8rem",
                overflow: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {JSON.stringify(trace.result, null, 2)}
            </pre>
          </div>
        )}
      </section>

      <section style={{ marginTop: "2rem" }}>
        <h2>Timeline</h2>
        {associationNone ? (
          <p
            role="note"
            style={{
              marginTop: "0.5rem",
              padding: "0.75rem 1rem",
              borderRadius: "6px",
              background: "#fffbeb",
              border: "1px solid #fde68a",
              color: "#92400e",
              fontSize: "0.875rem",
            }}
          >
            No per-request audit events are linked yet — see SPEC-API-004 limitation
            (timeline_association = none). This does not mean the run had no activity; the audit
            store is not indexed by request id, so no event could be honestly associated.
          </p>
        ) : (
          <p style={{ marginTop: "0.25rem", fontSize: "0.75rem", color: "#9ca3af" }}>
            association: {trace.timelineAssociation}
          </p>
        )}
        <div style={{ marginTop: "1rem" }}>
          <TraceTimeline timeline={trace.timeline} />
        </div>
      </section>
    </main>
  );
}
