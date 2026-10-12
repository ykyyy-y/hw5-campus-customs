import { useEffect, useRef, useState } from "react";
import type { Approval, CashResponse } from "../types";

interface Props {
  cash: CashResponse | null;
  approvals: Approval[];
  approver: string;
  onApproverChange: (v: string) => void;
  onDecide: (id: number, decision: "approve" | "reject") => void;
  deciding: number | null;
}

const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

export function CashDrawer({ cash, approvals, approver, onApproverChange, onDecide, deciding }: Props) {
  // The balance flashes and shakes when it falls, because a payment leaving the
  // account is the single most consequential thing on this screen.
  const [dropping, setDropping] = useState(false);
  const previous = useRef<number | null>(null);

  useEffect(() => {
    if (cash == null) return;
    if (previous.current != null && cash.balance < previous.current) {
      setDropping(true);
      const timer = setTimeout(() => setDropping(false), 1400);
      previous.current = cash.balance;
      return () => clearTimeout(timer);
    }
    previous.current = cash.balance;
  }, [cash?.balance]);

  const pending = approvals.filter((a) => a.status === "pending");
  const settled = approvals.filter((a) => a.status !== "pending");

  return (
    <>
      <div className="drawer">
        <div className="drawer-head">
          <span className="label">Checking</span>
        </div>
        <div className={`balance${dropping ? " dropping" : ""}`}>
          {cash ? money(cash.balance) : "—"}
        </div>
        <div className="balance-sub">
          {cash ? `as of ${cash.as_of}` : "waiting for the desk"}
        </div>

        {cash && (
          <div className="tape">
            <div className="tape-row">
              <span>paid out so far</span>
              <b>{money(cash.paid_out_total)}</b>
            </div>
            <div className="tape-row">
              <span>awaiting your call</span>
              <b>{money(cash.pending_total)}</b>
            </div>
            <div className="tape-row">
              <span>left if you approve all</span>
              <b style={{ color: cash.balance_if_all_pending_approved < 0 ? "var(--stop)" : undefined }}>
                {money(cash.balance_if_all_pending_approved)}
              </b>
            </div>
            <p className="tape-note">Cash only goes out here — nothing refills it.</p>
          </div>
        )}
      </div>

      <div className="col-head">
        <h2>Awaiting your approval</h2>
        <span className="count">{pending.length}</span>
      </div>

      {pending.length > 0 && (
        <input
          className="who-field"
          value={approver}
          onChange={(e) => onApproverChange(e.target.value)}
          placeholder="Your name — goes on the payment record"
          aria-label="Approver name"
        />
      )}

      {pending.length === 0 ? (
        <div className="quiet-panel">
          Nothing is waiting on you. The agents will queue anything that costs money.
        </div>
      ) : (
        pending.map((a) => (
          <div className="slip pending" key={a.id}>
            <div className="slip-top">
              <span className="slip-amount">{money(a.amount)}</span>
              <span className="slip-kind">{a.kind}</span>
            </div>
            <div className="slip-meta">
              #{a.id} · {a.kind} {a.ref_id} · asked by {a.requested_by}
              {a.ticket_id ? ` · ticket ${a.ticket_id}` : ""}
            </div>
            {a.reason && <p className="slip-why">{a.reason}</p>}
            <div className="slip-buttons">
              <button
                className="approve"
                disabled={deciding === a.id || !approver.trim()}
                onClick={() => onDecide(a.id, "approve")}
              >
                {deciding === a.id ? "Paying…" : "Approve & pay"}
              </button>
              <button className="reject" disabled={deciding === a.id} onClick={() => onDecide(a.id, "reject")}>
                Decline
              </button>
            </div>
          </div>
        ))
      )}

      <p className="gate-note" style={{ marginTop: 12 }}>
        <b>No agent can approve a payment.</b> They can only prepare one — the tool that
        authorises money is kept off every agent's toolset and lives here, with you.
      </p>

      {settled.length > 0 && (
        <>
          <div className="col-head" style={{ marginTop: 22 }}>
            <h2>Settled</h2>
            <span className="count">{settled.length}</span>
          </div>
          {settled.map((a) => (
            <div className="slip" key={a.id}>
              <div className="slip-top">
                <span className="slip-amount" style={{ fontSize: 18 }}>{money(a.amount)}</span>
                <span className="slip-kind">{a.kind} {a.ref_id}</span>
              </div>
              <div className={`slip-settled${a.status === "rejected" ? " rejected" : ""}`}>
                {a.status === "paid" ? "✓ paid" : a.status === "rejected" ? "✕ declined" : a.status}
                {a.decided_by ? ` · by ${a.decided_by}` : ""}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  );
}
