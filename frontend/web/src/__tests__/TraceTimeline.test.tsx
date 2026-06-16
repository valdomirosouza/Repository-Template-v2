import { render, screen } from "@testing-library/react";

import { TraceTimeline } from "@/components/runs/TraceTimeline";
import type { TraceEvent } from "@/lib/api";

const events: TraceEvent[] = [
  {
    eventType: "guardrail",
    action: "pii_filter",
    outcome: "success",
    riskScore: 0.2,
    occurredAt: "2026-06-01T10:00:00Z",
  },
  {
    eventType: "agent_action",
    action: "write_file",
    outcome: "failed",
    occurredAt: "2026-06-01T10:01:00Z",
  },
];

describe("TraceTimeline", () => {
  it("renders each event's type, action, outcome and risk score", () => {
    render(<TraceTimeline timeline={events} />);
    expect(screen.getByText("guardrail")).toBeInTheDocument();
    expect(screen.getByText("pii_filter")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText(/risk 20%/)).toBeInTheDocument();
    expect(screen.getByText("agent_action")).toBeInTheDocument();
    expect(screen.getByText("write_file")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
  });

  it("omits the risk score when it is absent", () => {
    render(<TraceTimeline timeline={[events[1]]} />);
    expect(screen.queryByText(/risk/)).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no events", () => {
    render(<TraceTimeline timeline={[]} />);
    expect(screen.getByText("No timeline events to display.")).toBeInTheDocument();
  });
});
