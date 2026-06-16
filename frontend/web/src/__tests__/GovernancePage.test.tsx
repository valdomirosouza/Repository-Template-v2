const mockGetSloStatus = jest.fn();

jest.mock("@/lib/api", () => ({
  GovernanceApi: jest.fn().mockImplementation(() => ({
    getSloStatus: mockGetSloStatus,
  })),
  Configuration: jest.fn(),
}));

import { render, screen } from "@testing-library/react";

import GovernancePage from "@/app/governance/page";
import type { SLOStatusResponse } from "@/lib/api";

const status: SLOStatusResponse = {
  sourceVersion: "1.2.3",
  generatedAt: "2026-01-01T00:00:00Z",
  services: [
    {
      name: "api-service",
      description: "Core API",
      slos: [
        {
          name: "availability",
          sliType: "availability",
          description: "uptime",
          target: 99.9,
          window: "30d",
          observed: {
            dataAvailable: true,
            value: 99.95,
            unit: "%",
            scope: "process_lifetime",
            source: "in-process counter",
          },
        },
        {
          name: "latency-p95",
          sliType: "latency",
          targetMs: 250,
          window: "30d",
          observed: {
            dataAvailable: false,
            note: "no in-process sample yet",
          },
        },
      ],
    },
  ],
};

afterEach(() => jest.clearAllMocks());

it("renders the live observed value and the no-live-data note", async () => {
  mockGetSloStatus.mockResolvedValue(status);
  render(<GovernancePage />);

  // header renders only after data loads
  expect(await screen.findByText("SLO & Error Budget")).toBeInTheDocument();

  // SLO with dataAvailable: true shows the value
  expect(screen.getByText(/99\.95/)).toBeInTheDocument();
  expect(screen.getByText(/process_lifetime/)).toBeInTheDocument();

  // SLO with dataAvailable: false shows the honest badge + note
  expect(screen.getByText("no live data")).toBeInTheDocument();
  expect(screen.getByText("no in-process sample yet")).toBeInTheDocument();
});

it("shows the loading state before data resolves", () => {
  let resolve!: (v: SLOStatusResponse) => void;
  mockGetSloStatus.mockReturnValue(new Promise<SLOStatusResponse>((r) => (resolve = r)));
  render(<GovernancePage />);

  expect(screen.getByText(/Loading SLO status/)).toBeInTheDocument();
  resolve(status);
});

it("shows the error state when the load fails", async () => {
  mockGetSloStatus.mockRejectedValue(new Error("slo boom"));
  render(<GovernancePage />);

  expect(await screen.findByText(/Error: slo boom/)).toBeInTheDocument();
});
