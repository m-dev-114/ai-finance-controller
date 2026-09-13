import datetime as dt
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ExceptionRecord, AuditLogEntry
from ..schemas import ExceptionOut, ResolveExceptionRequest, AuditLogOut, BulkResolveRequest, BulkResolveResult
from ..auth import require_api_key

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


@router.get("", response_model=List[ExceptionOut])
def list_exceptions(status: Optional[str] = None, level: Optional[str] = None,
                     db: Session = Depends(get_db)):
    q = db.query(ExceptionRecord)
    if status:
        q = q.filter(ExceptionRecord.status == status)
    if level:
        q = q.filter(ExceptionRecord.level == level)
    return q.order_by(ExceptionRecord.created_at.desc()).all()


@router.get("/{exception_id}", response_model=ExceptionOut)
def get_exception(exception_id: str, db: Session = Depends(get_db)):
    exc = db.query(ExceptionRecord).get(exception_id)
    if not exc:
        raise HTTPException(404, "Exception not found")
    return exc


@router.get("/{exception_id}/audit", response_model=List[AuditLogOut])
def get_exception_audit_trail(exception_id: str, db: Session = Depends(get_db)):
    return (
        db.query(AuditLogEntry)
        .filter(AuditLogEntry.exception_id == exception_id)
        .order_by(AuditLogEntry.created_at.asc())
        .all()
    )


@router.post("/{exception_id}/resolve", response_model=ExceptionOut, dependencies=[Depends(require_api_key)])
def resolve_exception(exception_id: str, body: ResolveExceptionRequest,
                       db: Session = Depends(get_db)):
    exc = db.query(ExceptionRecord).get(exception_id)
    if not exc:
        raise HTTPException(404, "Exception not found")

    exc.status = body.outcome
    exc.resolved_at = dt.datetime.utcnow()
    exc.resolved_by = body.resolved_by
    db.add(exc)
    db.add(AuditLogEntry(
        exception_id=exc.id, run_id=exc.run_id, actor=body.resolved_by,
        action=f"human_{body.outcome}",
        detail=body.note or "Resolved by a human reviewer via the dashboard.",
        data_snapshot={"previous_confidence": exc.confidence},
    ))
    db.commit()
    db.refresh(exc)
    return exc


@router.post("/bulk-resolve", response_model=BulkResolveResult, dependencies=[Depends(require_api_key)])
def bulk_resolve_exceptions(body: BulkResolveRequest, db: Session = Depends(get_db)):
    """Resolve or dismiss several exceptions in one call — a real finance
    controller triages in batches, not one row at a time."""
    updated, skipped = [], []
    for exception_id in body.exception_ids:
        exc = db.query(ExceptionRecord).get(exception_id)
        if not exc or exc.status not in ("needs_review", "open"):
            skipped.append(exception_id)
            continue
        exc.status = body.outcome
        exc.resolved_at = dt.datetime.utcnow()
        exc.resolved_by = body.resolved_by
        db.add(exc)
        db.add(AuditLogEntry(
            exception_id=exc.id, run_id=exc.run_id, actor=body.resolved_by,
            action=f"human_{body.outcome}",
            detail=body.note or "Bulk-resolved via the dashboard.",
            data_snapshot={"previous_confidence": exc.confidence, "bulk": True},
        ))
        updated.append(exception_id)
    db.commit()
    return BulkResolveResult(updated=updated, skipped=skipped)
