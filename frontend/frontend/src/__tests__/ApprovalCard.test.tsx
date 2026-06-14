import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ApprovalCard } from "@/components/hitl/ApprovalCard";
import { type HITLRequestSummary, HITLRequestSummaryStatusEnum } from "@/lib/api";

const mockRequest: HITLRequestSummary = {
  requestId: "req-001",
  agentId: "agent-abc",
  actionType: "write_file",
  contextSummary: 'Write to /etc/config: {"key":"value"}',
  riskScore: 0.6,
  status: HITLRequestSummaryStatusEnum.Pending,
  createdAt: "2026-05-28T10:00:00Z",
  expiresAt: "2026-05-28T11:00:00Z",
};

describe("ApprovalCard", () => {
  it("renders action type and risk score", () => {
    render(<ApprovalCard request={mockRequest} onDecision={jest.fn()} />);
    expect(screen.getByText("write_file")).toBeInTheDocument();
    expect(screen.getByText(/risk 60%/)).toBeInTheDocument();
  });

  it("disables buttons when rationale is empty", () => {
    render(<ApprovalCard request={mockRequest} onDecision={jest.fn()} />);
    expect(screen.getByText("Approve")).toBeDisabled();
    expect(screen.getByText("Reject")).toBeDisabled();
  });

  it("calls onDecision with approved=true when Approve clicked", async () => {
    const onDecision = jest.fn().mockResolvedValue(undefined);
    render(<ApprovalCard request={mockRequest} onDecision={onDecision} />);

    fireEvent.change(screen.getByPlaceholderText("Rationale (required)"), {
      target: { value: "Looks safe" },
    });
    fireEvent.click(screen.getByText("Approve"));

    await waitFor(() => {
      expect(onDecision).toHaveBeenCalledWith("req-001", true, "Looks safe");
    });
  });

  it("calls onDecision with approved=false when Reject clicked", async () => {
    const onDecision = jest.fn().mockResolvedValue(undefined);
    render(<ApprovalCard request={mockRequest} onDecision={onDecision} />);

    fireEvent.change(screen.getByPlaceholderText("Rationale (required)"), {
      target: { value: "Too risky" },
    });
    fireEvent.click(screen.getByText("Reject"));

    await waitFor(() => {
      expect(onDecision).toHaveBeenCalledWith("req-001", false, "Too risky");
    });
  });
});
