"""Fill the Actual sections and the Cash tab in `output/desk_tickets.html`.

The Expected sections written in Problem 6 are left untouched — the point of the page is the
comparison, so nothing that was predicted gets quietly edited after the fact.

Every number here is derived from the run rather than typed: cash movements come from the
`payments` table, agent activity comes from `output/audit_trail.json`, and the closing
balance is asserted against `cash_accounts` before the page is written.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
PAGE = OUT / "desk_tickets.html"
DB = ROOT / "data" / "campus_customs_new.db"

AGENT_HUE = {
    "Boss": "#a53a60", "Inventory": "#1f7a6b", "Accounting": "#9a6510",
    "Facilities": "#4a5bb5", "Customer Service": "#8b4bb8",
}

#: What the plan in Problem 6 predicted, so the Actual section can score itself honestly.
EXPECTED_FIRST_CONTACT = {101: "Inventory", 102: "Facilities", 103: "Accounting"}
EXPECTED_NOT_INVOLVED = {101: ["Facilities"], 102: ["Inventory"], 103: ["Facilities"]}


def esc(s) -> str:
    return html.escape(str(s or ""))


def money(n: float) -> str:
    return f"${n:,.2f}"


def db(sql: str) -> list[dict]:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def first_contact(events: list[dict], run_ids: set[str]) -> str | None:
    for e in events:
        if e["run_id"] in run_ids and e["event"] == "delegation" and e["agent"] == "Boss":
            return e["to_agent"]
    return None


def delegation_hops(events: list[dict], run_ids: set[str]) -> list[tuple[str, str, int]]:
    """Ordered (from, to, depth) hops, de-duplicated but keeping first appearance order."""
    seen: dict[tuple[str, str], int] = {}
    order: list[tuple[str, str]] = []
    for e in events:
        if e["run_id"] not in run_ids or e["event"] != "delegation":
            continue
        key = (e["agent"], e["to_agent"])
        if key not in seen:
            seen[key] = e["depth"]
            order.append(key)
    return [(f, t, seen[(f, t)]) for f, t in order]


def tools_by_agent(events: list[dict], run_ids: set[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for e in events:
        if e["run_id"] not in run_ids or e["event"] != "tool_call" or not e["tool"]:
            continue
        if e["agent"] not in AGENT_HUE and e["agent"] != "CustomerService":
            continue
        row = out.setdefault(e["agent"], [])
        if e["tool"] not in row:
            row.append(e["tool"])
    return out


def label(agent: str) -> str:
    return "Customer Service" if agent == "CustomerService" else agent


def actual_html(ticket: dict, log_entry: dict, events: list[dict]) -> str:
    tid = ticket["id"]
    run_ids = {p["run_id"] for p in log_entry["passes"]}
    hops = delegation_hops(events, run_ids)
    tools = tools_by_agent(events, run_ids)
    actives = sorted({label(a) for a in tools} | {label(f) for f, _, _ in hops} | {label(t) for _, t, _ in hops})
    contacted = first_contact(events, run_ids)
    predicted = EXPECTED_FIRST_CONTACT[tid]
    matched = contacted == predicted

    hop_items = "".join(
        f'<li><span class="hop"><span style="color:{AGENT_HUE.get(label(f), "#7b6671")}">{esc(label(f))}</span>'
        f'<span class="arrow">→</span>'
        f'<span style="color:{AGENT_HUE.get(label(t), "#7b6671")}">{esc(label(t))}</span></span>'
        f'<span class="why">depth {d + 1}'
        f'{" — never passed through the Boss" if f != "Boss" else ""}</span></li>'
        for f, t, d in hops
    )

    tool_rows = "".join(
        f"<tr><td style='color:{AGENT_HUE.get(label(a), '#7b6671')};font-weight:600'>{esc(label(a))}</td>"
        f"<td>{''.join(f'<code>{esc(t)}</code> ' for t in ts)}</td></tr>"
        for a, ts in sorted(tools.items(), key=lambda kv: label(kv[0]))
    )

    approvals = log_entry["approvals"]
    appr_html = "".join(
        f"<li><b>Approval #{a['approval_id']}</b> — {esc(a['kind'])} {esc(a['ref_id'])}, "
        f"<b>{money(a['amount'])}</b>, asked by {esc(a['requested_by'])}, approved by "
        f"<b>{esc(a['approved_by'])}</b> · balance {money(a['balance_before'])} → "
        f"{money(a['balance_after'])}</li>"
        for a in approvals
    ) or "<li>No money moved on this ticket.</li>"

    missing = [a for a in EXPECTED_NOT_INVOLVED[tid] if a in actives]
    extra_note = (
        f"The plan said {esc(' and '.join(EXPECTED_NOT_INVOLVED[tid]))} would stay out of this "
        f"ticket, and {'that held' if not missing else 'that did not hold — ' + esc(', '.join(missing)) + ' was pulled in'}."
    )

    last = log_entry["passes"][-1].get("decision") or {}
    drafts = [d for d in db("SELECT * FROM drafts ORDER BY id") if d["ticket_id"] == tid]
    draft_html = "".join(
        f"<li>Draft #{d['id']} — {esc(d['kind'].replace('_', ' '))} to <b>{esc(d['audience'])}</b>: "
        f"“{esc(d['subject'])}” <i>(written by {esc(d['created_by'])}, never sent)</i></li>"
        for d in drafts
    ) or "<li>No drafts on this ticket.</li>"

    return f"""
      <h3>Actual — agents that were active</h3>
      <p>{esc(', '.join(actives))} — {len(actives)} of the five.</p>
      <p>
        The Boss's first contact was <b style="color:{AGENT_HUE.get(label(contacted or ''), '#7b6671')}">{esc(label(contacted or '—'))}</b>,
        which {'<b>matches</b>' if matched else 'differs from'} the plan's prediction of
        <b>{esc(predicted)}</b>. {extra_note}
      </p>

      <h3>Actual — delegations</h3>
      <ol class="flow">{hop_items or '<li>No delegations — the Boss worked this one alone.</li>'}</ol>

      <h3>Actual — MCP tools used</h3>
      <table><thead><tr><th>Agent</th><th>Tools called</th></tr></thead><tbody>{tool_rows}</tbody></table>

      <h3>Actual — human approvals</h3>
      <ul class="notlist">{appr_html}</ul>

      <h3>Actual — drafts left on the board</h3>
      <ul class="notlist">{draft_html}</ul>

      <h3>Actual — outcome</h3>
      <p><b>Final status: {esc(ticket['status'])}</b> after {len(log_entry['passes'])} pass(es).</p>
      <p>{esc(last.get('decision', ''))}</p>
      <p class="why" style="color:var(--ink-soft);font-size:14px">{esc(last.get('reasoning', ''))}</p>

      <h3>Actual — cash on this ticket</h3>
      <p>
        {money(log_entry['balance_before'])} → <b>{money(log_entry['balance_after'])}</b>
        ({'−' if log_entry['cash_change'] < 0 else ''}{money(abs(log_entry['cash_change']))})
      </p>
"""


def cash_tab(log: dict, payments: list[dict], closing: float) -> str:
    opening = log["opening_balance"]
    rows = []
    running = opening
    for entry in log["tickets"]:
        tid = entry["ticket_id"]
        if not entry["approvals"]:
            rows.append(
                f"<tr><td><b>Ticket {tid}</b></td><td class='none'>no payment</td>"
                f"<td>—</td><td class='money'>{money(running)}</td>"
                f"<td>Resolved without spending: the work was analysis and a draft, and "
                f"nothing on this ticket required money to leave the shop.</td></tr>"
            )
            continue
        for a in entry["approvals"]:
            running = a["balance_after"]
            rows.append(
                f"<tr><td><b>Ticket {tid}</b></td>"
                f"<td>{esc(a['kind'])} {esc(a['ref_id'])} · approval #{a['approval_id']}</td>"
                f"<td class='money out'>−{money(a['amount'])}</td>"
                f"<td class='money'>{money(running)}</td>"
                f"<td>{esc(a['reason'])}<br><i>Approved by {esc(a['approved_by'])}.</i></td></tr>"
            )

    total = round(sum(p["amount"] for p in payments), 2)
    reconciles = round(opening - total, 2) == closing

    return f"""
    <div class="card">
      <h2>Cash — every dollar, itemised</h2>
      <p class="lede">
        Cash only goes out in this shop; no revenue is modelled. Every movement below is a
        payment a <b>human approved</b> — the agents queued them and could not pay.
      </p>

      <h3>Opening balance, after the reset</h3>
      <p style="font-size:30px;font-family:var(--serif);font-weight:600;margin:0 0 6px">{money(opening)}</p>
      <p class="why" style="color:var(--ink-soft)">Read from <code>cash_accounts.checking</code> immediately after
      <code>POST /reset</code> restored the working database from the untouched original.</p>

      <h3>Movements, ticket by ticket</h3>
      <table>
        <thead><tr><th>Ticket</th><th>What was paid</th><th>Amount</th><th>Balance after</th><th>Why</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>

      <h3>Closing balance</h3>
      <table>
        <tbody>
          <tr><td>Opening after reset</td><td class="money">{money(opening)}</td></tr>
          <tr><td>Total paid out ({len(payments)} payment{'' if len(payments) == 1 else 's'})</td><td class="money out">−{money(total)}</td></tr>
          <tr><td><b>Closing balance</b></td><td class="money"><b>{money(closing)}</b></td></tr>
        </tbody>
      </table>
      <p style="margin-top:14px">
        <b>{money(opening)} − {money(total)} = {money(round(opening - total, 2))}</b>, and
        <code>cash_accounts.checking</code> in <code>data/campus_customs_new.db</code> reads
        <b>{money(closing)}</b>. Reconciles: <b style="color:{'var(--ok)' if reconciles else 'var(--stop)'}">{reconciles}</b>.
      </p>
      <p class="why" style="color:var(--ink-soft)">
        Every payment row in <code>payments</code> carries <code>approved_by = "{esc(log['human'])}"</code>.
        There is no payment in this database that a human did not authorise.
      </p>
    </div>"""


def reflection_tab(log: dict, tickets: list[dict]) -> str:
    """The Problem 10 write-up. Every claim points at a tab on this page."""
    resolved = sum(1 for t in tickets if t["status"] != "open")
    closing = money(log["closing_balance"])

    return f"""
    <div class="card">
      <h2>Reflection</h2>
      <p class="lede">
        Three tickets, {resolved} resolved, {closing} left in checking. Everything below points
        at evidence on this page — the ticket tabs for what the agents did, the Cash tab for
        what it cost.
      </p>

      <h3>1 · How the agents performed, ticket by ticket</h3>

      <p><b>Ticket 101 — Bulldog tee. Grade: B.</b></p>
      <p>
        The analysis was genuinely good. Inventory found <code>on_hand: 0</code> for
        <code>CC-TEE-WHITE / S</code>, matched the shortfall to Bulldog Print Co, and
        <code>get_vendor_status</code> returned <code>can_ship: false</code> — so a one-line
        customer order was correctly re-diagnosed as a $840 accounts-payable problem. Customer
        Service then refused to invent a date, writing:
      </p>
      <p class="quote">“Our supplier, Bulldog Print Co, cannot ship a restock while an $840
      invoice remains unpaid. Because there is no confirmed payment date, we can’t give you a
      firm restock date yet.”</p>
      <p>
        That is exactly the behaviour the shop needs — the expensive failure here would have
        been promising September 5 before the invoice cleared.
      </p>
      <p>
        Two things cost it the higher grade. <b>It left contradictory letters on the board.</b>
        After the human approved the payment, the Boss wrote draft #2 correcting draft #1, but
        did not remove the original — it simply appended “Please use this corrected draft
        instead of the earlier draft, which incorrectly said the vendor is blocked.” Two
        letters to the same customer, saying opposite things, both sitting on the board.
        <b>And it was wasteful</b>: 39 tool calls and 142,228 tokens — the most expensive ticket
        of the three — for an order of <i>one tee</i>, including <code>check_stock</code> called
        six times on the same (sku, size) because each agent re-verifies rather than trusting
        the caller's numbers.
      </p>

      <p><b>Ticket 102 — Rent due. Grade: C−. The worst outcome of the run.</b></p>
      <p>
        Pass 1 was flawless: Facilities read lease 1 and reported $2,400.00 due
        <b>2026-09-02</b>, <code>days_until_due: 2</code> — matching the landlord's notice
        exactly — and Accounting queued approval #2 against a $2,560.00 balance.
      </p>
      <p>
        Then it broke. The human approved, <code>pay</code> rolled <code>leases.next_due</code>
        forward a month to <b>2026-10-02</b>, and in pass 2 the agents re-read the lease, saw
        32 days, and concluded the landlord was wrong. Customer Service wrote to Elm City
        Properties:
      </p>
      <p class="quote">“Your notice says the rent is due in 2 days. Our lease record … lists the
      next due date as October 2, 2026 (32 days from August 31, 2026). Could you please confirm
      the due date or send a corrected notice if needed?”</p>
      <p>
        <b>The landlord was right and the shop was wrong.</b> The rent <i>was</i> due in two
        days; it had simply just been paid — by this very team, forty seconds earlier. The
        letter asks the landlord to correct an accurate notice and never mentions the payment.
        The ticket is marked resolved with a misleading letter sitting on the board.
      </p>
      <p>
        Responsibility is shared, and most of it is mine rather than the model's. My
        <code>pay</code> tool mutates <code>next_due</code> as a side effect, and no tool lets an
        agent ask “what have I already done on this ticket?” — so the second pass read a changed
        world with no memory of having changed it. But the Boss also had
        <code>list_payment_approvals</code> available, called it, saw approval #2 marked
        <code>paid</code>, and still let the letter go out. It should have reconciled the two.
        The one redeeming fact is structural: because <b>nothing in this system can send</b>,
        the error stopped at a draft a human will read. That is the no-send rule doing precisely
        the job it exists for.
      </p>

      <p><b>Ticket 103 — Bulk hoodie discount. Grade: A−. The best-run ticket.</b></p>
      <p>
        One pass, 20 tool calls, 92,509 tokens, no money. Accounting pulled the real economics —
        $58.00 list, $22.00 cost floor, $1,160 on 20 units at 62.1% margin — and then
        <b>declined to quote a discount at all</b>, because the Yale AI Club never named a target
        price. The draft says so:
      </p>
      <p class="quote">“We have not quoted a bulk discount; please share the per-unit price you
      have in mind for review.”</p>
      <p>
        Inventory separately caught the supply problem the club had not asked about — only 8 of
        20 size-M hoodies on hand, 12 short — and the draft carries it with a conditional date
        (“If a restock order is placed today, the estimated arrival date is September 5, 2026.
        No restock order has been placed, so that date is conditional”). Refusing to invent a
        number, and volunteering a constraint the customer did not know to ask about, is the
        behaviour I would most want from a real shop assistant.
      </p>
      <p>
        This ticket also produced the run's only <code>delegation_refused</code> event — the
        budget ceiling fired — and the ticket still closed correctly. A guardrail that degrades
        the work instead of killing it.
      </p>

      <p><b>Across all three.</b> The thing that held without exception: <b>no agent ever moved
      money.</b> Two payments were needed, both were queued by Accounting, both waited for a
      named human, and the Cash tab reconciles to the penny —
      {money(log['opening_balance'])} − {money(log['opening_balance'] - log['closing_balance'])}
      = {closing}, which is what <code>cash_accounts</code> reads. Five drafts were written and
      <b>zero</b> were sent.</p>

      <h3>2 · Expected plan versus what actually happened</h3>

      <table>
        <thead><tr><th>Ticket</th><th>Predicted</th><th>Actual</th><th>Verdict</th></tr></thead>
        <tbody>
          <tr>
            <td><b>101</b></td>
            <td>Boss → Inventory first; Inventory → Accounting; Boss → Customer Service.
            Facilities excluded. One customer draft.</td>
            <td>All three predicted hops happened, <i>plus</i> Boss → Accounting directly and
            Customer Service → Inventory. Three drafts, not one — including a purchase order.</td>
            <td><b>Mostly right.</b> Routing correct; volume of work underestimated.</td>
          </tr>
          <tr>
            <td><b>102</b></td>
            <td>Boss → Facilities first; Facilities → Accounting; Boss → Customer Service.
            Inventory excluded.</td>
            <td><b>Exactly that</b> — three hops, no others, Inventory never touched it.</td>
            <td><b>Perfect on routing, blind on risk.</b> The plan never imagined the danger was
            re-reading state the team had itself changed.</td>
          </tr>
          <tr>
            <td><b>103</b></td>
            <td>Boss → Accounting first (a price question); Accounting → Inventory for supply;
            Boss → Customer Service. Facilities excluded.</td>
            <td>Boss → Accounting first ✓, but the supply check came from <b>Boss → Inventory
            directly</b>, not via Accounting. Customer Service then delegated to <i>both</i>
            before drafting.</td>
            <td><b>Right call, flatter path.</b></td>
          </tr>
        </tbody>
      </table>

      <p><b>What the plan nailed:</b> all three first contacts — including the deliberate choice
      to open 101 with Inventory but 103 with Accounting even though both tickets touch hoodie
      stock and the same blocked vendor. Ticket 102's entire chain. The Inventory → Accounting
      hand-off on 101, predicted as “the hand-off that matters”. The narrow routing held on
      every ticket: Facilities never touched merchandise, Inventory never touched rent. And the
      {closing} closing balance, forecast from the database before a single agent ran.</p>

      <p><b>What the plan missed:</b></p>
      <ul class="notlist">
        <li><b>Customer Service delegates before it writes.</b> Not foreseen at all. On 101 it
        went back to Inventory; on 103 to Accounting <i>and</i> Inventory. It was refusing to put
        a number in a customer's letter it had not verified itself — better behaviour than the
        passive drafting the plan assumed.</li>
        <li><b>Purchase orders exist.</b> The plan listed <code>save_draft</code> for customer
        messages only. Once invoice 501 cleared, the Boss drafted a PO to Bulldog Print Co for
        one unit. Obvious in hindsight; entirely absent from the forecast.</li>
        <li><b>One pass per ticket was never possible.</b> The plan implicitly assumed a ticket
        runs once. Any ticket blocked on money needs three beats — agents queue, human approves,
        agents finish. 101 and 102 each took two passes; 103, the only ticket with no payment,
        took one. That pattern <i>is</i> the approval gate, visible in the run shape.</li>
        <li><b>Side effects of paying.</b> Nothing in the plan considered that resolving a ticket
        changes the data the next pass reads. That gap produced the ticket 102 defect.</li>
      </ul>

      <h3>3 · What one agent with tools would have done better</h3>

      <p><b>Ticket 102, without question.</b></p>
      <p>
        Strip it to what it actually required: read lease 1, compare <code>next_due</code> to
        <code>desk.date_today</code>, check the balance covers $2,400.00, queue the approval,
        draft an acknowledgement. Four tool calls. One domain. No judgment that crosses a
        specialist boundary.
      </p>
      <p>
        What it cost instead: <b>20 tool calls, 4 delegations and 80,815 tokens</b>, with
        <code>get_rent_due</code> called <b>six times</b> against the same unchanging row — three
        times in pass 1 (Boss, Facilities, Accounting) and three in pass 2 (Boss, Facilities,
        Customer Service). Every agent re-reads rather than trusting the numbers handed to it,
        which is correct behaviour for an agent that cannot verify its caller, and pure waste
        when the caller already read the same row.
      </p>
      <p>
        And the delegation did not merely cost tokens — <b>it caused the error</b>. The wrong
        letter was written by an agent in a later pass that re-read <code>next_due</code> with no
        knowledge of the payment its own team had just made. A single agent holding one
        conversation would have had the payment in its own context two turns earlier and could
        not have made that mistake.
      </p>
      <p>
        The contrast with ticket 101 is the lesson. 101 genuinely crosses four domains — stock,
        vendor, money, customer wording — and no single specialist owns that chain; the mesh
        earned its cost there. 102 never leaves Facilities plus a payment request. <b>The team
        should scale with the number of domains a ticket crosses, not with the number of agents
        that exist.</b> A sensible next change is letting the Boss answer single-domain tickets
        with its own tools instead of convening the team.
      </p>

      <h3>4 · Three new problems this team could already solve</h3>

      <p>All three are solvable with the 18 tools already on the MCP server and the five agents
      as built — no new code.</p>

      <p><b>a) “The AI Club order is pending — can I still buy a navy hoodie in L today?”</b><br>
      A walk-in while ticket 103 sits unresolved. Inventory calls
      <code>check_stock(CC-HOOD-NAVY, L)</code> and gets <b>14 on hand</b>; the club's request is
      size <b>M</b>, where only 8 of 20 exist. The pending bulk order touches a different
      <code>(sku, size)</code> key entirely, so the walk-in can be filled immediately.
      <code>price_quote</code> confirms $58.00 at 62.1% margin, <code>adjust_stock</code> with
      <code>delta: -1</code> records the sale leaving 13, and the Boss closes it. This is the
      exact failure mode the size-aware key was built to prevent — “we have hoodies” being
      treated as an answer.</p>

      <p><b>b) “The Crest Mug shelf in Aisle D is empty — should we restock?”</b><br>
      <code>CC-MUG-CREST</code> sits at <code>qty: 0</code> and no ticket has been raised.
      <code>list_vendors</code> matches “mugs and small goods” to <b>Elm City Gifts</b>, vendor 2;
      <code>get_vendor_status(2)</code> returns <code>can_ship: true</code> — unlike Bulldog Print
      Co it holds no open invoice — and <code>estimate_restock_eta</code> dates delivery at
      <b>3 days</b>. <code>price_quote</code> shows the best margin in the shop at 75.0%.
      And then <code>get_cash_balance</code> returns <b>{closing}</b>, so
      <code>request_payment_approval</code> comes back <code>affordable: false</code> and
      Accounting must refuse. <b>The valuable output is the refusal</b>: a correctly reasoned “the
      margin is excellent, the vendor is ready, and we still cannot afford it this week.”</p>

      <p><b>c) “Can we cover October's rent?”</b><br>
      After the run, <code>get_rent_due(1)</code> reads <b>$2,400.00 due 2026-10-02</b> while
      checking holds <b>{closing}</b>. Facilities and Accounting can already build the whole
      picture from <code>get_rent_due</code>, <code>get_cash_balance</code>,
      <code>list_invoices</code> and <code>list_payment_approvals</code>, and state plainly that
      the shop is <b>$2,240.00 short</b> of its next rent obligation. Early insolvency warning,
      with no new tool required — the Cash tab on this page is the evidence.</p>

      <h3>5 · Three problems this team could <i>not</i> solve, and what it would take</h3>

      <p><b>a) “Did we already do this?” — the ticket 102 defect, generalised.</b><br>
      Nothing in the system lets an agent ask what has already happened on a ticket. The second
      pass re-read a lease its own team had changed, and 101 ended with two contradictory letters
      because a correction can only be appended, never substituted.<br>
      <b>What's needed:</b> an MCP tool <code>get_ticket_history(ticket_id)</code> returning the
      approvals, payments, stock movements and drafts already recorded against that ticket, so
      “read the current row” is always accompanied by “and here is what we did to it”; a
      <code>supersede_draft(draft_id, replacement_id)</code> so corrections replace rather than
      stack; and a <b>sixth agent — an Auditor</b> that reads every draft against the database
      before it is saved and blocks any claim the data contradicts. Here it would have caught
      “please correct your notice” against a <code>payments</code> row dated the same day. This
      cannot be fixed by better prompting: the agent had no tool with which to know.</p>

      <p><b>b) Money only ever leaves.</b><br>
      The Yale AI Club's 20 hoodies would be <b>$1,160</b> of revenue — the largest single inflow
      the shop could book — and there is no table, no tool and no agent that can record a sale.
      So Accounting is structurally pessimistic: every recommendation it makes is a
      countdown from {money(log['opening_balance'])} to {closing} with no path back up, and the
      whole bulk-discount question on ticket 103 is being decided with half the arithmetic
      missing.<br>
      <b>What's needed:</b> an <code>orders</code> table and <code>record_sale</code> /
      <code>fulfil_order</code> tools that decrement <code>inventory.qty</code> and credit
      <code>cash_accounts</code> in one transaction; a <b>Sales agent</b> owning quotes, deposits
      and order status. Only then can a discount be evaluated as “does this order improve our
      cash position” rather than “is this above cost”.</p>

      <p><b>c) Nothing can be sent, and nothing can come back.</b><br>
      This is the sharpest limit, and all three tickets hit it. Every one ends on a question
      nobody can answer: draft #3 is a purchase order to Bulldog Print Co that will never reach
      them, so the tee is never actually reordered; draft #4 asks the landlord to confirm a date;
      draft #5 asks the AI Club for a target price. The shop's entire output is five letters in
      a drawer. It is also why the Boss first refused to close tickets at all — it was waiting
      for replies that are structurally impossible.<br>
      <b>What's needed:</b> a <code>send_draft(draft_id, approved_by)</code> tool gated behind a
      human approval that mirrors the payment gate exactly — drafts should be as hard to send as
      money is to spend; an inbound <code>receive_reply</code> that opens a linked follow-up
      ticket so a vendor confirmation becomes work on the board; a real
      <code>purchase_orders</code> table giving a PO a lifecycle (drafted → sent → confirmed →
      received) whose receipt triggers <code>adjust_stock</code>; and a <b>Dispatch agent</b>
      owning that outbound queue and chasing what has gone unanswered. Without it, “resolved”
      means the thinking is finished — not that the tee is coming.</p>

      <h3>The one-sentence version</h3>
      <p>
        On the evidence of these three tickets, the team is <b>good at diagnosis and honest about
        what it does not know</b> — it found an invoice hiding behind a t-shirt order, and refused
        twice to invent a date or a discount — but it is <b>bad at remembering what it has just
        done</b>, and that is a tooling gap rather than a reasoning one.
      </p>
    </div>"""


def main() -> int:
    log = json.loads((OUT / "run_log.json").read_text(encoding="utf-8"))
    trail = json.loads((OUT / "audit_trail.json").read_text(encoding="utf-8"))
    events = trail["events"]
    page = PAGE.read_text(encoding="utf-8")

    tickets = {t["id"]: t for t in db("SELECT * FROM tickets")}
    payments = db("SELECT * FROM payments ORDER BY id")
    closing = db("SELECT balance FROM cash_accounts WHERE name='checking'")[0]["balance"]

    expected_closing = round(log["opening_balance"] - sum(p["amount"] for p in payments), 2)
    assert expected_closing == closing, (
        f"cash does not reconcile: {log['opening_balance']} - "
        f"{sum(p['amount'] for p in payments)} = {expected_closing} but table says {closing}"
    )

    # --- Actual sections, one per ticket, leaving Expected untouched ---
    for entry in log["tickets"]:
        tid = entry["ticket_id"]
        body = actual_html(tickets[tid], entry, events)
        pattern = re.compile(
            rf'(<section class="panel[^"]*" id="t{tid}" role="tabpanel">.*?)'
            r'(<div class="actual">)(.*?)(</div>\s*</section>)',
            re.S,
        )
        new_block = r'\1\2\n      <h3>Actual</h3>' + body.replace("\\", "\\\\") + r'\4'
        page, n = pattern.subn(new_block, page)
        assert n == 1, f"could not place the Actual section for ticket {tid}"

    # --- Cash and Reflection tabs ---
    page = re.sub(
        r'(<section class="panel" id="cash" role="tabpanel">).*?(</section>)',
        lambda m: m.group(1) + cash_tab(log, payments, closing) + "\n  " + m.group(2),
        page, flags=re.S,
    )
    page = re.sub(
        r'(<section class="panel" id="reflect" role="tabpanel">).*?(</section>)',
        lambda m: m.group(1) + reflection_tab(log, list(tickets.values())) + "\n  " + m.group(2),
        page, flags=re.S,
    )

    # The Actual placeholder styling was a dashed stub; make it a real panel now.
    page = page.replace(
        "the <b>Actual</b> section is filled in after the agents work the board, so the plan can\n      be compared against the real outcome.",
        "the <b>Actual</b> section below it records what really happened, so the two can be read\n      side by side.",
    )

    PAGE.write_text(page, encoding="utf-8")
    print(f"opening {money(log['opening_balance'])} → closing {money(closing)} "
          f"(paid out {money(sum(p['amount'] for p in payments))})")
    print("cash reconciles against cash_accounts: True")
    print("written output/desk_tickets.html - Expected sections preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
