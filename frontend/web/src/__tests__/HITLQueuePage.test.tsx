const mockListPending = jest.fn();
const mockSubmitDecision = jest.fn();

jest.mock("@/lib/api", () => ({
  HitlApi: jest.fn().mockImplementation(() => ({
    listPendingRequests: mockListPending,
    submitDecision: mockSubmitDecision,
  })),
  Configuration: jest.fn(),
  DecisionInDecisionEnum: { Approved: "APPROVED", Rejected: "REJECTED" },
  HITLRequestSummaryStatusEnum: { Pending: "PENDING" },
}));

import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import HITLQueuePage from "@/app/hitl/page";
import type { HITLRequestSummary } from "@/lib/api";

const req: HITLRequestSummary = {
  requestId: "req-1",
  agentId: "agent-x",
  actionType: "write_file",
  contextSummary: "do X",
  riskScore: 0.5,
  status: "PENDING",
  createdAt: "2026-01-01T00:00:00Z",
  expiresAt: "2026-01-01T01:00:00Z",
};

afterEach(() => jest.clearAllMocks());

it("renders pending requests after the initial load", async () => {
  mockListPending.mockResolvedValue([req]);
  render(<HITLQueuePage />);
  expect(await screen.findByText("write_file")).toBeInTheDocument();
  expect(screen.getByText(/1 pending request/)).toBeInTheDocument();
});

it("shows the empty state when there are no requests", async () => {
  mockListPending.mockResolvedValue([]);
  render(<HITLQueuePage />);
  expect(await screen.findByText("No pending requests.")).toBeInTheDocument();
});

it("shows an error state when the load fails", async () => {
  mockListPending.mockRejectedValue(new Error("boom"));
  render(<HITLQueuePage />);
  expect(await screen.findByText(/Error: boom/)).toBeInTheDocument();
});

it("submits an APPROVED decision and removes the resolved card", async () => {
  mockListPending.mockResolvedValue([req]);
  mockSubmitDecision.mockResolvedValue({});
  render(<HITLQueuePage />);
  await screen.findByText("write_file");

  fireEvent.change(screen.getByPlaceholderText("Rationale (required)"), {
    target: { value: "approved by operator" },
  });
  fireEvent.click(screen.getByText("Approve"));

  await waitFor(() =>
    expect(mockSubmitDecision).toHaveBeenCalledWith({
      requestId: "req-1",
      decisionIn: { decision: "APPROVED", rationale: "approved by operator" },
    }),
  );
  await waitFor(() => expect(screen.queryByText("write_file")).not.toBeInTheDocument());
});
