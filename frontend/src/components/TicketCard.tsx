import type { Ticket } from "../types";

interface Props {
  ticket: Ticket;
  selected: boolean;
  busy: boolean;
  running: boolean;
  onSelect: () => void;
  onRun: () => void;
}

const TYPE_LABEL: Record<string, string> = {
  customer_order: "customer order",
  rent_notice: "rent notice",
  price_override: "price override",
};

export function TicketCard({ ticket, selected, busy, running, onSelect, onRun }: Props) {
  const resolved = ticket.status !== "open";
  const pending = ticket.approvals.filter((a) => a.status === "pending");

  return (
    <div
      className={`ticket${selected ? " selected" : ""}${resolved ? " is-resolved" : ""}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect()}
    >
      <div className="ticket-top">
        <span className="ticket-no">#{ticket.id}</span>
        <span className="ticket-type">{TYPE_LABEL[ticket.type] ?? ticket.type}</span>
      </div>

      <h3>{ticket.subject}</h3>
      <p className="who">
        from <em>{ticket.requester}</em>
      </p>

      <div className="ticket-tags">
        {ticket.sku && <span className="tag">{ticket.sku}{ticket.size ? ` · ${ticket.size}` : ""}</span>}
        {ticket.qty != null && <span className="tag">qty {ticket.qty}</span>}
        {ticket.lease_id != null && <span className="tag">lease {ticket.lease_id}</span>}
        {ticket.invoice_id != null && <span className="tag alert">invoice {ticket.invoice_id}</span>}
        {pending.length > 0 && (
          <span className="tag alert">
            {pending.length} awaiting approval
          </span>
        )}
        {ticket.drafts.length > 0 && (
          <span className="tag">{ticket.drafts.length} draft{ticket.drafts.length > 1 ? "s" : ""}</span>
        )}
      </div>

      {resolved && (
        <div className="seal" aria-label="resolved">
          <span>
            re&shy;solved
          </span>
        </div>
      )}

      <div className="ticket-foot">
        <button
          className={`run-btn${resolved ? " rerun" : ""}`}
          disabled={busy}
          onClick={(e) => {
            e.stopPropagation();
            onRun();
          }}
        >
          {running ? "Team is working…" : resolved ? "Run again" : "Hand to the team"}
        </button>
      </div>
    </div>
  );
}
