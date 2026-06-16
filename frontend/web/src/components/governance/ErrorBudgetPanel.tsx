"use client";

import type { SLOItemStatus, SLOStatusResponse } from "@/lib/api";

interface Props {
  status: SLOStatusResponse;
}

function formatTarget(slo: SLOItemStatus): string {
  if (slo.targetMs != null) {
    return `${slo.targetMs} ms`;
  }
  if (slo.targetMax != null) {
    return `${slo.targetMax} (max)`;
  }
  if (slo.target != null) {
    return `${slo.target}`;
  }
  return "—";
}

export function ErrorBudgetPanel({ status }: Props) {
  if (status.services.length === 0) {
    return <p style={{ color: "#6b7280" }}>No SLOs defined.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {status.services.map((service) => (
        <section
          key={service.name}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: "8px",
            padding: "1.25rem",
            background: "#fff",
          }}
        >
          <h2 style={{ margin: 0 }}>{service.name}</h2>
          {service.description && (
            <p style={{ marginTop: "0.25rem", color: "#6b7280", fontSize: "0.875rem" }}>
              {service.description}
            </p>
          )}

          <table
            style={{
              marginTop: "1rem",
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.875rem",
            }}
          >
            <thead>
              <tr style={{ textAlign: "left", color: "#6b7280" }}>
                <th style={{ padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>SLO</th>
                <th style={{ padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Type</th>
                <th style={{ padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Target</th>
                <th style={{ padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Window</th>
                <th style={{ padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Observed</th>
              </tr>
            </thead>
            <tbody>
              {service.slos.map((slo) => (
                <tr key={slo.name}>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6" }}>
                    <strong>{slo.name}</strong>
                    {slo.description && (
                      <div style={{ color: "#9ca3af", fontSize: "0.75rem" }}>{slo.description}</div>
                    )}
                  </td>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6" }}>
                    {slo.sliType}
                  </td>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6" }}>
                    {formatTarget(slo)}
                  </td>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6" }}>
                    {slo.window ?? "—"}
                  </td>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6" }}>
                    {slo.observed.dataAvailable ? (
                      <span>
                        <strong>
                          {slo.observed.value ?? "—"}
                          {slo.observed.unit ? ` ${slo.observed.unit}` : ""}
                        </strong>
                        {slo.observed.scope && (
                          <span
                            style={{ marginLeft: "0.5rem", color: "#9ca3af", fontSize: "0.75rem" }}
                          >
                            ({slo.observed.scope})
                          </span>
                        )}
                        {slo.observed.source && (
                          <div style={{ color: "#9ca3af", fontSize: "0.7rem" }}>
                            source: {slo.observed.source}
                          </div>
                        )}
                      </span>
                    ) : (
                      <span>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "0.1rem 0.5rem",
                            borderRadius: "999px",
                            background: "#f3f4f6",
                            color: "#6b7280",
                            fontSize: "0.7rem",
                            fontWeight: 600,
                          }}
                        >
                          no live data
                        </span>
                        {slo.observed.note && (
                          <div
                            style={{ marginTop: "0.25rem", color: "#9ca3af", fontSize: "0.7rem" }}
                          >
                            {slo.observed.note}
                          </div>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}
