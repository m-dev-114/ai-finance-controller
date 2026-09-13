# AI Finance Controller

A multi-level payment reconciliation system with an agentic exception
investigator. Built to demonstrate production-grade thinking, not just a
demo: idempotent replay-safe matching, confidence-gated auto-resolution,
and a full audit trail for every automated decision.

## The problem

Money coming in through a payment gateway rarely matches cleanly against
the bank settlement file or the internal ledger — gateway fees, refunds,
partial settlements, bank charges, and timing lag all create discrepancies
that finance teams currently reconcile by hand. This system automates the
easy 90% deterministically and uses an LLM-backed agent only for the
residue that needs real investigation — never the other way around.

## Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   React      │────▶│   FastAPI backend     │────▶│   Postgres /     │
│   dashboard  │◀────│   (matching + agent)  │◀────│   Supabase       │
└─────────────┘     └──────────────────────┘     └─────────────────┘
```

**Three-level deterministic matching** (`app/matching.py`) — runs first,
is cheap, and never needs an LLM:
1. **Transaction ↔ settlement item** — does the net amount settled match
   `amount - fee - tax`?
2. **Settlement batch ↔ bank credit(s)** — does the bank statement total
   match what the gateway says it settled (handles split settlements
   across multiple bank credits)?
3. **Ledger ↔ settlement** — was revenue recognized within the expected
   T+1 to T+4 settlement lag window? Are refunds/chargebacks eventually
   offset?

**Idempotent by design** — re-running a reconciliation against unchanged
data (or replaying after a corrected file lands) does not create duplicate
exceptions. Each discrepancy is deduplicated by its underlying record
references, not by run ID, so a scheduled nightly job can safely re-run
without double-counting.

**LangGraph investigation agent** (`app/agent.py`) — only invoked on the
residue the deterministic engine couldn't resolve. Each investigative
step is a discrete graph node (fee-mismatch check, split/shortfall check,
timing-lag check), so the `reasoning_trail` returned to the API is the
literal node-by-node path the agent took — not a black-box verdict. An
LLM (Groq or OpenAI, whichever key is set) is used only to phrase the
final explanation in plain English; with no key configured, a
deterministic template produces the same structured output, so the whole
pipeline runs end-to-end with zero external dependencies.

**Confidence-gated auto-resolution** — exceptions that match a known,
recognizable pattern (e.g. a gateway fee deducted twice, a bank charge
matching a known slab) score high confidence and auto-clear. Anything
else is flagged `needs_review` for a human. The threshold
(`AUTO_CLEAR_CONFIDENCE`, default `0.9`) is a config value, not a
hardcoded constant — a finance team can tune how conservative the system
is.

**Immutable audit trail** — every automated decision (auto-clear, flag,
human resolution) is written to `audit_log` with the data snapshot that
informed it. "The AI decided" is never an acceptable answer in an audit;
this makes every decision traceable.

## Project structure

```
backend/
  app/
    main.py            FastAPI app + router registration
    config.py           env-driven settings (thresholds, tolerances, LLM keys)
    models.py            SQLAlchemy models — the full data model
    database.py         engine/session setup (SQLite locally, Postgres in prod)
    schemas.py            Pydantic response/request models
    matching.py         deterministic 3-level matching engine (idempotent)
    agent.py             LangGraph investigation agent + rule-based fallback
    seed.py               synthetic but realistically-shaped sample dataset
    routers/
      reconcile.py        POST /reconcile/run, /reconcile/seed
      exceptions.py        GET/POST exception review + resolution
      metrics.py            match rates, auto-clear rate, resolution time
  requirements.txt
  render.yaml            Render deploy config
  supabase_schema.sql    reference schema (also auto-created by SQLAlchemy)
  .env.example
frontend/
  src/
    App.jsx               top-level layout + state
    api.js                 fetch client
    format.js              currency/time/status formatting
    components/
      Header.jsx, MetricsStrip.jsx, QueueTabs.jsx,
      ExceptionList.jsx, ExceptionRow.jsx
  vite.config.js, vercel.json, .env.example
```

## Feature reference

**Trend dashboard** — the *Trends* tab in the dashboard shows match rate
and exception volume per run (`GET /metrics/trend`), plus a run history
list with a CSV download for each one.

**Bulk actions + smarter queue** — select multiple needs-review rows and
resolve/dismiss them together (`POST /exceptions/bulk-resolve`). The
queue also supports free-text search (by ID, level, or hypothesis) and
sorting by amount, confidence, or age — all client-side, since exception
volumes here are small enough not to need server-side pagination yet.

**Scheduled runs + notifications** — for local/continuous use, set
`ENABLE_SCHEDULER=true` and `RECONCILE_INTERVAL_MINUTES` to run an
in-process APScheduler job automatically. For production on a host that
sleeps on idle (Render's free tier included), use a real cron trigger
instead — `render.yaml` includes a Cron Job service example that simply
calls `POST /reconcile/run` on a schedule. Set `SLACK_WEBHOOK_URL` to get
a Slack message after any run that leaves exceptions needing review,
listing the largest discrepancies first.

**Configurable threshold from the UI** — the auto-clear confidence
threshold is stored in the database (`app_settings` table), not just an
env var, so it's editable live from the dashboard's *Auto-clear settings*
panel without a redeploy. The panel calls `GET /settings/simulate` to
show, live, how many already-scored exceptions would flip between
auto-clear and needs-review at a candidate threshold, before you save it.
Saving also calls `POST /settings/reevaluate`, which retroactively
promotes existing `needs_review` exceptions whose already-computed
confidence now clears the new (lower) threshold — without this, changing
the threshold would have no visible effect until a future reconciliation
run on entirely new data, since `/reconcile/run` deliberately skips
anything already tracked as an exception (that's the idempotency that
makes replays safe). Note: raising the threshold never retroactively
un-clears something already auto-cleared — that decision was valid when
it was made. Also note the practical ceiling: no single investigation
check currently scores above ~92% confidence, so setting the threshold
above that will stop auto-clearing anything.

**Exportable reconciliation report** — `GET /reconcile/runs/{id}/report.csv`
returns a CSV with the run's summary stats and every exception it
produced, including how each was resolved and by whom. Downloadable from
the Trends tab's run history.

**Optional API key** — mutating endpoints (`/reconcile/run`, `/seed`,
`/import`, exception resolution, `/settings` updates) accept an
`X-Api-Key` header. Set `RECONCILE_API_KEY` to require it — this is what
lets you expose the reconciliation-trigger endpoint to a cron job without
leaving it open to the public internet. Leave it unset for local dev.

## Getting data in

Two ways:
- **Generate sample data** — a synthetic 120-transaction dataset with
  deliberately injected mismatches. Good for a first look.
- **Import CSVs** — upload a real settlement report and bank statement.
See `backend/app/importer.py` for the exact expected columns. Two
downloadable references are linked in the dashboard's Import panel:
a minimal *format reference* (a handful of rows covering every column
and status value) and a bigger *example dataset* (~40 transactions,
`backend/app/example_data.py`) that exercises every exception pattern
the agent knows how to investigate — good for actually trying the
end-to-end flow rather than just checking the column names.
`POST /reconcile/import/preview` validates and summarizes a pair of
files before anything is written.

Both operations **replace** whatever data currently exists — re-clicking
"Generate sample data" or re-importing doesn't stack on top of the
previous dataset. This matches how you'd actually use it: a corrected
settlement file replaces the wrong one, it doesn't merge with it.

## Running locally

**Backend** (works out of the box with local SQLite, no API keys needed):
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Click **Generate sample data**, then
**Run reconciliation** to see the matching engine and agent work through
a synthetic 120-transaction dataset with deliberately injected mismatches
(a double-deducted fee, a bank wire charge, a split settlement, a
delayed refund).

## Deploying

**1. Database — Supabase**
- Create a project at [supabase.com](https://supabase.com).
- Grab the Postgres connection string from *Project Settings → Database*
  (use the *Session pooler* URI).
- Optionally run `backend/supabase_schema.sql` in the SQL editor — the
  app also creates these tables automatically on first boot.

**2. Backend — Render**
- Push this repo to GitHub, create a new Web Service on
  [render.com](https://render.com) pointed at `backend/`, or use the
  included `render.yaml` (Render will detect it as a Blueprint).
- Set env vars: `DATABASE_URL` (from Supabase), `CORS_ORIGINS` (your
  Vercel URL once you have it), and optionally `GROQ_API_KEY` or
  `OPENAI_API_KEY` for LLM-phrased explanations.
- Build command: `pip install -r requirements.txt`
  Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**3. Frontend — Vercel**
- Import `frontend/` as a new Vercel project (framework preset: Vite).
- Set env var `VITE_API_BASE_URL` to your Render backend URL.
- Deploy. Update the backend's `CORS_ORIGINS` to match the resulting
  Vercel URL.

## API reference

| Method | Path | Purpose |
|---|---|---|
| POST | `/reconcile/seed` | Generate the synthetic sample dataset (wipes existing data) |
| POST | `/reconcile/run` | Run matching + agent investigation |
| GET | `/reconcile/runs` | List past reconciliation runs |
| GET | `/reconcile/runs/{id}/report.csv` | Download a CSV report for one run |
| POST | `/reconcile/import/preview` | Validate + summarize CSVs without writing |
| POST | `/reconcile/import` | Import real settlement + bank CSVs (wipes existing data) |
| GET | `/reconcile/import/template/{settlement,bank}` | Minimal format-reference CSVs |
| GET | `/reconcile/import/example/{settlement,bank}` | Bigger example dataset to try |
| GET | `/exceptions?status=&level=` | List exceptions, optionally filtered |
| GET | `/exceptions/{id}` | Get one exception |
| GET | `/exceptions/{id}/audit` | Full audit trail for one exception |
| POST | `/exceptions/{id}/resolve` | Human resolve/dismiss one exception |
| POST | `/exceptions/bulk-resolve` | Human resolve/dismiss several at once |
| GET | `/metrics` | Match rates, auto-clear rate, avg resolution time |
| GET | `/metrics/trend` | Per-run history for trend charts |
| GET | `/settings` | Current auto-clear confidence threshold |
| POST | `/settings` | Update the threshold |
| POST | `/settings/reevaluate` | Retroactively apply the current threshold to existing exceptions |
| GET | `/settings/simulate?threshold=` | What-if: how many would auto-clear at X |

## Extending this further

- **Real Razorpay settlement reports**: swap `seed.py` for an importer
  that parses Razorpay's actual settlement CSV export format.
- **Scheduled runs**: add a cron trigger on Render (or a Supabase Edge
  Function) to call `/reconcile/run` nightly.
- **Multi-currency**: extend `matching.py` level 3 to apply FX rates at
  settlement date rather than transaction date.
- **Real bank feeds**: replace `BankStatementLine` seeding with an actual
  bank statement import (most Indian banks export MT940 or a proprietary
  CSV — either can map onto the existing model).
