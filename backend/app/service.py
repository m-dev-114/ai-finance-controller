import datetime as dt
from sqlalchemy.orm import Session

from .models import (
    ReconciliationRun, Transaction, BankStatementLine, LedgerEntry, AuditLogEntry
)
from .matching import run_matching
from .agent import investigate_exception
from .settings_store import get_auto_clear_confidence
from .notify import notify_run_complete


def _build_context(db: Session, exc):
    ctx = {}
    if exc.level == "transaction":
        txn_id = exc.reference_ids[0]
        txn = db.query(Transaction).get(txn_id)
        ctx["transaction"] = {
            "id": txn.id, "amount": txn.amount, "fee": txn.fee, "tax": txn.tax,
        } if txn else {}
    elif exc.level == "batch":
        bank_ids = exc.reference_ids[1:]
        lines = db.query(BankStatementLine).filter(BankStatementLine.id.in_(bank_ids)).all()
        ctx["bank_lines"] = [{"id": l.id, "amount": l.amount} for l in lines]
    elif exc.level == "ledger":
        entry = db.query(LedgerEntry).get(exc.reference_ids[0])
        ctx["ledger_entry"] = {
            "id": entry.id, "entry_type": entry.entry_type, "amount": entry.amount,
        } if entry else {}
        ctx["has_settlement_item"] = len(exc.reference_ids) > 1
    return ctx


def perform_reconciliation(db: Session) -> ReconciliationRun:
    run = ReconciliationRun(status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    threshold = get_auto_clear_confidence(db)
    stats, exceptions = run_matching(db, run.id)

    auto_cleared = 0
    scored = []
    for exc in exceptions:
        exc_dict = {"id": exc.id, "level": exc.level, "amount_delta": exc.amount_delta}
        context = _build_context(db, exc)
        result = investigate_exception(exc_dict, context, threshold=threshold)

        exc.confidence = result["confidence"]
        exc.hypothesis = result["hypothesis"]
        exc.reasoning_trail = result["checks"]

        if result["decision"] == "auto_clear":
            exc.status = "auto_cleared"
            exc.resolved_at = dt.datetime.utcnow()
            exc.resolved_by = "agent"
            auto_cleared += 1
            action = "auto_cleared"
        else:
            exc.status = "needs_review"
            action = "flagged_for_review"

        db.add(exc)
        db.add(AuditLogEntry(
            exception_id=exc.id, run_id=run.id, actor="agent", action=action,
            detail=exc.hypothesis,
            data_snapshot={"confidence": exc.confidence, "checks": exc.reasoning_trail,
                            "threshold_used": threshold},
        ))
        scored.append({
            "level": exc.level, "amount_delta": exc.amount_delta,
            "confidence": exc.confidence, "hypothesis": exc.hypothesis,
            "status": exc.status,
        })

    stats["total_exceptions"] = len(exceptions)
    stats["auto_cleared"] = auto_cleared
    stats["needs_review"] = len(exceptions) - auto_cleared
    stats["threshold_used"] = threshold

    run.status = "completed"
    run.finished_at = dt.datetime.utcnow()
    run.stats = stats
    db.add(run)
    db.add(AuditLogEntry(
        run_id=run.id, actor="system", action="run_completed",
        detail=f"Matched {stats.get('l1_matched',0)+stats.get('l2_matched',0)+stats.get('l3_matched',0)} "
               f"records deterministically; {len(exceptions)} exception(s) investigated, "
               f"{auto_cleared} auto-cleared (threshold {threshold}).",
        data_snapshot=stats,
    ))
    db.commit()
    db.refresh(run)

    top_needing_review = sorted(
        [s for s in scored if s["status"] == "needs_review"],
        key=lambda s: abs(s["amount_delta"] or 0), reverse=True,
    )
    notify_run_complete(run.id, stats, top_needing_review)

    return run
