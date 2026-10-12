import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { CashDrawer } from "./components/CashDrawer";
import { TicketCard } from "./components/TicketCard";
import { Verdict } from "./components/Verdict";
import { Wire } from "./components/Wire";
import type { AgentEvent, Approval, CashResponse, RunState, Ticket } from "./types";

/** How often the board asks the backend what the agents have done since last time. */
const POLL_MS = 1200;

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [today, setToday] = useState("");
  const [cash, setCash] = useState<CashResponse | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);

  const [selected, setSelected] = useState<number | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);

  const [approver, setApprover] = useState("Yookyung Eom");
  const [deciding, setDeciding] = useState<number | null>(null);
  const [toast, setToast] = useState<{ text: string; bad?: boolean } | null>(null);
  const [offline, setOffline] = useState(false);

  const lastSeq = useRef<number | null>(null);
  const running = run?.status === "running";

  const say = (text: string, bad = false) => {
    setToast({ text, bad });
    setTimeout(() => setToast(null), 5200);
  };

  /** Ticket list, cash and the approval queue — everything except the live feed. */
  const refreshDesk = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()]);
      setTickets(t.tickets);
      setToday(t.today);
      setCash(c);
      setApprovals(a);
      setOffline(false);
      setSelected((s) => s ?? t.tickets[0]?.id ?? null);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    refreshDesk();
  }, [refreshDesk]);

  /** While a run is live, pull only what is new and append it to the wire. */
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const page = await api.events(runId, lastSeq.current);
        if (cancelled) return;
        if (page.events.length) {
          setEvents((prev) => [...prev, ...page.events]);
          lastSeq.current = page.latest_seq ?? lastSeq.current;
        }
        if (page.run) setRun(page.run);
        if (page.run && page.run.status !== "running") {
          await refreshDesk();
          say(
            page.run.status === "error"
              ? `The run stopped: ${page.run.error}`
              : `Ticket ${page.run.ticket_id} — the team has made its call.`,
            page.run.status === "error",
          );
          return; // stop polling
        }
      } catch {
        setOffline(true);
      }
      if (!cancelled) timer = setTimeout(tick, POLL_MS);
    };

    let timer = setTimeout(tick, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [runId, refreshDesk]);

  /** Selecting a ticket replays what the team did on it, from the audit trail. */
  const showHistory = useCallback(
    async (ticketId: number) => {
      setSelected(ticketId);
      if (running) return;
      try {
        const [page, runList] = await Promise.all([api.events(), api.runs()]);
        const forTicket = page.events.filter((e) => e.ticket_id === ticketId);
        setEvents(forTicket);
        const last = runList.runs.find((r) => r.ticket_id === ticketId && r.decision);
        setRun(last ?? null);
        setRunId(null);
      } catch {
        setOffline(true);
      }
    },
    [running],
  );

  const handleRun = async (ticketId: number) => {
    setSelected(ticketId);
    setEvents([]);
    lastSeq.current = null;
    try {
      const started = await api.runTicket(ticketId);
      setRunId(started.run_id);
      setRun({
        run_id: started.run_id,
        ticket_id: ticketId,
        status: "running",
        started_utc: new Date().toISOString(),
        finished_utc: null,
        decision: null,
        error: null,
      });
      say(`Ticket ${ticketId} handed to the team.`);
    } catch (err) {
      say(err instanceof Error ? err.message : "Could not start the run.", true);
    }
  };

  const handleDecide = async (approvalId: number, decision: "approve" | "reject") => {
    setDeciding(approvalId);
    try {
      const result = await api.decide(approvalId, decision, approver.trim());
      say(result.message, !result.ok);
      await refreshDesk();
    } catch (err) {
      say(err instanceof Error ? err.message : "That decision did not go through.", true);
    } finally {
      setDeciding(null);
    }
  };

  const handleReset = async () => {
    try {
      await api.reset();
      setEvents([]);
      setRun(null);
      setRunId(null);
      lastSeq.current = null;
      await refreshDesk();
      say("Shop reset — tickets reopened, cash back to $3,400.00.");
    } catch (err) {
      say(err instanceof Error ? err.message : "Reset failed.", true);
    }
  };

  const openCount = tickets.filter((t) => t.status === "open").length;
  const pendingCount = approvals.filter((a) => a.status === "pending").length;

  return (
    <div className="desk">
      <header className="masthead">
        <div className="brand">
          <span className="kicker">Campus Customs · New Haven</span>
          <h1>The Desk</h1>
          <p className="tagline">Five agents work the board. You hold the chequebook.</p>
        </div>
        <div className="masthead-right">
          <span className="stamp-date">
            shop today · <b>{today || "—"}</b>
          </span>
          <span className="pill">
            <b>{openCount}</b> open
          </span>
          {pendingCount > 0 && (
            <span className="pill">
              <b>{pendingCount}</b> awaiting you
            </span>
          )}
          <button className="ghost-btn" onClick={handleReset} disabled={running}>
            Reset the shop
          </button>
        </div>
      </header>

      {offline && (
        <div className="quiet-panel" style={{ marginBottom: 18 }}>
          The desk cannot reach the backend. Start it with{" "}
          <code>uvicorn main:app --reload --port 8000</code> from the <code>backend/</code> folder.
        </div>
      )}

      <div className="columns">
        {/* ---------------- the board ---------------- */}
        <div>
          <div className="col-head">
            <h2>On the board</h2>
            <span className="count">{tickets.length} tickets</span>
          </div>
          {tickets.map((t) => (
            <TicketCard
              key={t.id}
              ticket={t}
              selected={selected === t.id}
              busy={running}
              running={running && run?.ticket_id === t.id}
              onSelect={() => showHistory(t.id)}
              onRun={() => handleRun(t.id)}
            />
          ))}
        </div>

        {/* ---------------- the wire ---------------- */}
        <div>
          <Wire events={events} running={running} ticketId={run?.ticket_id ?? selected} />
          {run?.decision && <Verdict decision={run.decision} events={events} />}
        </div>

        {/* ---------------- the cash drawer ---------------- */}
        <div className="col-cash">
          <CashDrawer
            cash={cash}
            approvals={approvals}
            approver={approver}
            onApproverChange={setApprover}
            onDecide={handleDecide}
            deciding={deciding}
          />
        </div>
      </div>

      {toast && <div className={`toast${toast.bad ? " bad" : ""}`}>{toast.text}</div>}
    </div>
  );
}
