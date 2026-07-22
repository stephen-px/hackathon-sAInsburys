# CLAUDE.md — sAInsburys: Waste the Difference

> PhysicsX Agentic Hackathon 2026 (UK) · 22–23 July · Theme: Efficiency + Automation  
> GitHub: https://github.com/stephen-px/hackathon-sAInsburys  
> Notion build plan: https://app.notion.com/p/sainsburys-build-plan-3a54aca9ecb380e788b1d06a1dcd3b06  
> Hackathon page: https://www.notion.so/PhysicsX-Agentic-Hackathon-2026-UK-36e4aca9ecb38029b4e4c716cdc7acbb

---

## What we're building

Two Slack-native agents around one shared Postgres database (Supabase).

**The Basket Agent** collects weekly meal picks (one-tap buttons or free-text natural language) from employees and turns them into two consolidated Sainsbury's baskets — one for Monday delivery, one for Wednesday delivery — with a human-in-the-loop Approve step before checkout.

**The Rescue Board Agent** runs every Friday: it collects check-ins on what people actually ate, ranks leftover items by expiry risk, and posts a personalised public claim board with one-tap claiming. Every claim logs a £-saved event that ticks a live counter on the dashboard.

A lightweight read-only **dashboard** (Next.js or Streamlit) shows the live basket, leftovers board, leaderboard, and £-saved counter in real time via Supabase realtime subscriptions.

---

## Judging criteria (design every feature against these)

| Criterion | What judges want |
|---|---|
| **Impact 💥** | How many people/teams can use it? How cross-functional? |
| **Efficiency 📈** | Time/money saved? Easy to use, run, and maintain? |
| **Creativity 🧠 + Wow Factor 🤯** | Most inventive solution? What blows people's minds? |
| **Platform Expansion** | Agents utilising the platform most successfully? |

**The demo is 3 minutes. Build to make those 3 minutes land.**

---

## Project structure

```
sainsburys/
├── app.py                    # Bolt entrypoint + APScheduler jobs
├── store.py                  # THE contract — every DB read/write lives here
├── contracts.md              # store signatures, action_ids, event payload shapes
├── slack_surface/            # ── Track A (Slack surface)
│   ├── manifest.yaml
│   ├── blocks.py             # Block Kit builders
│   └── handlers.py           # slash commands, actions, modals
├── agents/                   # ── Track B (Intelligence)
│   ├── loop.py
│   ├── tools.py
│   ├── suggester.py
│   ├── parser.py
│   ├── personaliser.py
│   ├── prompts/              # .md prompt files — edit these, not the code
│   ├── fixtures/             # ~10 real example inputs for evals
│   └── run_fixtures.py       # 20-line eval script — run after every prompt change
├── flows/                    # Shared orchestration
│   ├── basket.py
│   └── rescue.py
├── data/                     # ── Track C (Data + demo ops)
│   ├── schema.sql
│   ├── views.sql
│   ├── seed.py
│   ├── demo_reset.py
│   └── catalogue.csv         # ~40 real Sainsbury's items with prices + shelf lives
├── dashboard/                # Next.js app or streamlit_app.py (Track C)
└── .env.example
```

---

## Architecture decisions (already made — don't relitigate)

| Layer | Choice | Why |
|---|---|---|
| Employee interface | Slack Bolt + Socket Mode | No public URL needed, works on office wifi, zero install for employees |
| Database | Supabase Postgres | Free tier, realtime subscriptions for the live counter, normal SQL |
| Runtime | Single Python service | No queues, no Docker, runs on a laptop — demo-safe |
| Checkout | **Mocked** (basket CSV + Approve button) | No public Sainsbury's API; the agent loop is the demo, not payment |
| Dashboard | Next.js or Streamlit | Read-only; zero business logic; Streamlit if time is tight |

**Slack Socket Mode** opens a websocket outbound from your laptop — no ngrok needed.  
**Supabase Postgres** is the single source of truth. Notion is a display surface only — never the DB.  
**Every scheduled behaviour also has a `/demo-*` slash command** so you can compress a week into 3 minutes on stage.

---

## The agent loop (the entire trick)

```python
# agents/loop.py
import json, anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

def run_agent(system, user_msg, tools, impls, model="claude-sonnet-4-6", max_turns=6):
    messages = [{"role": "user", "content": user_msg}]
    for _ in range(max_turns):
        resp = client.messages.create(
            model=model, max_tokens=2000,
            system=system, tools=tools, messages=messages,
        )
        if resp.stop_reason != "tool_use":
            return resp                      # model is done
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = impls[block.name](**block.input)
                results.append({"type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(out)})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("agent exceeded max_turns")
```

**Key facts:**
- The Messages API is **stateless** — you resend the whole conversation each call. The loop owns state.
- **Structured output = a finisher tool.** Never parse prose. Give the model a `submit_*` tool whose `input_schema` is your target JSON shape, instruct it to finish by calling that tool, and read `block.input` directly.
- Use `claude-sonnet-4-6` for everything. At hackathon volume, API cost is a rounding error.

### LLM vs plain code — the rule

| Use the LLM | Use plain code |
|---|---|
| Parsing "that banh mi thing again, no coriander, enough for two days" | Summing quantities across selections |
| Suggesting meals given constraints | Decrementing inventory (FIFO) |
| Personalising the rescue board ("you've picked falafel 3 weeks running") | Expiry risk scoring |
| Writing charming Slack digest copy | Anything involving money |

**When a judge asks "what stops it hallucinating 400 avocados?"** — the model only ever *proposes* structured data through tool schemas; deterministic code validates and aggregates; a human taps Approve before checkout.

---

## Data model

```sql
-- people
create table users (
  slack_id  text primary key,
  name      text,
  dietary   text[] default '{}',      -- {'vegetarian','no-pork',...}
  taste     jsonb  default '{}'       -- rolling tag counts: {"wrap":3,"salad":1}
);

-- Sainsbury's items we stock — hand-seeded, ~40 rows
create table products (
  id               serial primary key,
  name             text,
  category         text,
  price            numeric,           -- £ per unit as sold
  shelf_life_days  int,               -- 2 for bagged salad, 5 for hummus, 30 for crisps
  url              text
);

-- no-hob-no-oven meals, mapped to products
create table meals (
  id          serial primary key,
  name        text,
  description text,
  tags        text[]                  -- {'wrap','vegan','spicy'}
);
create table meal_products (
  meal_id    int references meals,
  product_id int references products,
  qty        numeric                  -- units of product AS SOLD (integer maths)
);

-- who chose what this week
create table selections (
  id             serial primary key,
  week           date,                -- Monday of the week
  half           text check (half in ('early','late')),
  user_slack_id  text references users,
  meal_id        int references meals,
  freeform       text,
  parsed         jsonb,
  status         text default 'pending'
);

-- the two weekly baskets
create table orders (
  id            serial primary key,
  week          date,
  delivery_date date,
  status        text default 'draft'  -- draft | approved | delivered
);
create table order_lines (
  order_id   int references orders,
  product_id int references products,
  qty        numeric,
  unit_price numeric
);

-- what's physically in the fridge, lot by lot
create table inventory_lots (
  id            serial primary key,
  product_id    int references products,
  delivery_date date,
  expiry_date   date,
  qty_delivered numeric,
  qty_remaining numeric
);

-- every event — everything else derives from this
create table events (
  id            serial primary key,
  ts            timestamptz default now(),
  kind          text check (kind in ('consumed','claimed','wasted')),
  user_slack_id text,
  lot_id        int references inventory_lots,
  qty           numeric,
  value         numeric               -- £ = qty * unit_price
);
```

**Three views do the rest:**

```sql
create view leftovers as
  select l.*, p.name, p.price,
         (l.expiry_date - current_date) as days_left
  from inventory_lots l join products p on p.id = l.product_id
  where l.qty_remaining > 0;

create view leaderboard as
  select user_slack_id, sum(value) as saved
  from events where kind = 'claimed'
  group by user_slack_id order by saved desc;

create view weekly_totals as
  select date_trunc('week', ts) as week, kind, sum(value) as total
  from events group by 1, 2;
```

**Simplifications (intentional):** quantities are always in units-as-sold; check-in decrements FIFO per product.

---

## store.py — the contract (write stubs by D1 10:30 to unblock all tracks)

```python
record_selection(user, week, half, meal_id=None, parsed=None, freeform=None) -> Selection
confirm_selection(selection_id) -> None
build_baskets(week) -> list[Order]            # deterministic aggregation
approve_order(order_id) -> Order
deliver_order(order_id) -> list[Lot]          # creates inventory lots
open_items_for(user, week) -> list[LotShare]  # feeds the check-in DM
record_consumption(user, lot_id, fraction) -> Event
leftovers() -> list[Lot]                      # the view, risk-scored
claim_lot(lot_id, user) -> Event              # transactional
sweep_waste(week) -> Digest
leaderboard() -> ...
weekly_totals() -> ...
```

**Track A (Slack) and Track B (agents) call only these functions — never raw SQL.**  
Changing a signature = tell the group first.

---

## The three agents

### Basket Agent — LLM stations

**Suggester** (`agents/suggester.py`): given the meals catalogue + dietary tags + constraints (no hob, no oven, keeps 2+ days), returns 5 meal cards via a `submit_suggestions` finisher tool.

**Parser** (`agents/parser.py`): turns freeform text into product lines. Tools available:
- `search_products(query)` → rows from `products`
- `get_meals()` → catalogue
- `get_user_prefs(user)` → dietary + taste profile
- `submit_meal_plan(product_lines, half, notes)` → finisher

Max 6 turns. Result written to `selections.parsed`. Bot DMs the user their interpreted plan with an ✏️ Edit button — this is the **hallucination backstop and a demo beat**.

**Aggregation** (`flows/basket.py`): **deterministic** — sum product lines across confirmed selections → two draft orders → Approve button (human-in-the-loop).

### Rescue Board Agent — LLM stations

**Check-in** (`/demo-checkin`): DM each user their ordered items with `[Ate it] [Some left] [Didn't touch]` buttons. Writes `consumed` events and decrements lots FIFO. **No LLM.**

**Risk scoring** (`flows/rescue.py`): **deterministic**:
```python
risk = 3.0 / (days_left + 0.5) + 0.2 * lot.price + 0.1 * lot.qty_remaining
```

**Personaliser** (`agents/personaliser.py`): the wow moment. Gets leftovers + taste profiles of in-office users → top-3 items per person with a one-line reason. Posts:
- Public board to `#free-lunch`, sorted by risk, one Claim button per row
- Personal DM per in-office user: *"🛟 The falafel pot expires today and you've picked falafel three weeks running."*

---

## Slack setup (30 minutes)

1. api.slack.com/apps → **Create New App → From an app manifest**
2. Add all `/demo-*` slash commands (suggest, aggregate, deliver, checkin, rescue, sweep, reset)
3. **Socket Mode → generate app-level token** (`xapp-…`, scope `connections:write`)
4. **Install to workspace** → grab bot token (`xoxb-…`)
5. Both tokens go in `.env`

```python
# app.py — the whole entrypoint
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_surface import handlers

app = App(token=os.environ["SLACK_BOT_TOKEN"])
handlers.register(app)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
```

**Gotchas:** `ack()` within 3 seconds always; buttons carry state in `value` as strings; test in a DM before posting to the channel.

---

## Environment setup

```bash
pip install slack-bolt anthropic psycopg2-binary apscheduler python-dotenv
```

`.env` (copy from `.env.example`):
```
ANTHROPIC_API_KEY=sk-ant-...
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SUPABASE_URL=https://...supabase.co
SUPABASE_KEY=...
DATABASE_URL=postgresql://...
```

---

## Demo slash commands

| Command | Real-life trigger | What it does |
|---|---|---|
| `/demo-suggest` | Thu 10:00 | Posts meal picker to `#free-lunch` |
| `/demo-aggregate` | Fri 12:00 | Builds the two baskets, posts for Approve |
| `/demo-deliver` | Mon/Wed arrival | Creates inventory lots |
| `/demo-checkin` | Fri 09:30 | Sends check-in DMs |
| `/demo-rescue` | Fri 11:30 | Posts rescue board + personal DMs |
| `/demo-sweep` | Fri 16:00 | Logs waste, posts weekly digest + leaderboard |
| `/demo-reset` | Any time | Resets to clean seeded demo state |

---

## 3-minute demo script

Open on a photo of the actual Friday fridge graveyard.  
*"We spend £X a week on lunch and bin roughly a third of it. Nobody knows what's in there. So we gave the fridge two agents."*

| Time | Beat | You run | Judges see |
|---|---|---|---|
| 0:20 | Ordering | `/demo-suggest` | Meal picker; teammate taps a meal |
| 0:40 | Agentic bit | Teammate types messy freeform in modal | Bot DMs back a correctly parsed plan seconds later |
| 1:10 | Aggregation | `/demo-aggregate` | Two baskets, Approve tap → CSV. *"45 mins of ordering admin, gone."* |
| 1:40 | Fast-forward to Friday | `/demo-deliver` then `/demo-checkin` | Check-in DM; teammate taps Ate/Some in ~5s |
| 2:00 | The wow | `/demo-rescue` | Public board + personalised DM — read the reason aloud |
| 2:20 | The moment | Teammate taps **Claim** | Threaded "£3.50 saved" + dashboard counter **ticks live** |
| 2:45 | Close | `/demo-sweep` | Digest + leaderboard. *"It runs itself weekly. Humans do three taps: pick, approve, claim."* |

**Per-criterion talking points:**
- **Impact:** whole company, zero install, in the tool everyone already lives in; generalises to any recurring office order
- **Efficiency:** quantify — ordering admin minutes eliminated, £/week waste baseline vs saved
- **Wow:** personalised DM with a *reason*, live counter, freeform-to-basket parsing on stage
- **Platform expansion:** agents at every stage; humans reduced to pick/approve/claim

---

## Timeline (1.5 days ≈ 12 focused hours each)

| When | What | Done when… |
|---|---|---|
| **D1 09:00–10:00** | All three together: Slack app, Supabase project, repo scaffold, write `contracts.md`, split catalogue seeding | Everyone can run `app.py` and see the bot online |
| **D1 10:00–13:00** | Parallel tracks | **M1 — tracer bullet:** button tap → `events` row → dashboard counter. Prove the whole stack once, thinly. |
| **D1 13:00–18:00** | Basket flow end to end | **M2:** suggest → picks + freeform parse → aggregate → approve → deliver → lots on dashboard |
| **D1 evening (opt, 2h)** | Check-in DMs + rescue board skeleton | Board posts with working claim buttons |
| **D2 09:00–11:30** | Rescue flow complete + personalised DMs | **M3:** claim → threaded reply → counter ticks live |
| **D2 11:30–12:30** | Digest, leaderboard, dashboard polish, `/demo-reset`, seeded demo data | **M4:** full demo runs from a clean reset |
| **D2 12:30–13:30** | Rehearse demo twice, fix what breaks, screen-record backup | Demo runs from `main` with wifi down |

**If a milestone slips:** cut from the stretch list — never from the demo path.

---

## Division of work

**Track A — Slack surface** (owns everything employees see)  
Manifest, Bolt wiring, all Block Kit builders, handlers, `/demo-*` commands, APScheduler. Calls only `agents/*`, `flows/*`, and `store.*` — never raw SQL.

**Track B — Intelligence** (owns everything the system decides)  
`loop.py`, tool definitions, the three prompts + fixtures, deterministic aggregator and risk scorer, digest copy. Success = `run_fixtures.py` produces sensible output for all ~10 fixtures.

**Track C — Data, dashboard, demo ops** (owns truth and the pitch)  
Schema + views, `store.py` (stub all signatures by D1 10:30 to unblock A and B), seed scripts, dashboard, `demo_reset.py`, seeded demo data, demo script. C is the integrator — runs `main` at every checkpoint.

**Working agreements:**
- Integrate only through `store.py` and `contracts.md`
- Changing a signature = tell the group first
- Merge to `main` at every checkpoint; demo only from `main`
- Hardcode nothing that `/demo-reset` can't restore

---

## Gamification data sources

| Source | Data available |
|---|---|
| Slack interactions | Who voted what + when, claim response times, participation rates |
| Sainsbury's orders | Item prices (£ waste value), category patterns, order history trends |
| Inventory tracker | Quantity claimed vs expired per item, consistently rescued vs wasted items |
| User profiles (over time) | Personal rescue score, vote accuracy score, attendance vs ordering ratio |

**Live gamification surfaces:**
- £ saved leaderboard (updated on every claim)
- Rescue Hero of the Week (most items claimed)
- Prediction accuracy badge (voted for = actually ate)
- Weekly streak counter
- Department vs department waste reduction %
- Friday Fridge health bar (live on dashboard)

---

## Cut list (cut in this order if behind)

1. Notion sync
2. Playwright real-cart checkout (mock stays)
3. Next.js dashboard → Streamlit
4. Personalised DMs → board sorted by expiry only *(hurts wow — cut late)*
5. Taste profiles → static dietary tags

**Never cut:** one-tap claim, the live counter, the Approve step, `/demo-reset`.

---

## Stretch goals (only after M4)

- **Fridge-cam reconciliation** — Friday photo of open fridge → vision call lists contents → auto-diff against inventory (~2h, very demoable, high wow)
- **Playwright cart-filler** on sainsburys.co.uk for the final flourish
- **Food-bank hand-off** — sweep posts an Olio/City Harvest link for unclaimed edible items
- **Notion mirror** of the waste log
- **Taste profile cards** — *"You are 78% wrap person."*

---

## Prompt sketches

**Parser** (`agents/prompts/parser.md`):
> You turn an employee's free-text lunch request into product lines from our catalogue. Use `search_products` to find real items; use `get_user_prefs` for dietary constraints — never violate them. Quantities are in units as sold. If the request implies multiple days, multiply. When confident, finish by calling `submit_meal_plan`. If something is impossible (not stocked, needs a hob), pick the closest alternative and say so in `notes` — do not invent products.

**Personaliser** (`agents/prompts/personaliser.md`):
> Given leftover items (with expiry and price) and each person's taste profile, pick up to 3 items per person they're genuinely likely to eat. Prioritise items expiring soonest. For each, write one warm, specific line referencing their history. Never guilt-trip. Finish by calling `submit_matches`.

**Suggester** (`agents/prompts/suggester.md`):
> Suggest 5 meals for next week from the catalogue. Hard constraints: no hob, no oven, survives 2+ days refrigerated. Cover the dietary needs provided. Favour variety vs the last 2 weeks (provided). Finish by calling `submit_suggestions`.

**Fixtures to write first (10 min):** three messy freeform requests (one with a dietary conflict, one multi-day, one impossible item), two taste profiles, one leftovers list. If prompts handle these, they'll handle the demo.

---

## Poor man's evals (build this — seriously)

Prompts live in `agents/prompts/*.md`. A `agents/fixtures/` folder holds ~10 real example inputs. A 20-line script runs every fixture through the agent and prints results. Rerun after every prompt tweak.

This takes 20 minutes to set up and saves hours of "wait, did my change break the other case?"
