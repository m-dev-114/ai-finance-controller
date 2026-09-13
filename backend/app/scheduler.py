"""
Best-effort in-process scheduler. Fine for local development or a
continuously-running server; not reliable on a free-tier host that spins
down on idle (Render's web services included) — for production, prefer a
real cron trigger hitting POST /reconcile/run instead (see render.yaml,
which includes a Cron Job service example that does exactly this).
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

from .database import SessionLocal
from .service import perform_reconciliation
from .config import RECONCILE_INTERVAL_MINUTES

logger = logging.getLogger("scheduler")
_scheduler = None


def _scheduled_run():
    db = SessionLocal()
    try:
        run = perform_reconciliation(db)
        logger.info("Scheduled reconciliation run %s completed: %s", run.id, run.stats)
    except Exception:
        logger.exception("Scheduled reconciliation run failed")
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _scheduled_run, "interval", minutes=RECONCILE_INTERVAL_MINUTES,
        id="reconcile_job", next_run_time=None,
    )
    _scheduler.start()
    logger.info("In-process scheduler started: every %s minute(s).", RECONCILE_INTERVAL_MINUTES)


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
