const mockGetRunTrace = jest.fn();

// The page calls React 19's `use(params)` to unwrap the route-param promise.
// The test runtime pins React 18.3.1, where `use` does not exist, so we provide
// a minimal synchronous shim that unwraps an already-resolved promise's value.
jest.mock("react", () => {
  const actual = jest.requireActual("react");
  return {
    ...actual,
    use: (value: unknown) => (value as { __resolved?: unknown }).__resolved ?? value,
  };
});

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    ...actual,
    RunsApi: jest.fn().mockImplementation(() => ({
      getRunTrace: mockGetRunTrace,
    })),
    Configuration: jest.fn(),
  };
});

import { render, screen } from "@testing-library/react";

import RunTracePage from "@/app/runs/[requestId]/page";
import { ResponseError, type RunTraceResponse, type TraceEvent } from "@/lib/api";

const events: TraceEvent[] = [
  {
    eventType: "perception",
    action: "pii_mask",
    outcome: "success",
    riskScore: 0.1,
    occurredAt: "2026-01-01T00:00:00Z",
  },
  {
    eventType: "act",
    action: "write_file",
    outcome: "failed",
    occurredAt: "2026-01-01T00:01:00Z",
  },
];

const baseTrace: RunTraceResponse = {
  requestId: "req-42",
  status: "completed",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:02:00Z",
  timeline: events,
  timelineAssociation: "metadata_request_id",
};

// The `use` shim above reads `__resolved`; we cast to the Promise type the page expects.
const params = { __resolved: { requestId: "req-42" } } as unknown as Promise<{
  requestId: string;
}>;

afterEach(() => jest.clearAllMocks());

it("renders status, request id and timeline events after load", async () => {
  mockGetRunTrace.mockResolvedValue(baseTrace);
  render(<RunTracePage params={params} />);

  expect(await screen.findByText("req-42")).toBeInTheDocument();
  expect(screen.getByText("completed")).toBeInTheDocument();
  expect(screen.getByText("pii_mask")).toBeInTheDocument();
  expect(screen.getByText("write_file")).toBeInTheDocument();
  // association is not "none", so the honest note must NOT be shown
  expect(screen.queryByRole("note")).not.toBeInTheDocument();
  expect(screen.getByText(/association: metadata_request_id/)).toBeInTheDocument();
});

it("renders error and result blocks when present", async () => {
  mockGetRunTrace.mockResolvedValue({
    ...baseTrace,
    status: "failed",
    error: "boom happened",
    result: { ok: false },
  });
  render(<RunTracePage params={params} />);

  // "failed" appears both as the run status and a timeline event outcome.
  expect((await screen.findAllByText("failed")).length).toBeGreaterThan(0);
  expect(screen.getByText(/boom happened/)).toBeInTheDocument();
  expect(screen.getByText(/"ok": false/)).toBeInTheDocument();
});

it("renders the honest 'none' association note", async () => {
  mockGetRunTrace.mockResolvedValue({
    ...baseTrace,
    timeline: [],
    timelineAssociation: "none",
  });
  render(<RunTracePage params={params} />);

  await screen.findByText("req-42");
  expect(screen.getByRole("note")).toBeInTheDocument();
  expect(screen.getByText(/timeline_association = none/)).toBeInTheDocument();
  expect(screen.getByText("No timeline events to display.")).toBeInTheDocument();
});

it("shows the not-found view on a 404 ResponseError", async () => {
  const response = { status: 404 } as Response;
  mockGetRunTrace.mockRejectedValue(new ResponseError(response, "not found"));
  render(<RunTracePage params={params} />);

  expect(await screen.findByText("Run not found")).toBeInTheDocument();
});

it("shows the error view on a non-404 failure", async () => {
  mockGetRunTrace.mockRejectedValue(new Error("network down"));
  render(<RunTracePage params={params} />);

  expect(await screen.findByText(/Error: network down/)).toBeInTheDocument();
});
