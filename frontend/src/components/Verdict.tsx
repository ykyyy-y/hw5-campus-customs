import { lookOf } from "../agents";
import type { AgentEvent, TicketDecision } from "../types";

interface Props {
  decision: TicketDecision;
  events: AgentEvent[];
}

/** What each agent actually did on this ticket: tools touched, time, tokens. */
function perAgent(events: AgentEvent[]) {
  const roster = new Map<string, { tools: Set<string>; calls: number; tokens: number }>();
  for (const e of events) {
    if (e.agent === "dashboard" || e.agent.startsWith("human")) continue;
    const row = roster.get(e.agent) ?? { tools: new Set<string>(), calls: 0, tokens: 0 };
    if (e.event === "tool_call" && e.tool) {
      row.tools.add(e.tool);
      row.calls += 1;
    }
    row.tokens += (e.tokens_in ?? 0) + (e.tokens_out ?? 0);
    roster.set(e.agent, row);
  }
  return [...roster.entries()];
}

export function Verdict({ decision, events }: Props) {
  const roster = perAgent(events);

  return (
    <div className="verdict">
      <h3>The call on ticket {decision.ticket_id}</h3>
      <p className="call">{decision.decision}</p>
      {decision.reasoning && <p className="why">{decision.reasoning}</p>}

      <div className="agent-cards">
        {roster.map(([name, row]) => {
          const look = lookOf(name);
          return (
            <div className="agent-card" key={name}>
              <div className="ac-top">
                <div className="monogram" style={{ background: look.bg, color: look.color, width: 24, height: 24, fontSize: 11 }}>
                  {look.monogram}
                </div>
                <span className="ac-name" style={{ color: look.color }}>{look.label}</span>
                <span className="ac-stat" style={{ marginLeft: "auto" }}>
                  {row.calls} call{row.calls === 1 ? "" : "s"}
                </span>
              </div>
              <div className="ac-tools">
                {[...row.tools].slice(0, 6).map((t) => (
                  <span key={t}>{t}</span>
                ))}
                {row.tools.size > 6 && <span>+{row.tools.size - 6}</span>}
              </div>
            </div>
          );
        })}
      </div>

      {decision.actions_taken.length > 0 && (
        <ul className="actions-list">
          {decision.actions_taken.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
