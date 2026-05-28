export interface HITLRequest {
  id: string;
  agent_id: string;
  action_type: string;
  proposed_action: string;
  risk_score: number;
  status: "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";
  created_at: string;
  expires_at: string;
  context: Record<string, unknown>;
}

export interface DecisionPayload {
  approved: boolean;
  rationale: string;
  decided_by: string;
}

export interface DomainRequest {
  request_id: string;
  status: string;
  created_at: string;
  result?: string;
}
