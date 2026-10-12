# The Desk — design notes

**Campus Customs · HW 5 · the React dashboard in `frontend/`**

This is not an admin panel with a table of rows. It is a **desk** — the counter a shop owner
sits behind while five agents work the board in front of them. Every decision below follows
from that one idea, because the thing being designed is not "an interface for an agent
system", it is *the place where a person decides whether to spend their shop's last $3,400*.

---

## 1. The governing idea: a desk, not a dashboard

Most agent dashboards are a log viewer with buttons. They show you *that* something happened
and leave you to reconstruct *what it means*. The problem with that, specifically here, is
that this board asks a human to authorise real money. A log does not help you decide; it
makes you do the deciding somewhere else, in your head, with worse information.

So the screen is laid out the way a physical desk is, and each of the three zones has one
job:

```
┌──────────────┬────────────────────────────────┬──────────────┐
│  ON THE      │           THE WIRE             │  THE CASH    │
│  BOARD       │                                │  DRAWER      │
│              │  what the team is doing,       │              │
│  paper slips │  in order, as it happens       │  the balance │
│  you pick up │                                │  + what      │
│  and hand    │  ↓                             │  needs your  │
│  over        │  THE CALL                      │  signature   │
│              │  what each agent did           │              │
│  (left hand) │  (centre of attention)         │  (right hand)│
└──────────────┴────────────────────────────────┴──────────────┘
```

Left is **intake** — work arriving. Centre is **the work itself**. Right is **the one thing
only you can do**. The eye travels left → centre → right, which is also the actual order of
the task: pick a ticket, watch the team, decide about money. Nothing on the screen asks you
to move backwards.

The right column is pinned to the cash drawer and never gets reused for anything else, so
"money needs you" always arrives in the same place in your peripheral vision. You learn it
once.

---

## 2. Colour: pink as a deliberate choice, not decoration

The palette is built on warm rose — `#fff8fa` paper on a `#ffeaf1` surface, with `#a53a60`
for emphasis. Two reasons, and neither is "pink is pretty":

**It matches the business.** This is a campus merch shop that sells hoodies and mugs to
student organisations. A navy-and-slate enterprise palette would be borrowed authority — it
would make a shop that sells Yale caps look like a trading terminal. Warmth is honest here.

**It leaves the alarm colours free.** Because nothing in the base palette is red, amber or
green, those three colours mean exactly one thing each when they appear:

| Colour | Reserved for | Where you see it |
|---|---|---|
| Red `#c4445c` | something is blocked or failed | `invoice 501` tag, a refused tool call, a falling balance |
| Amber `#c2780f` | a guardrail fired | a refused delegation, a write-tool chip |
| Green `#2f8f6b` | money was authorised | the Approve button, a settled payment |

In a grey dashboard, a red badge competes with a dozen other greys for attention. Here it is
the only hot thing on a warm, low-contrast field, so it is seen before it is read.

Depth comes from **warm neutrals**, never grey: `#3b2830` ink, `#7b6671` secondary, `#a8949d`
faint. A single cool grey anywhere would look like a bug in the page.

---

## 3. How the five agents read differently

This is the detail the whole wire depends on. During one ticket, four agents speak, some of
them nested two levels deep inside each other's delegations. If they all look alike, the feed
becomes a wall and the human stops reading it — which defeats the point of having a board.

Each agent gets **three** distinguishing signals, so you can identify a speaker from any one
of them:

| Agent | Hue | Monogram | Why that hue |
|---|---|---|---|
| **Boss** | deep rose `#a53a60` | **B** | The house colour, deepened. The Boss *is* the shop's voice. |
| **Inventory** | green `#1f7a6b` | **I** | Stock, shelves, physical goods — the one agent that deals in things |
| **Accounting** | ochre `#9a6510` | **A** | Ledger ink and brass. Money has always been this colour. |
| **Facilities** | indigo `#4a5bb5` | **F** | Buildings and leases — cool, institutional, not merchandise |
| **Customer Service** | violet `#8b4bb8` | **C** | The outward-facing voice; the only agent writing to people |
| **You** | forest `#2f6d4f` | your initial | Deliberately outside the agent palette — a human on the board must never be mistaken for an agent |

**The Boss also changes typeface.** Agent names are set in Inter; the Boss's name is set in
**Fraunces**, the display serif used for the masthead and the balance. It is the only agent
whose name is serif. You do not have to read "Boss" — the shape of the word tells you the
decision-maker just spoke. This is the single cheapest hierarchy signal on the page and it
costs no colour, no icon and no space.

**Delegation depth is drawn, not labelled.** A delegated agent's line indents 26px and grows a
vertical thread back up to whoever asked it. Two levels down, 52px and another thread. You can
see at a glance that Customer Service → Facilities → Accounting happened *without the Boss
touching it*, which is the whole point of a fully connected team and is invisible in a flat
log.

**Tool calls are translated into shop English.** The wire does not say
`get_vendor_status({vendor_id: 1})`. It says *"checked vendor 1 — can they ship?"* followed by
a small monospace chip reading `get_vendor_status`, and under it the answer in plain words:
*"Bulldog Print Co holds 1 open invoice(s) totalling $840.00 and will not ship until paid."*
Prose for the human, the exact tool name for anyone auditing. Neither reader is asked to
accept the other's format.

Write tools — the six that change the database — get an **ochre** chip instead of a rose one.
A lookup and a payment request should not look identical, and this is how you skim a run for
"what actually changed".

**When an agent reports back, it gets a quote block.** A left rule, a tinted ground, more
generous line-height, and room for six lines instead of two. Tool calls are machinery; an
agent's conclusion is *speech*. Giving the conclusion a different physical shape means you can
scroll a long run and read only the italicised-feeling parts and still know what happened.

---

## 4. Resolved tickets: a wax seal, not a grey badge

When the team finishes a ticket, a **wax seal** presses onto the card — a rose-gradient disc,
rotated −11°, with a dashed inner ring, and it animates in by scaling down from 2.1× with a
slight overshoot, like something physically stamped.

The alternative was a grey "RESOLVED" pill in the corner. Three reasons the seal won:

1. **Closing a ticket is an event, not a state change.** The press animation gives the moment
   a beat. Grey pills just quietly appear and you miss them.
2. **It survives peripheral vision.** The ticket column is on the left while your eyes are on
   the wire. A circular, rotated, saturated object registers out of the corner of your eye in
   a way a rectangular grey label does not.
3. **It carries the right connotation.** A seal means *authorised and done*, which is exactly
   what `resolve_ticket` means in this system — the work genuinely happened, not just "status
   field updated".

The card underneath also shifts to a faint rose wash and its title drops to secondary ink, so
a resolved ticket recedes without disappearing. And the button changes from "Hand to the
team" to **"Run again"**, because a finished ticket is still re-runnable after a reset.

**Tickets that are waiting on you do not get a seal** — and this matters. Ticket 101 ends with
the analysis complete, a draft written and a payment queued, but it stays **open** with a red
`1 awaiting approval` tag, because the work is not finished until a human signs. A dashboard
that sealed it would be lying about who is holding the baton.

The unopened ticket cards are each rotated a third of a degree, alternating direction, so the
stack reads as *paper that someone put down* rather than a CSS grid. Hovering straightens the
card and lifts it. It is a half-degree of rotation; it is also the difference between a
surface and a screen.

---

## 5. The cash drawer: where the money rule becomes visible

The balance is set in **Fraunces at 42px with tabular numerals** — the largest and most
serious type on the page, larger than the app's own title. On a board where everything else is
reversible, this is the one irreversible number, and it is sized accordingly. Tabular figures
mean the digits do not jitter when the value changes.

**When the balance falls, it turns red and shakes.** A four-keyframe horizontal shake over
500ms, then back to ink. Money leaving is the most consequential thing this screen can do, and
the standard pattern — silently re-rendering a new number — gives it exactly as much weight as
a page refresh. The shake is small and it does not block anything, but you cannot miss it.

Under the balance sits a **paper tape**: a repeating 7px pinstripe over a cream ground, showing
three lines — *paid out so far*, *awaiting your call*, *left if you approve all*. The third
line is the one a real shopkeeper actually needs, and it is the one most dashboards omit: it
answers "if I say yes to everything in this queue, where do I land?" before you say yes to
anything. If that number would go negative it turns red. With both pending approvals queued,
it reads **$160.00** — which tells the story of this entire shop in one figure.

The tape closes with a line in italic: *"Cash only goes out here — nothing refills it."* The
shop has no revenue model, and a balance with no inflow behaves differently from one with
inflow. Saying so once, quietly, in the place where the number lives, is better than assuming
the user has read the brief.

### The approval slips

Each pending payment is a **slip** — rose-tinted, ring-highlighted, with the amount set in the
same display serif as the balance so the eye connects "this amount" to "that balance". It
carries the agent's own reason for asking, the requester, and the ticket it serves.

There is a **name field above the slips**, pre-filled but editable, labelled *"Your name — goes
on the payment record"*. It is not decoration: that string is written into
`payments.approved_by` and is the permanent record of who authorised the money. The Approve
button is disabled until it is non-empty. Making the human type their own name into the thing
that spends the money is a small piece of friction, deliberately kept.

And beneath the queue, always visible:

> **No agent can approve a payment.** They can only prepare one — the tool that authorises
> money is kept off every agent's toolset and lives here, with you.

This is a true statement about the architecture (`decide_payment_approval` is filtered out of
all five agents' toolsets), and putting it on the screen is a design decision in itself. The
person sitting at this desk should know *why* they are being asked, not just *that* they are.
Trust in an agent system comes from understanding the limits, and the limits are worth printing.

---

## 6. Typography

Three families, each with a job, which is two more than a dashboard usually needs and one
fewer than it takes to look chaotic:

- **Fraunces** (display serif) — masthead, the Boss's name, the balance, section headings,
  the wax seal. Everything with *authority*: the shop's identity, the decision-maker, the
  money.
- **Inter** (sans) — all body text and UI. Invisible by design; it is doing the reading work.
- **JetBrains Mono** — tool names, SKUs, timestamps, tape figures, ticket numbers. Anything
  that is **an identifier a machine would recognise** is monospaced, so you always know
  whether you are looking at prose or at a key you could paste into a query.

That last rule is applied without exception, and it is why the wire can mix English and tool
names in one sentence without either becoming hard to parse.

The masthead reads **"The Desk"**, with *"Campus Customs · New Haven"* above it and the
tagline *"Five agents work the board. You hold the chequebook."* Twelve words that establish
the metaphor, the location, the cast, and the division of authority before you have looked at
anything else. Beside it the shop date sits in a dashed, slightly rotated **rubber stamp** —
because `desk.date_today` is 2026-08-31 and not the real date, and a stamp is how a shop
marks "this is today for our purposes."

---

## 7. Motion, and the live state

Motion is used for exactly three things, and nothing else moves:

1. **Arrival** — each new wire line fades up 6px over 300ms, so you see *where* the new
   content landed rather than hunting for it in a re-rendered list.
2. **A pulsing bulb** in the "WORKING" badge while a run is live. The board polls `/events`
   every 1.2 seconds with a `since_seq` cursor so only new events come over the wire, and the
   feed auto-scrolls to the newest line.
3. **The seal press and the balance shake**, as above — the two moments that deserve a beat.

Everything else is static, which is what lets those three read as meaningful rather than as
ambient animation.

While the team is working, every "Hand to the team" button disables and the selected ticket's
button reads **"Team is working…"**. The backend allows one run at a time and returns HTTP 409
otherwise; the UI reflects that honestly instead of letting you queue a click that will fail.

Toasts land centre-bottom, carrying the backend's own sentence — including the refusals. When
a payment exceeds the balance, the toast says *"REFUSED: paying $500.00 from $160.00 would
leave a negative balance"*, in red. The guardrail speaks for itself; the UI does not paraphrase
it into something softer.

---

## 8. What makes this specifically different

Lined up against the usual agent-observability screen:

| The usual thing | The Desk |
|---|---|
| A flat scrolling log, one typeface, one colour | Indented threads showing who asked whom, five hues, a serif reserved for the Boss |
| Raw tool names and JSON | Shop English with the tool name kept as a chip, and the result's key numbers pulled out in words |
| "Status: resolved" | A wax seal that presses onto the card — and *refuses* to appear while a human is still owed a decision |
| The balance as a number in a stat card | The largest type on the page, in tabular serif, that reddens and shakes when it falls |
| "2 pending approvals" | *"left if you approve all: $160.00"* — the number you actually need before deciding |
| Approve button | Approve button gated behind typing your own name, which is then written permanently into `payments.approved_by` |
| Silent about its own limits | Prints the rule on the screen: no agent can approve a payment, and here is why |

The thread running through all of it: **the interface should make the human's job easier, not
the system's job more visible.** Every choice above — the translation layer over tool calls,
the third line on the tape, the seal that will not appear early, the name field — exists
because someone has to decide about money with incomplete information, and the screen can
either help with that or merely report around it.

---

## 9. Running it

```bash
# backend — from HW 5/backend
uvicorn main:app --reload --port 8000

# the desk — from HW 5/frontend
npm run dev
```

The board is served at `http://localhost:5173` and talks to `http://localhost:8000`, which
allows that origin via CORS. If the backend is not up, the desk says so in plain language and
prints the command to start it rather than failing silently.
