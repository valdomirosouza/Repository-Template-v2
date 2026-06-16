import { render, screen } from "@testing-library/react";

import { ErrorBudgetPanel } from "@/components/governance/ErrorBudgetPanel";
import type { SLOStatusResponse } from "@/lib/api";

const status: SLOStatusResponse = {
  sourceVersion: "1.0",
  generatedAt: "2026-06-01T00:00:00Z",
  services: [
    {
      name: "api-gateway",
      description: "Edge service",
      slos: [
        {
          name: "availability",
          sliType: "availability",
          target: 0.999,
          window: "30d",
          observed: {
            dataAvailable: true,
            value: 0.9995,
            unit: "ratio",
            source: "in_process_counter",
            scope: "process_lifetime",
          },
        },
        {
          name: "latency-p99",
          sliType: "latency",
          targetMs: 250,
          window: "30d",
          observed: {
            dataAvailable: false,
            note: "no metrics-query layer available",
          },
        },
      ],
    },
  ],
};

describe("ErrorBudgetPanel", () => {
  it("renders targets (target and target_ms) and sli types", () => {
    render(<ErrorBudgetPanel status={status} />);
    // "availability" is both the SLO name and its sli_type, so it appears twice.
    expect(screen.getAllByText("availability").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("0.999")).toBeInTheDocument();
    expect(screen.getByText("latency-p99")).toBeInTheDocument();
    expect(screen.getByText("250 ms")).toBeInTheDocument();
    expect(screen.getByText("latency")).toBeInTheDocument();
  });

  it("shows the observed value, unit and scope when data is available", () => {
    render(<ErrorBudgetPanel status={status} />);
    expect(screen.getByText("0.9995 ratio")).toBeInTheDocument();
    expect(screen.getByText("(process_lifetime)")).toBeInTheDocument();
  });

  it("shows a 'no live data' badge and the note when data is not available", () => {
    render(<ErrorBudgetPanel status={status} />);
    expect(screen.getByText("no live data")).toBeInTheDocument();
    expect(screen.getByText("no metrics-query layer available")).toBeInTheDocument();
  });

  it("does not fabricate a number when data is unavailable", () => {
    render(<ErrorBudgetPanel status={status} />);
    // The unavailable latency SLO must not render a fake 100% / value.
    expect(screen.queryByText("100%")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no services", () => {
    render(<ErrorBudgetPanel status={{ generatedAt: "2026-06-01T00:00:00Z", services: [] }} />);
    expect(screen.getByText("No SLOs defined.")).toBeInTheDocument();
  });
});
