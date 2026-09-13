import os

# Database: works against local SQLite out of the box, or Supabase/Postgres via DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finance_controller.db")

# Optional LLM provider for the investigation agent's natural-language explanations.
# If neither key is set, the agent falls back to a deterministic, rule-based explainer
# so the whole system runs end-to-end with zero external dependencies.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_PROVIDER = "groq" if GROQ_API_KEY else ("openai" if OPENAI_API_KEY else "none")

# Auto-clear threshold: exceptions with agent confidence >= this are auto-resolved.
# Configurable per deployment (env var) rather than hardcoded, per finance-controls best practice.
AUTO_CLEAR_CONFIDENCE = float(os.getenv("AUTO_CLEAR_CONFIDENCE", "0.9"))

# Settlement lag tolerance windows (days) for ledger <-> settlement matching
SETTLEMENT_LAG_MIN_DAYS = int(os.getenv("SETTLEMENT_LAG_MIN_DAYS", "1"))
SETTLEMENT_LAG_MAX_DAYS = int(os.getenv("SETTLEMENT_LAG_MAX_DAYS", "4"))

# Amount tolerance for floating point / rounding differences (in currency units)
AMOUNT_TOLERANCE = float(os.getenv("AMOUNT_TOLERANCE", "0.01"))

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Optional shared-secret protection for mutating endpoints (run, seed, import,
# resolve, settings). Leave unset for open local dev; set it in production so
# a scheduled cron job (or anyone else) needs the header to trigger a run.
RECONCILE_API_KEY = os.getenv("RECONCILE_API_KEY", "")

# Slack incoming-webhook URL for run-completion notifications. Leave unset to
# skip notifications entirely (no external calls).
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
# Notify whenever a run leaves at least this many exceptions needing review.
NOTIFY_MIN_NEEDS_REVIEW = int(os.getenv("NOTIFY_MIN_NEEDS_REVIEW", "1"))

# Best-effort in-process scheduler for local/dev use. In production, prefer
# a real cron trigger (see render.yaml) since a free-tier web service that
# spins down on idle won't keep an in-process scheduler alive reliably.
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"
RECONCILE_INTERVAL_MINUTES = int(os.getenv("RECONCILE_INTERVAL_MINUTES", "60"))
