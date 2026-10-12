/** Every call to the Campus Customs backend lives here. */

import type {
  Approval,
  CashResponse,
  DecideResponse,
  Draft,
  EventsResponse,
  RunState,
  TicketsResponse,
} from "./types";

export const API_BASE = "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body; keep the status text */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ ok: boolean; model: string; mcp_tools: number }>("/health"),

  tickets: () => request<TicketsResponse>("/tickets"),

  /** Hand a ticket to the agent team. Returns immediately; follow it with `events`. */
  runTicket: (ticketId: number) =>
    request<{ run_id: string; ticket_id: number; status: string }>(
      `/tickets/${ticketId}/run`,
      { method: "POST" },
    ),

  /** Incremental feed. Pass `sinceSeq` so each poll only brings back what is new. */
  events: (runId?: string, sinceSeq?: number | null) => {
    const params = new URLSearchParams({ limit: "400" });
    if (runId) params.set("run_id", runId);
    if (sinceSeq != null) params.set("since_seq", String(sinceSeq));
    return request<EventsResponse>(`/events?${params}`);
  },

  runs: () => request<{ count: number; busy: boolean; runs: RunState[] }>("/runs"),

  cash: () => request<CashResponse>("/cash"),

  /** The approval queue, flattened to the list the drawer renders. */
  approvals: async () =>
    (await request<{ approvals: Approval[] }>("/approvals")).approvals,

  drafts: () => request<{ count: number; drafts: Draft[] }>("/drafts"),

  /** The only call in the app that moves money. */
  decide: (approvalId: number, decision: "approve" | "reject", decidedBy: string) =>
    request<DecideResponse>(`/approvals/${approvalId}/decide`, {
      method: "POST",
      body: JSON.stringify({ decision, decided_by: decidedBy }),
    }),

  reset: () => request<{ ok: boolean; balance: number }>("/reset", { method: "POST" }),
};
