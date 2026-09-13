from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReconciliationRun, ExceptionRecord, Transaction
from ..schemas import MetricsOut, TrendOut, TrendPoint

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=MetricsOut)
def get_metrics(db: Session = Depends(get_db)):
    runs = db.query(ReconciliationRun).order_by(ReconciliationRun.started_at.desc()).all()
    latest = runs[0] if runs else None

    all_exceptions = db.query(ExceptionRecord).all()
    total_exc = len(all_exceptions)
    auto_cleared = len([e for e in all_exceptions if e.status == "auto_cleared"])
    auto_clear_rate = round(auto_cleared / total_exc, 3) if total_exc else 0.0

    resolved = [e for e in all_exceptions if e.resolved_at]
    if resolved:
        avg_minutes = sum(
            (e.resolved_at - e.created_at).total_seconds() / 60 for e in resolved
        ) / len(resolved)
    else:
        avg_minutes = None

    by_status = {}
    for e in all_exceptions:
        by_status[e.status] = by_status.get(e.status, 0) + 1

    # aggregate match rate by level across all runs' stats
    l1_m = l1_e = l2_m = l2_e = l3_m = l3_e = 0
    for r in runs:
        s = r.stats or {}
        l1_m += s.get("l1_matched", 0); l1_e += s.get("l1_exceptions", 0)
        l2_m += s.get("l2_matched", 0); l2_e += s.get("l2_exceptions", 0)
        l3_m += s.get("l3_matched", 0); l3_e += s.get("l3_exceptions", 0)

    def rate(m, e):
        return round(m / (m + e), 3) if (m + e) else 0.0

    return MetricsOut(
        total_runs=len(runs),
        latest_run=latest,
        auto_clear_rate=auto_clear_rate,
        avg_resolution_minutes=round(avg_minutes, 1) if avg_minutes is not None else None,
        exceptions_by_status=by_status,
        match_rate_by_level={
            "transaction": rate(l1_m, l1_e),
            "batch": rate(l2_m, l2_e),
            "ledger": rate(l3_m, l3_e),
        },
        total_transactions_in_dataset=db.query(Transaction).count(),
    )


@router.get("/trend", response_model=TrendOut)
def get_trend(db: Session = Depends(get_db)):
    """Per-run history for the trend charts: match rate and exception
    volume over time, one point per completed reconciliation run."""
    runs = (
        db.query(ReconciliationRun)
        .filter(ReconciliationRun.status == "completed")
        .order_by(ReconciliationRun.started_at.asc())
        .all()
    )
    points = []
    for r in runs:
        s = r.stats or {}
        matched = s.get("l1_matched", 0) + s.get("l2_matched", 0) + s.get("l3_matched", 0)
        total = matched + s.get("total_exceptions", 0)
        match_rate = round(matched / total, 4) if total else 0.0
        points.append(TrendPoint(
            run_id=r.id, started_at=r.started_at, match_rate=match_rate,
            total_exceptions=s.get("total_exceptions", 0),
            auto_cleared=s.get("auto_cleared", 0),
            needs_review=s.get("needs_review", 0),
        ))
    return TrendOut(points=points)
