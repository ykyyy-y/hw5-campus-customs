import { useEffect, useRef } from "react";
import { lookOf, toolPhrase, WRITE_TOOLS } from "../agents";
import type { AgentEvent } from "../types";

interface Props {
  events: AgentEvent[];
  running: boolean;
  ticketId: number | null;
}

function clock(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** The one-line human reading of an event. */
function describe(e: AgentEvent): { verb: React.ReactNode; detail?: React.ReactNode; tone?: string } {
  switch (e.event) {
    case "ticket_started":
      return { verb: <>picked up <b>ticket {e.ticket_id}</b></> };

    case "agent_started":
      return { verb: <>was asked to help</>, detail: e.task };

    case "delegation": {
      const to = lookOf(e.to_agent ?? "").label;
      return {
        verb: <>turned to <span className="hop-arrow">→</span> <b>{to}</b></>,
        detail: e.task,
      };
    }

    case "delegation_refused":
      return { verb: <>held back from delegating</>, detail: e.detail, tone: "refused" };

    case "tool_call": {
      const write = e.tool ? WRITE_TOOLS.has(e.tool) : false;
      const chipClass = !e.ok ? "failed" : write ? "write" : "";
      return {
        verb: (
          <>
            {toolPhrase(e.tool ?? "", e.arguments)}{" "}
            <span className={`tool-chip ${chipClass}`}>{e.tool}</span>
          </>
        ),
        detail: !e.ok ? e.detail : summariseResult(e.result),
        tone: e.ok ? undefined : "failed",
      };
    }

    case "agent_finished": {
      const out = e.result as { summary?: string } | null;
      return { verb: <>reported back</>, detail: out?.summary, tone: "speech" };
    }

    case "ticket_finished": {
      const out = e.result as { decision?: string } | null;
      return { verb: <>made the call</>, detail: out?.decision, tone: "speech" };
    }

    case "error":
      return { verb: <>hit a problem</>, detail: e.detail, tone: "failed" };

    default:
      return { verb: <>{e.event.replace(/_/g, " ")}</>, detail: e.detail };
  }
}

/** Pull the one or two numbers out of a tool result that a person would care about. */
function summariseResult(result: unknown): string | undefined {
  if (!result || typeof result !== "object") return undefined;
  const r = result as Record<string, unknown>;

  if (r.found === false || r.ok === false) return String(r.message ?? "not found");
  if ("on_hand" in r) return `${r.on_hand} on hand · short ${r.shortfall} · ${r.location}`;
  if ("monthly_rent" in r) return `$${Number(r.monthly_rent).toLocaleString()} due ${r.next_due} · ${r.days_until_due} days away`;
  if ("can_ship" in r) return r.can_ship ? `can ship · ${r.lead_days}-day lead` : String(r.blocking_reason ?? "blocked");
  if ("list_margin_pct" in r) return `$${Number(r.list_revenue).toLocaleString()} at list on $${Number(r.total_cost).toLocaleString()} cost · ${r.list_margin_pct}% margin · floor $${r.cost_floor_unit_price}`;
  if ("balance" in r && "account" in r) return `$${Number(r.balance).toLocaleString()} in ${r.account}`;
  if ("approval_id" in r && "affordable" in r) return `approval #${r.approval_id} queued · ${r.affordable ? "affordable" : "NOT affordable"} · nothing paid yet`;
  if ("draft_id" in r) return `draft #${r.draft_id} saved to the board — not sent`;
  if ("eta" in r) return `eta ${r.eta}`;
  if ("qty_after" in r) return `${r.qty_before} → ${r.qty_after}`;
  if ("count" in r) return `${r.count} row${r.count === 1 ? "" : "s"}`;
  return undefined;
}

export function Wire({ events, running, ticketId }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length]);

  return (
    <section className="wire">
      <div className="wire-head">
        <div>
          <h2>The wire</h2>
          <p className="sub">
            {ticketId ? `Everything the team does on ticket ${ticketId}, as it happens` : "Pick a ticket to watch the team work"}
          </p>
        </div>
        {running ? (
          <span className="live"><span className="bulb" />working</span>
        ) : (
          <span className="idle-note">{events.length ? `${events.length} entries` : "quiet"}</span>
        )}
      </div>

      <div className="feed">
        {events.length === 0 ? (
          <div className="feed-empty">
            <div className="big">✉</div>
            <p>
              The wire is quiet. Hand a ticket to the team and every lookup, hand-off and
              decision will land here in order.
            </p>
          </div>
        ) : (
          events.map((e) => {
            const look = lookOf(e.agent);
            const { verb, detail, tone } = describe(e);
            return (
              <div className={`line${tone ? ` ${tone}` : ""}`} data-depth={e.depth} key={`${e.run_id}-${e.seq}`}>
                <div className="monogram" style={{ background: look.bg, color: look.color }}>
                  {look.monogram}
                </div>
                <div className="line-body">
                  <div className="line-top">
                    <span
                      className={`agent-name${e.agent === "Boss" ? " is-boss" : ""}${e.agent.startsWith("human") ? " is-human" : ""}`}
                      style={{ color: look.color }}
                    >
                      {look.label}
                    </span>
                    <span className="verb">{verb}</span>
                    <span className="stamp-time">{clock(e.at_utc)}</span>
                  </div>
                  {detail && <div className="line-detail">{detail}</div>}
                </div>
              </div>
            );
          })
        )}
        <div ref={endRef} />
      </div>
    </section>
  );
}
