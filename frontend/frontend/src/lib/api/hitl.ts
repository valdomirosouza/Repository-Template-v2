import { apiFetch } from "./client";
import type { DecisionPayload, HITLRequest } from "./types";

export async function fetchPendingRequests(): Promise<HITLRequest[]> {
  return apiFetch<HITLRequest[]>("/v1/hitl/requests?status=PENDING");
}

export async function submitDecision(
  requestId: string,
  approved: boolean,
  rationale: string,
): Promise<void> {
  const payload: DecisionPayload = {
    approved,
    rationale,
    decided_by: "operator",
  };
  await apiFetch(`/v1/hitl/${requestId}/decide`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
