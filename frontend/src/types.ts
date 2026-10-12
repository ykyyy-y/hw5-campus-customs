/** Shapes returned by the Campus Customs backend. */

export type TicketStatus = "open" | "resolved" | string;

export interface Approval {
  id: number;
  ticket_id: number | null;
  kind: "invoice" | "rent" | string;
  ref_id: number | null;
  amount: number;
  reason: string | null;
  status: "pending" | "approved" | "rejected" | "paid" | string;
  requested_by: string;
  requested_at: string;
  decided_by: string | null;
  decided_at: string | null;
  payment_id: number | null;
}

export interface Draft {
  id: number;
  ticket_id: number | null;
  kind: string;
  audience: string;
  subject: string;
  body: string;
  created_by: string;
  created_at: string;
}

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: TicketStatus;
  notes: string | null;
  created_at: string;
  approvals: Approval[];
  drafts: Draft[];
}

export interface TicketsResponse {
  today: string;
  count: number;
  open: number;
  resolved: number;
  tickets: Ticket[];
}

export type EventKind =
  | "run_started"
  | "ticket_started"
  | "agent_started"
  | "tool_call"
  | "delegation"
  | "delegation_refused"
  | "agent_finished"
  | "ticket_finished"
  | "run_finished"
  | "error";

export interface AgentEvent {
  run_id: string;
  seq: number;
  at_utc: string;
  event: EventKind;
  agent: string;
  depth: number;
  ticket_id: number | null;
  tool: string | null;
  arguments: Record<string, unknown> | null;
  result: unknown;
  to_agent: string | null;
  task: string | null;
  ok: boolean;
  detail: string | null;
  duration_ms: number | null;
  model: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
}

export interface TicketDecision {
  ticket_id: number;
  decision: string;
  reasoning: string;
  agents_consulted: string[];
  actions_taken: string[];
  awaiting_human_approval: number[];
  resolved: boolean;
}

export interface RunState {
  run_id: string;
  ticket_id: number | null;
  status: "running" | "finished" | "error";
  started_utc: string;
  finished_utc: string | null;
  decision: TicketDecision | null;
  error: string | null;
}

export interface EventsResponse {
  count: number;
  total_events: number;
  latest_seq: number | null;
  busy: boolean;
  run: RunState | null;
  events: AgentEvent[];
}

export interface CashResponse {
  account: string;
  balance: number;
  as_of: string;
  today: string;
  paid_out_total: number;
  pending_requests: number;
  pending_total: number;
  balance_if_all_pending_approved: number;
  note: string;
}

export interface DecideResponse {
  ok: boolean;
  approval: Record<string, unknown>;
  payment: {
    payment_id: number;
    amount: number;
    kind: string;
    ref_id: number;
    approved_by: string;
    balance_before: number;
    balance_after: number;
  } | null;
  balance_after: number;
  message: string;
}
