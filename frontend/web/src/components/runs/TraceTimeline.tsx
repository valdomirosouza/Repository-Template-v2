"use client";

import type { TraceEvent } from "@/lib/api";

interface Props {
  timeline: TraceEvent[];
}

function outcomeColor(outcome: string): string {
  const o = outcome.toLowerCase();
  if (o.includes("fail") || o.includes("error") || o.includes("denied") || o.includes("reject")) {
    return "#dc2626";
  }
  if (o.includes("success") || o.includes("approved") || o.includes("allow")) {
    return "#16a34a";
  }
  return "#6b7280";
}

export function TraceTimeline({ timeline }: Props) {
  if (timeline.length === 0) {
    return <p style={{ color: "#6b7280", padding: "1rem 0" }}>No timeline events to display.</p>;
  }

  return (
    <ol
      style={{
        listStyle: "none",
        margin: 0,
        padding: 0,
        borderLeft: "2px solid #e5e7eb",
      }}
    >
      {timeline.map((event, index) => (
        <li
          key={`${event.occurredAt}-${index}`}
          style={{ position: "relative", padding: "0 0 1.25rem 1.25rem" }}
        >
          <span
            aria-hidden="true"
            style={{
              position: "absolute",
              left: "-7px",
              top: "0.25rem",
              width: "12px",
              height: "12px",
              borderRadius: "50%",
              background: "#fff",
              border: `2px solid ${outcomeColor(event.outcome)}`,
            }}
          />
          <time dateTime={event.occurredAt} style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
            {new Date(event.occurredAt).toLocaleString()}
          </time>
          <div style={{ marginTop: "0.25rem" }}>
            <strong>{event.eventType}</strong>
            <span style={{ marginLeft: "0.5rem", fontSize: "0.875rem" }}>{event.action}</span>
          </div>
          <div style={{ marginTop: "0.25rem", fontSize: "0.8rem" }}>
            <span style={{ color: outcomeColor(event.outcome), fontWeight: 600 }}>
              {event.outcome}
            </span>
            {event.riskScore != null && (
              <span style={{ marginLeft: "0.75rem", color: "#6b7280" }}>
                risk {(event.riskScore * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
