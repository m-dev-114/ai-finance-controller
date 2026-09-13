from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import datetime as dt

from ..database import get_db
from ..models import ExceptionRecord, AuditLogEntry
from ..schemas import ThresholdOut, ThresholdUpdate, ThresholdSimulation, ReevaluateResult
from ..settings_store import get_auto_clear_confidence, set_auto_clear_confidence
from ..auth import require_api_key

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=ThresholdOut)
def get_settings(db: Session = Depends(get_db)):
    return ThresholdOut(auto_clear_confidence=get_auto_clear_confidence(db))


@router.post("", response_model=ThresholdOut, dependencies=[Depends(require_api_key)])
def update_settings(body: ThresholdUpdate, db: Session = Depends(get_db)):
    new_value = set_auto_clear_confidence(db, body.auto_clear_confidence)
    return ThresholdOut(auto_clear_confidence=new_value)


@router.post("/reevaluate", response_model=ReevaluateResult, dependencies=[Depends(require_api_key)])
def reevaluate_against_current_threshold(db: Session = Depends(get_db)):
    """Applies the current threshold to exceptions that were already scored
    under an older one. Without this, lowering the threshold has no visible
    effect until the next fresh reconciliation run — /reconcile/run skips
    anything already tracked as an exception (that's the idempotency that
    keeps replays safe), so it never re-scores existing needs_review items
    against a new threshold on its own.

    Only promotes needs_review -> auto_cleared when the existing (already
    computed) confidence now qualifies. Deliberately never demotes an
    already auto_cleared exception if the threshold is raised afterward —
    that decision was valid when it was made, and rewriting history
    downward is not something a threshold slider should be able to do."""
    threshold = get_auto_clear_confidence(db)
    candidates = (
        db.query(ExceptionRecord)
        .filter(ExceptionRecord.status == "needs_review")
        .filter(ExceptionRecord.confidence.isnot(None))
        .all()
    )
    promoted = []
    for exc in candidates:
        if exc.confidence >= threshold:
            exc.status = "auto_cleared"
            exc.resolved_at = dt.datetime.utcnow()
            exc.resolved_by = "agent"
            db.add(exc)
            db.add(AuditLogEntry(
                exception_id=exc.id, run_id=exc.run_id, actor="agent",
                action="auto_cleared_on_reevaluation",
                detail=f"Threshold changed to {threshold}; this exception's existing "
                       f"confidence ({exc.confidence}) now qualifies for auto-clear.",
                data_snapshot={"threshold": threshold, "confidence": exc.confidence},
            ))
            promoted.append(exc.id)
    db.commit()
    return ReevaluateResult(
        threshold=threshold, promoted=promoted,
        remaining_needs_review=len(candidates) - len(promoted),
    )


@router.get("/simulate", response_model=ThresholdSimulation)
def simulate_threshold(threshold: float, db: Session = Depends(get_db)):
    """Answers: 'if I moved the auto-clear threshold to X, how many of the
    exceptions the agent has already scored would auto-clear vs need
    review?' Uses each exception's already-computed confidence — no
    re-running the agent needed. Only considers exceptions the agent has
    scored (i.e. not still-open or already human-resolved) so a human's
    decision is never silently overridden by a slider."""
    scored = (
        db.query(ExceptionRecord)
        .filter(ExceptionRecord.confidence.isnot(None))
        .filter(ExceptionRecord.status.in_(["needs_review", "auto_cleared"]))
        .all()
    )
    would_auto_clear = sum(1 for e in scored if (e.confidence or 0) >= threshold)
    would_need_review = len(scored) - would_auto_clear
    current = get_auto_clear_confidence(db)
    return ThresholdSimulation(
        threshold=threshold,
        would_auto_clear=would_auto_clear,
        would_need_review=would_need_review,
        current_auto_clear_confidence=current,
    )
