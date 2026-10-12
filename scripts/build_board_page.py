"""Build `output/resolved_board.html` — a double-clickable page of the finished board.

One section per ticket: the screenshot of the React desk showing that ticket's run, next to
the facts from `resolved_tickets.json` (final status, who worked it, what the human
approved, and what the cash did).

Expects the screenshots to already exist at `output/screenshots/ticket-<id>.jpg`.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
SHOTS = OUT / "screenshots"

CSS = """
:root{
  --rose-50:#fff8fa;--rose-75:#fff2f6;--rose-100:#ffeaf1;--rose-150:#ffdfe9;
  --rose-200:#ffd0e0;--rose-300:#f7b3cb;--rose-500:#e0638f;--rose-600:#c94d79;
  --rose-700:#a53a60;--ink:#3b2830;--ink-soft:#7b6671;--ink-faint:#a8949d;
  --paper:#fff;--line:#f7dde6;--ok:#2f8f6b;--stop:#c4445c;
  --shadow:0 1px 2px rgba(124,42,71,.05),0 12px 32px rgba(124,42,71,.09);
}
*{box-sizing:border-box}
body{
  margin:0;padding:46px 26px 90px;
  font:16px/1.65 "Inter",ui-sans-serif,-apple-system,"Segoe UI",system-ui,sans-serif;
  color:var(--ink);
  background:
    radial-gradient(1200px 560px at 10% -8%,var(--rose-150),transparent 58%),
    radial-gradient(900px 480px at 94% 2%,#fdeef6,transparent 52%),
    var(--rose-50);
}
.wrap{max-width:1180px;margin:0 auto}
.kicker{font-size:11px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--rose-600)}
h1{font-family:"Fraunces",ui-serif,Georgia,serif;font-size:38px;font-weight:600;letter-spacing:-.02em;margin:12px 0 6px}
.sub{color:var(--ink-soft);max-width:70ch;margin:0 0 22px}
.summary{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-bottom:38px;
}
.stat{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:15px 18px;box-shadow:var(--shadow)}
.stat .l{font-size:10.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--rose-600)}
.stat .v{font-family:"Fraunces",ui-serif,Georgia,serif;font-size:27px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums;margin-top:2px}
.stat .n{font-size:12px;color:var(--ink-soft)}
section{
  background:var(--paper);border:1px solid var(--line);border-radius:22px;
  box-shadow:var(--shadow);overflow:hidden;margin-bottom:30px;
}
.head{padding:20px 26px;border-bottom:1px solid var(--line);background:linear-gradient(var(--rose-75),var(--paper));display:flex;align-items:center;gap:13px;flex-wrap:wrap}
.no{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:var(--rose-700);background:var(--rose-100);border-radius:7px;padding:3px 9px}
.head h2{font-family:"Fraunces",ui-serif,Georgia,serif;font-size:21px;font-weight:600;margin:0}
.badge{margin-left:auto;font-size:11.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;padding:5px 13px;border-radius:99px}
.badge.resolved{color:#fff;background:linear-gradient(135deg,var(--rose-500),var(--rose-600))}
.badge.open{color:var(--stop);background:#fdeef1;border:1px solid #f8d6dd}
figure{margin:0;padding:22px 26px 6px;background:var(--rose-50)}
figure img{width:100%;display:block;border-radius:14px;border:1px solid var(--line);box-shadow:0 10px 30px rgba(124,42,71,.14)}
figcaption{font-size:12.5px;color:var(--ink-faint);padding:10px 2px 16px;text-align:center}
.body{padding:4px 26px 26px}
h3{font-size:11.5px;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--rose-600);margin:22px 0 10px}
.outcome{font-size:15px;margin:0 0 6px}
.why{font-size:13.5px;color:var(--ink-soft);margin:0}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--ink-faint);font-weight:700}
tbody tr:last-child td{border-bottom:none}
code{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:var(--rose-100);color:var(--rose-700);padding:1px 6px;border-radius:5px}
.agent{font-weight:600}
.money{font-variant-numeric:tabular-nums;font-weight:600}
.money.out{color:var(--stop)}
.none{color:var(--ink-faint);font-style:italic;font-size:13.5px}
footer{text-align:center;color:var(--ink-faint);font-size:13px;margin-top:34px}
"""

AGENT_HUE = {
    "Boss": "#a53a60", "Inventory": "#1f7a6b", "Accounting": "#9a6510",
    "Facilities": "#4a5bb5", "Customer Service": "#8b4bb8",
}


def money(n: float) -> str:
    return f"${n:,.2f}"


def esc(s) -> str:
    return html.escape(str(s or ""))


def main() -> int:
    data = json.loads((OUT / "resolved_tickets.json").read_text(encoding="utf-8"))
    cash = data["cash"]

    parts = [f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Campus Customs — The Resolved Board</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<span class="kicker">Campus Customs · New Haven</span>
<h1>The Resolved Board</h1>
<p class="sub">Every ticket after the full run, as it appeared on the React desk. The agents
analysed and prepared; a named human authorised every dollar that moved. Model:
<code>{esc(data['model'])}</code> · shop today <code>{esc(data['shop_date_today'])}</code>.</p>

<div class="summary">
  <div class="stat"><div class="l">Opening</div><div class="v">{money(cash['opening_balance_after_reset'])}</div><div class="n">after the reset</div></div>
  <div class="stat"><div class="l">Paid out</div><div class="v" style="color:var(--stop)">−{money(cash['total_paid_out'])}</div><div class="n">{data['totals']['payments_made']} payment(s), all human-approved</div></div>
  <div class="stat"><div class="l">Closing</div><div class="v">{money(cash['closing_balance'])}</div><div class="n">matches <code>cash_accounts</code></div></div>
  <div class="stat"><div class="l">Tickets</div><div class="v">{data['totals']['resolved']} / {data['totals']['tickets']}</div><div class="n">resolved</div></div>
  <div class="stat"><div class="l">Drafts</div><div class="v">{data['totals']['drafts_written']}</div><div class="n">written · {data['totals']['drafts_sent']} sent</div></div>
</div>
"""]

    for t in data["tickets"]:
        resolved = t["final_status"] != "open"
        shot = SHOTS / f"ticket-{t['id']}.jpg"
        img = (f'<figure><img src="screenshots/ticket-{t["id"]}.jpg" alt="The desk showing ticket {t["id"]}">'
               f'<figcaption>The React desk — ticket {t["id"]} after the run</figcaption></figure>'
               if shot.exists() else "")

        agents = "".join(
            f"<tr><td class='agent' style='color:{AGENT_HUE.get(a['agent'], '#7b6671')}'>{esc(a['agent'])}</td>"
            f"<td>{a['tool_calls']}</td>"
            f"<td>{''.join(f'<code>{esc(x)}</code> ' for x in a['tools_used'][:8]) or '<span class=none>—</span>'}</td>"
            f"<td>{esc(', '.join(a['delegated_to']) or '—')}</td>"
            f"<td>{esc(a['said'][-1] if a['said'] else '—')}</td></tr>"
            for a in t["agent_contributions"]
        )

        approvals = "".join(
            f"<tr><td>#{a['approval_id']}</td><td>{esc(a['kind'])} {esc(a['ref_id'])}</td>"
            f"<td class='money out'>−{money(a['amount'])}</td>"
            f"<td>{esc(a['approved_by'])}</td>"
            f"<td class='money'>{money(a['balance_before'])} → {money(a['balance_after'])}</td></tr>"
            for a in t["human_approvals"]
        ) or "<tr><td colspan='5' class='none'>No money moved on this ticket.</td></tr>"

        drafts = "".join(
            f"<tr><td>#{d['id']}</td><td>{esc(d['kind'].replace('_', ' '))}</td>"
            f"<td>{esc(d['audience'])}</td><td>{esc(d['subject'])}</td>"
            f"<td>{esc(d['created_by'])}</td><td>not sent</td></tr>"
            for d in t["drafts_written"]
        ) or "<tr><td colspan='6' class='none'>No drafts on this ticket.</td></tr>"

        parts.append(f"""
<section>
  <div class="head">
    <span class="no">#{t['id']}</span>
    <h2>{esc(t['subject'])}</h2>
    <span style="color:var(--ink-soft);font-size:13.5px">from {esc(t['requester'])}</span>
    <span class="badge {'resolved' if resolved else 'open'}">{esc(t['final_status'])}</span>
  </div>
  {img}
  <div class="body">
    <h3>Outcome</h3>
    <p class="outcome">{esc(t['outcome'])}</p>
    <p class="why">{esc(t['reasoning'])}</p>

    <h3>What each agent did</h3>
    <table><thead><tr><th>Agent</th><th>Calls</th><th>Tools used</th><th>Delegated to</th><th>Said</th></tr></thead>
    <tbody>{agents}</tbody></table>

    <h3>Human approvals</h3>
    <table><thead><tr><th>Approval</th><th>For</th><th>Amount</th><th>Approved by</th><th>Balance</th></tr></thead>
    <tbody>{approvals}</tbody></table>

    <h3>Drafts left on the board</h3>
    <table><thead><tr><th>Draft</th><th>Kind</th><th>To</th><th>Subject</th><th>By</th><th>Status</th></tr></thead>
    <tbody>{drafts}</tbody></table>

    <h3>Cash on this ticket</h3>
    <p class="outcome">
      <span class="money">{money(t['cash']['balance_before'])}</span> →
      <span class="money">{money(t['cash']['balance_after'])}</span>
      <span class="money {'out' if t['cash']['change'] < 0 else ''}">
        ({'−' if t['cash']['change'] < 0 else ''}{money(abs(t['cash']['change']))})
      </span>
    </p>
  </div>
</section>""")

    parts.append(f"""
<footer>Campus Customs · HW 5 · run {esc(data['started_utc'])} → {esc(data['finished_utc'])} ·
cash reconciles to <code>cash_accounts</code>: {cash['reconciles'] and cash['matches_cash_accounts_table']}</footer>
</div></body></html>
""")

    (OUT / "resolved_board.html").write_text("".join(parts), encoding="utf-8")
    missing = [t["id"] for t in data["tickets"] if not (SHOTS / f"ticket-{t['id']}.jpg").exists()]
    print("written output/resolved_board.html")
    print("screenshots missing for:", missing or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
