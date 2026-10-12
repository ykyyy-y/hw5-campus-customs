/** How each agent reads on the board: colour, monogram, and plain-English name.
 *
 * Five voices need to stay apart at a glance when four of them are talking inside
 * one ticket, so every agent owns a hue and a monogram rather than sharing a generic
 * avatar. The human gets an entry too — a person acting on the board should never be
 * mistaken for one of the agents.
 */

export interface AgentLook {
  label: string;
  monogram: string;
  color: string;
  bg: string;
}

const LOOKS: Record<string, AgentLook> = {
  Boss: { label: "Boss", monogram: "B", color: "var(--boss)", bg: "var(--boss-bg)" },
  Inventory: { label: "Inventory", monogram: "I", color: "var(--inv)", bg: "var(--inv-bg)" },
  Accounting: { label: "Accounting", monogram: "A", color: "var(--acct)", bg: "var(--acct-bg)" },
  Facilities: { label: "Facilities", monogram: "F", color: "var(--fac)", bg: "var(--fac-bg)" },
  CustomerService: { label: "Customer Service", monogram: "C", color: "var(--cs)", bg: "var(--cs-bg)" },
};

const FALLBACK: AgentLook = {
  label: "Desk",
  monogram: "·",
  color: "var(--ink-soft)",
  bg: "var(--rose-75)",
};

export function lookOf(agent: string): AgentLook {
  if (LOOKS[agent]) return LOOKS[agent];
  if (agent.startsWith("human:")) {
    const name = agent.slice(6).trim();
    return {
      label: name || "You",
      monogram: (name[0] ?? "Y").toUpperCase(),
      color: "var(--human)",
      bg: "var(--human-bg)",
    };
  }
  if (agent === "dashboard" || agent === "human") {
    return { label: "The desk", monogram: "·", color: "var(--human)", bg: "var(--human-bg)" };
  }
  return FALLBACK;
}

/** Tools that change the database. Shown differently from a harmless lookup. */
export const WRITE_TOOLS = new Set([
  "resolve_ticket",
  "adjust_stock",
  "request_payment_approval",
  "decide_payment_approval",
  "pay",
  "save_draft",
]);

/** Tool name -> what it actually did, in words a shop owner would use. */
export function toolPhrase(tool: string, args: Record<string, unknown> | null): string {
  const a = args ?? {};
  switch (tool) {
    case "list_open_tickets": return "read the board";
    case "get_ticket": return `opened ticket ${a.ticket_id ?? ""}`.trim();
    case "resolve_ticket": return `closed ticket ${a.ticket_id ?? ""}`.trim();
    case "check_stock": return `checked stock — ${a.sku} / ${a.size}`;
    case "adjust_stock": return `moved stock — ${a.sku} / ${a.size} by ${a.delta}`;
    case "price_quote": return `priced ${a.qty ?? ""} × ${a.sku}`.trim();
    case "list_vendors": return "looked up vendors";
    case "get_vendor_status": return `checked vendor ${a.vendor_id} — can they ship?`;
    case "estimate_restock_eta": return `dated a restock from vendor ${a.vendor_id}`;
    case "get_rent_due": return `read lease ${a.lease_id}`;
    case "get_cash_balance": return "checked the cash balance";
    case "list_invoices": return "reviewed invoices";
    case "request_payment_approval": return `asked a human to approve $${Number(a.amount ?? 0).toLocaleString()}`;
    case "list_payment_approvals": return "checked the approval queue";
    case "decide_payment_approval": return `${a.decision === "approve" ? "approved" : "rejected"} approval ${a.approval_id}`;
    case "pay": return `paid approval ${a.approval_id}`;
    case "save_draft": return `drafted a ${String(a.kind ?? "message").replace(/_/g, " ")} to ${a.audience}`;
    case "list_drafts": return "reviewed the drafts";
    default: return tool.replace(/_/g, " ");
  }
}
