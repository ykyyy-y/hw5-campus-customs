# HW 5 — Campus Customs Multi-Agent Operations: Vibe Coder Prompt Log

**Course:** 409 AI for Managers — AI Foundation
**Assignment:** HW 5 — Campus Customs Multi-Agent Operations (MCP server + FastAPI backend
with a fully connected five-agent team + React approval dashboard, over the shop's SQLite
database)
**Author:** Yookyung Eom
**Started:** 2026-10-04

## How this log works

This file is the running record of every prompt I typed to the vibe coder while building
this assignment. It is updated as each problem is completed, not reconstructed afterward.

Each problem below has exactly three parts, per the assignment spec:

1. **Problem number and title**
2. **At least one prompt I typed** — recorded verbatim, as typed
3. **One follow-up prompt if I needed it** — plus one sentence on what was lacking after
   the first prompt. Where the first prompt was sufficient, that is stated explicitly.

The evidence of the work itself is the code, the MCP server, the running dashboard, and the
database writes — no separate proof write-up is included here beyond these prompts.

### Standing rules I set for the whole assignment

These were established at the start and apply to every problem below, so they are not
repeated in each section:

- All work lives in the `HW 5` folder.
- Every agent call uses **`gpt-6-luna` only**, through Portkey, with `PORTKEY_API_KEY` read
  from the root `.env` and never printed, committed, or exposed.
- `data/campus_customs.db` is the untouched original; the server and backend work against
  `data/campus_customs_new.db`, which is regenerated from the original by a reset step
  before any full run.
- Human approval is required before any payment; the pay tool refuses when cash is short;
  no customer emails or vendor calls — drafts stay on the board.

---

## Setup — before Problem 1

### Prompts I typed

> today, working on HW5. 다음 지시사항 한줄한줄 잘 읽고 참고해서 내가 앞으로 명령하는거
> 반영해서 해줘. all the work will be put at HW5 folder. okay?
>
> (with the two assignment pages — Scenario / Data, and Rules of this shop — attached)

> 응 1. 자료 경로는 너가 아예 수정해줘. 2. 그리고 gpt-6-luna를 사용해줘.

> 복사 파일 둘다 가지고 있기 싫은데, 가이드라인 따라 정확한 경로에 하나만 유지해줘

### What these set up

The unzipped data had arrived one folder too deep, at `data/data/campus_customs.db`. The
coder flattened it to the path the assignment specifies, `data/campus_customs.db`, and that
original is now the only database file kept on disk — the working copy
`campus_customs_new.db` is generated from it by the reset step rather than stored alongside
it, so there is exactly one source of truth to reset from. The model choice
(`gpt-6-luna` only) was fixed here as well.

---

## Problem 1 — Vibe Coder Prompts

Create the prompt log itself, at the start of the assignment, and keep updating it as the
work proceeds: one dedicated section per problem, each with the problem number and title,
at least one prompt I typed, and a follow-up prompt if one was needed, with one sentence on
what was lacking after the first.

### Prompt I typed

> now going to problem #1: vibe coder prompts (5 points)
>
> create `AI_prompts.md` when you begin the assignment and update it continuously. this
> file serves as the log for prompts sent to your vibe coder.
>
> make sure to set up a dedicated section for each problem. every section needs to include:
>
> * problem number and title
> * at least one prompt i typed
> * a follow-up prompt if you needed it (and one sentence on what was lacking after the
>   first)

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It named the file, the
timing ("when you begin… update it continuously"), the per-problem sectioning, and all
three required parts inside each section, so `AI_prompts.md` was created correctly on the
first attempt and the remaining problems only need their sections appended as they are
finished.

---

## Problem 2 — Study the Campus Customs Database

Examine every table and field in `data/campus_customs.db`, duplicate it to
`data/campus_customs_new.db` as the working copy that later problems write to, trace how the
three open tickets connect to the other tables, and start `output/harness.md` with each
table, its fields, and a one-line note on why each field matters to the agents.

### Prompt I typed

> now going to problem #2: study the campus customs database
>
> open data/campus_customs.db and examine all tables along with their fields. duplicate this
> file to data/campus_customs_new.db --- later problems update that working copy.
>
> check the three unresolved tickets to understand how they connect with other tables.
> create output/harness.md. for every table, write down its fields and include a quick
> summary in one line explaining its significance for the agents.
>
> you will continue expanding this harness file in subsequent problems!

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It named the source and
destination database paths, the per-field "why it matters" format, the output file, the
requirement to trace the three open tickets through their joins, and the fact that the
harness would keep growing — so all nine tables were documented with live values, the three
tickets were traced to the shared Bulldog Print Co bottleneck, and numbered stubs were left
for the models, tools, safety, and run-spec sections.

---

## Problem 3 — Build the MCP Server

Build an MCP server in `mcp_server/` with FastMCP, pointed at `data/campus_customs_new.db`,
holding the first three tools the open tickets need — plainly named, inventing no data.
Document all three in `output/harness.md` with the table each reads, the exact ticket each
unlocks, and one sentence tying the tool to that ticket. Add a short `mcp_server/README.md`
covering the server's purpose, its database file, and its three tools.

### Prompt I typed

> now going to problem #3: build the MCP server
>
> construct an MCP server inside the mcp_server/ folder by utilizing FastMCP. it should be
> configured to interact with data/campus_customs_new.db, but you are not required to
> connect or execute it during this step.
>
> all agents in this assignment rely on the tools within this mcp server, you will add more
> tools to it later. and first write three tools that will be essential for the database
> tickets. make sure the names of these tools are straightforward, never invent ANY DATA,
> only use information in the database.
>
> within output/harness.md, document each all three of your mcp tools. for each tool, detail
> the table it reads from, the exact ticket it helps to unlock (101, 102, or 103), and add
> one sentence justifying why the tool is suitable for that specific ticket. avoid vague
> descriptions and clearly connect each tool to its ticket. vague lines like "reads
> inventory" are score low- tie the tool to the ticket.
>
> finally, create a concise mcp_server/README.md file that describes the 1.
> objective/explanation of the of the MCP server is for, 2. identifies the database file it
> employs, and 3. lists the three tools it incorporates.

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It fixed the framework
(FastMCP), the folder, the database file, the tool count, the naming and no-invented-data
constraints, the three documentation points per tool, the warning against vague wording, and
the three required README sections — so `check_stock` / `get_rent_due` / `price_quote` were
written one-per-ticket (101 / 102 / 103), each documented with its source table, its ticket,
a tool-to-ticket justification sentence, and the live JSON it returns from the working copy.

---

## Problem 4 — Connect the MCP Server and Test Each Tool

Register the MCP server so its tools can actually be called, saving the connection config as
`.mcp.json` at the project root, then test all three tools and record the proof in
`output/mcp_smoke.json` — for each tool, the prompt asked, the tool name, and the output,
which must match the values in `data/campus_customs_new.db`.

### Prompt I typed

> now going to problem #4: add the MCP server to vibe coder and test each tool
>
> integrate your MCP server into this project, so that the tools can be called. save this
> connection JSON configuration within .mcp.json at the root of the project (or however you
> save local MCP server lists).
>
> after connecting the vibe coder, TEST EACH of the three MCP tools and then record the
> proof in output/mcp_smoke.json.
> so run the three test and make the prompts to test, run the test, and check the details.
>
> for every tool, you must provide:
> the specific prompt you asked
> the tool name
> the output from the tool (must match values in data/campus_customs_new.db)

### The three test prompts I typed

One per tool, each written from the ticket it has to unlock. These are the `prompt` fields
recorded alongside the tool output in `output/mcp_smoke.json`.

**Test 1 — `check_stock`, ticket 101**

> Ticket 101 is Tauhid Zaman asking for a Classic Bulldog Tee in size S. Use the
> campus-customs MCP server to check stock for CC-TEE-WHITE size S for 1 unit, and tell me
> whether we can fill it and by how much we are short.

**Test 2 — `get_rent_due`, ticket 102**

> Ticket 102 is a rent notice from Elm City Properties on lease 1, and the email claims rent
> is due in 2 days. Use the campus-customs MCP server to get the rent due for lease 1 and
> confirm the amount and the due date against the shop's own date_today rather than the
> email.

**Test 3 — `price_quote`, ticket 103**

> Ticket 103 is the Yale AI Club asking for a bulk discount on 20 CC-HOOD-NAVY hoodies in
> size M. Use the campus-customs MCP server to price 20 units and test a 20 percent discount
> at $46.40 per unit — I want the list margin, the cost floor, and whether that proposed
> price still clears cost.

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It named the config file and
its location, required every tool to be tested rather than a sample, named the proof file, and
listed the three fields each entry must carry — so `.mcp.json` registers the server over stdio,
`scripts/mcp_smoke_test.py` launches it from that same config as a real subprocess and calls
each tool through the MCP handshake instead of importing the functions, and
`output/mcp_smoke.json` records the prompt, tool name, arguments, and output for all three,
each cross-checked against a direct SQL read with a `matches_database` flag
(`all_outputs_match_database: true`).

---

## Problem 5 — Build the Agent Team and Grow the MCP Tools

Build the five-agent Campus Customs team in PydanticAI — Boss, Inventory, Accounting,
Facilities, Customer Service — with prompts, models and agent loops giving full
connectivity for delegation. Prompts in `backend/prompts/` (one file per agent), data types
in `backend/models.py`, agents in `backend/`. `PORTKEY_API_KEY` and `gpt-6-luna` for every
agent. Add whatever MCP tools the open tickets need, with all shop facts coming through the
MCP server and no alternative tool layer. Append every agent-loop step to
`output/audit_trail.json`. Document the agents, every tool and the table it touches, plus a
safety section and token-usage constraints, in `output/harness.md`, and update
`mcp_server/README.md` so the tool list matches.

### Prompt I typed

> now going to problem #5: build the agent team and grow the MCP tools
>
> construct an agentic team for Campus Customs using PydanticAI, including the roles: Boss,
> Inventory, Accounting, Facilities, and Customer Service. ensure you provide prompts,
> models, and agent loops to allow full connectivity for delegating tasks among them.
>
> store the agent prompts in the `backend/prompts/` directory, using one file per agent.
> place your data types in `backend/models.py`, and organize the agent files within
> `backend/` (the structure can vary as long as the five distinct roles are easily
> identifiable!). you must use your `PORTKEY_API_KEY` and restrict the model to
> `gpt-6-luna` for every single agent.
>
> draft each prompt in your own words, making sure to incorporate the specific shop rules
> required by that agent. keep in mind that comprehensive and detailed prompts covering all
> aspects of an agent's responsibilities and scope will yield better results than brief,
> generic ones.
>
> incorporate any necessary tools into your MCP server so the agents can process the open
> tickets. all shop facts must be retrieved from the MCP server via
> `data/campus_customs_new.db` — do not create an alternative tool layer that bypasses MCP.
>
> configure the agents to append their activity to `output/audit_trail.json` during
> execution: for every agent-loop step, log sufficient details for future auditing.
> remember to append to this file rather than overwriting it on each run.
>
> within `output/harness.md`, document each agent and every MCP tool (including any newly
> added ones in this problem), noting which table each tool accesses. additionally, include
> a brief safety section outlining the guardrails a real business would require when agents
> interact with real customers and finances, along with constraints to manage token usage.
>
> finally, update the `mcp_server/README.md` file so the tool list accurately matches what
> you have now

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It fixed the framework, the
five roles, the file layout, the model and credential, the "no tool layer that bypasses MCP"
constraint, the append-don't-overwrite requirement for the audit trail, and every section the
harness and README had to gain — so the team was built as a complete delegation mesh on
`gpt-6-luna` through Portkey, the MCP server grew from 3 to 18 tools with the human-only
approval switch withheld from all five agents, and a live full-board run proved the
guardrails hold (two approvals queued, zero payments made, cash unchanged at $3,400, three
drafts saved and none sent, one delegation refused at the budget ceiling).

---

## Problem 6 — Plan the Three Tickets

Before wiring the backend, write down what the team is expected to do with each open ticket.
Build `output/desk_tickets.html` with one tab per ticket (101, 102, 103) plus empty Cash and
Reflection tabs, and fill only an Expected section on each ticket tab — leaving room for an
Actual section to be completed after the agents run. Each Expected section covers who the
Boss contacts first and why, the specific delegations foreseen, and the MCP tools expected
to be used. Routing every specialist to every ticket scores low.

### Prompt I typed

> now going to problem #6: plan the three tickets
>
> before connecting the backend, document what you anticipate the team will execute for each
> open ticket. create an `output/desk_tickets.html` file that features one tab per ticket
> `(101, 102, and 103)`. you should also include empty Cash and Reflection tabs for future
> tasks `(leave them blank or with a short "coming later" note for now)`.
>
> for every ticket tab, complete an Expected section only `(leave room for an Actual section
> you will fill after you run the agents)`.
>
> within the Expected section of each ticket, describe the following in your own words:
>
> * who the Boss needs to contact first, including the reasoning
> * all the agent delegations you foresee happening — not "Boss calls everyone"
> * which MCP tools are anticipated to be utilized during the run
>
> keep in mind that strategies routing every specialist to every ticket will receive low
> scores. you will eventually compare this initial plan against the real outcomes once your
> agents handle the three tickets.

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It named the file, the five
tabs, the Expected-only scope with room left for Actual, the three points each Expected
section had to cover, and the warning against fan-out routing — so each ticket got a
different first contact (101 → Inventory, 102 → Facilities, 103 → Accounting), a named
delegation chain including agent-to-agent hops that skip the Boss, a per-tool table, and an
explicit "not involved, and why" list so the narrow routing is visibly deliberate rather than
an omission.

---

## Problem 7 — Backend Routes

Build `backend/main.py` with FastAPI so the React dashboard has something to talk to:
routes to list the three tickets with their open/resolved status, trigger the agent team on
one ticket id, serve recent agent events so the board can refresh, execute a payment once a
human hits approve (agents only prepare it; this route is what actually changes cash),
return the checking balance from `cash_accounts`, and reset the database for a fresh run.
Run it with `uvicorn main:app --reload --port 8000` from `backend/`, and document every
route on a single line in `output/harness.md`.

### Prompt I typed

> now going to problem #7: Backend routes
>
> the React frontend dashboard `(the next problem)` requires a functional backend to
> communicate with. within `backend/main.py`, utilize FastAPI to build routes that
> accomplish the following tasks:
>
> * rerun the three tickets along with their current status, whether if they are open or
>   resolved
> * take a ticket id and trigger your agent team to process that specific ticket
> * provide recent agent events —what each agent said and which tools they used so the board
>   can refersh
> * confirm/ approve a payment or purchase once a human user hits approve `(agents only
>   prepare the pay; this route is what actually changes cash)`
> * return the current checking balance from `cash_accounts`
> * reset the database back to its initial state when you need to execute a fresh run
>
> navigate to the `backend/` directory and launch the server using this command: `uvicorn
> main:app --reload --port 8000`.
> this will activate your backend at `http://localhost:8000`, enabling the frontend
> dashboard to access those created routes.
> finally, inside `output/harness.md`, document every route on a single line!! `(what URL /
> what it does)`

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It listed all six required
capabilities, named the file, the launch command and the port, and specified the one-line
documentation format — so the six became eleven routes (with `/runs`, `/drafts`,
`/approvals` and `/health` added for the dashboard), the server was started with exactly
that uvicorn command, and every route was exercised live: approving invoice 501 moved the
balance $3,400 → $2,560 and flipped the invoice to `paid`, approving rent took it to $160, a
$500 payment against that $160 was refused with the balance untouched, a rejection moved no
money, `/reset` restored the shop while keeping the audit trail, and a second concurrent run
returned HTTP 409.

---

## Problem 8 — Agent Dashboard

Build the React + Vite + TypeScript dashboard in `frontend/`, calling the Problem 7 routes:
list all three tickets, pick one and trigger the agent team, show each agent saying and doing
things while the ticket runs, mark a ticket resolved when it finishes, summarise what each
agent did, let a human approve a payment, and display the checking balance so it drops after
an approved payment. Make it genuinely attractive — a real desk someone would want to sit at.
Point it at `http://localhost:8000`, allow the Vite origin on the backend, start it with
`npm run dev`, and write `output/design.md` explaining the look and the reasoning behind it.

### Prompt I typed

> now going to problem #8: agent dashboard
>
> develop the frontend dashboard inside the `frontend/` using React + Vite + TypeScript. this
> page needs to call the routes you established in problem 7. At a minimum, the board must:
>
> * list all three tickets
> * allow you to pick one ticket and trigger the agent team on it
> * show each agent along with what they are saying / doing while the ticket runs
> * mark a ticket as 'resolved" when the execution finishes
> * present a short summary of what each agent did on that ticket
> * Let a human to approve a pay or purchase when requested
> * display the checking balance (it should drop after an approved pay)
>
> ensure the dashboard looks visually appealing. be creative with its layout and overall feel
> — this represents a real desk that people would actually want to sit at, so invest thought
> into its appearance. make it clear but aesthetic, put the creative details in the layout and
> fonts and colors!
> configure the front end to communicate with your backend at `http://localhost:8000`. on the
> backend side, make sure to allow the Vite page origin (usually `http://localhost:5173`) so
> that the browser is permitted to call those routes.
> start the board with executing this command:
> `npm run dev`
> this will open the React desk in your browser, allowing you to select tickets and observe
> the agents in action.
> create `output/design.md` detailing your choices for the dashboard's look (layout, how
> agents read differently, how resolved tickets and cash show up) and the reasoning behind
> them and it is important to include creative decisions that make it feel special and
> something humans would actually enjoy using. put the reasoning in detail that could be
> differentiated with other services. be creative and specific and aesthetic but clear and
> need to include the details I requested

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It listed all seven board
requirements, the stack, both ports and the CORS origin, the launch command, and exactly which
design decisions `design.md` had to justify — so the desk was built as a three-column shop
counter (board / wire / cash drawer), every requirement was exercised live in the browser
rather than assumed, and the design doc explains each choice against the alternative it
replaced. Verified in the running app: three tickets listed, ticket 101 handed to the team,
the wire filled with colour-coded agents and indented delegations, per-agent summary cards
rendered under the Boss's call, approving the $840 invoice moved the balance $3,400.00 →
$2,560.00 with the settled slip reading "paid · by Yookyung Eom", and a resolved ticket took
the wax seal with its button switching to "Run again".

---

## Problem 9 — Resolve the Tickets

Reset the working database, note the opening checking balance, and run all three tickets
(101, 102, 103) until they are completely resolved. Fill the Actual section of each ticket
tab in `output/desk_tickets.html` with the agents that were active, their delegations and the
tools used, keeping the Expected sections intact for comparison. Itemise the money on the Cash
tab: opening balance after reset, how cash moved on each ticket and why, and a closing balance
that matches `cash_accounts` exactly. Save `output/resolved_tickets.json` and
`output/resolved_board.html` (with a screenshot of the React board per resolved ticket), append
the run to `output/audit_trail.json`, and complete `output/harness.md` across tables, MCP
tools, the five agents, API routes, the dashboard and safety.

### Prompt I typed

> now going to problem #9: Resolve the tickets
>
> before executing a full test of the agents across the three tickets, reset your working
> database `data/campus_customs_new.db` to ensure a clean start. take note of the initial
> checking balance, and then process all three tickets on the board `(101, 102, 103)` until
> they are completely resolved.
>
> open the `output/desk_tickets.html` file created in problem 6. within each ticket's tab,
> fill in the actual section based on this run by detailing 'which agents were active', 'their
> delegations', and the specific tools utilized'. do not delete your expected section so that
> a comparison can be made between the two.
>
> On the cash tab inside that same `output/desk_tickets.html` and itemize the money:
>
> * initial checking balance `(after the reset)`
> * for every single ticket, describe how the cash fluctuated upon resolution and the
>   reasoning behind it `(which pay / purchase, dollar amount)`
> * the final checking balance — this needs to perfectly match `cash_accounts` inside the
>   working database
>
> incorrect cash calculations will result in a penalty.... even if the dashboard indicates all
> tickets are resolved. you must also save the following:
>
> * `output/resolved_tickets.json` —for each ticket: id, final status, short outcome, each
>   agent's contribution, and any human approvals for each ticket
> * `output/resolved_board.html` — a page you can double click containing a screenshot of your
>   React board for each resolved ticket `(101, 102, and 103)`
>
> add the actual run data to `output/audit_trail.json`. complete `output/harness.md` ensuring
> it encompasses the tables, MCP tools, the five agents, API routes, the dashboard, and safety
> guidelines.

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It specified the reset, the
completion bar ("until they are completely resolved"), that Expected sections must survive,
every field the Cash tab and `resolved_tickets.json` had to carry, and the warning that wrong
cash is penalised — so the cash figures are generated from the `payments` table rather than
typed, and both build scripts assert `opening − Σ payments == cash_accounts.checking` and
refuse to write a file if it fails. The board ran from a clean reset at $3,400.00 and closed at
$160.00 with all three tickets resolved; the two payments ($840.00 invoice 501, $2,400.00 rent
on lease 1) both carry `approved_by = "Yookyung Eom"`, and five drafts were written with none
sent.

---

## Problem 10 — Reflection

Complete the Reflection tab in `output/desk_tickets.html` with detailed answers, in my own
voice, covering: how the agents performed on each ticket and why; how the actual results
compared to the expected plan for every ticket; which specific task would have been easier
for a single agent with tools, and why; three new Campus Customs problems the current team and
tools could solve; and three it could not, with the extra tools and agents that would be
needed. Every answer must be tied to this app and these three tickets, using the ticket tabs
and the Cash tab as evidence — generic essays score low.

### Prompt I typed

> now going to problem #10: reflection
>
> open output/desk_tickets.html and complete the reflection tab. make sure to provide thorough
> and detailed answers in your own style for the following:
>
> * how you evaluate the agents' performance across each ticket and the reasons why
> * a breakdown of how the actual results compared to your earlier expected plan for every
>   ticket
> * what specific task would have been easier if handled by a single agent equipped with
>   tools, 'and why'
> * describe three new challenges Campus Customs might face that your current agent team and
>   tools could solve with the tools you built
> * describe three new challenges Campus Customs might encounter that your team could not
>   solve with the existing setup, and expalin the extra tools and agents you would need to
>   resolve them
>
> ensure every answer is directly connected to "this app and the three tickets you executed "—
> utilize the ticket tabs and the cash tab on the same page to support your points as the
> evidence. and mind that generic essays lacking specific campus customs details will result
> in a low score .and getting high score than others is the goal

### Follow-up prompt

No follow-up prompt was needed; the first prompt was sufficient. It listed all five questions,
required the answers to cite this app and these three tickets rather than generic agent
theory, and named the ticket tabs and Cash tab as the evidence — so each answer is anchored in
run data: graded tickets with tool-call and token counts (101: 39 calls / 142,228 tokens;
102: 20 calls / 80,815; 103: 20 calls / 92,509), three verbatim quotes from the drafts the
agents actually wrote, a hop-by-hop plan-versus-actual table, and the five SKUs, two vendors
and real balances from the working database. Re-reading the audit trail while writing it
surfaced a genuine defect in ticket 102 that the Problem 9 summary had mistaken for good
behaviour, and that correction is now the centrepiece of the performance section.

---
