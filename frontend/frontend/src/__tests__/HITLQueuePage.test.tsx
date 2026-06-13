import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import HITLQueuePage from "@/app/hitl/page";
import { fetchPendingRequests, submitDecision } from "@/lib/api/hitl";
import type { HITLRequest } from "@/lib/api/types";

jest.mock("@/lib/api/hitl");

const mockFetch = fetchPendingRequests as jest.MockedFunction<typeof fetchPendingRequests>;
const mockSubmit = submitDecision as jest.MockedFunction<typeof submitDecision>;

const req: HITLRequest = {
  id: "req-1",
  agent_id: "agent-x",
  action_type: "write_file",
  proposed_action: "do X",
  risk_score: 0.5,
  status: "PENDING",
  created_at: "2026-01-01T00:00:00Z",
  expires_at: "2026-01-01T01:00:00Z",
  context: {},
};

afterEach(() => jest.clearAllMocks());

it("renders pending requests after the initial load", async () => {
  mockFetch.mockResolvedValue([req]);
  render(<HITLQueuePage />);
  expect(await screen.findByText("write_file")).toBeInTheDocument();
  expect(screen.getByText(/1 pending request/)).toBeInTheDocument();
});

it("shows the empty state when there are no requests", async () => {
  mockFetch.mockResolvedValue([]);
  render(<HITLQueuePage />);
  expect(await screen.findByText("No pending requests.")).toBeInTheDocument();
});

it("shows an error state when the load fails", async () => {
  mockFetch.mockRejectedValue(new Error("boom"));
  render(<HITLQueuePage />);
  expect(await screen.findByText(/Error: boom/)).toBeInTheDocument();
});

it("submits a decision and removes the resolved card", async () => {
  mockFetch.mockResolvedValue([req]);
  mockSubmit.mockResolvedValue();
  render(<HITLQueuePage />);
  await screen.findByText("write_file");

  fireEvent.change(screen.getByPlaceholderText("Rationale (required)"), {
    target: { value: "approved by operator" },
  });
  fireEvent.click(screen.getByText("Approve"));

  await waitFor(() =>
    expect(mockSubmit).toHaveBeenCalledWith("req-1", true, "approved by operator"),
  );
  await waitFor(() => expect(screen.queryByText("write_file")).not.toBeInTheDocument());
});
