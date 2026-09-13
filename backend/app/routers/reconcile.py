import csv
import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    ReconciliationRun, Transaction, SettlementItem, BankStatementLine,
    LedgerEntry, AuditLogEntry, SettlementBatch, ExceptionRecord
)
from ..schemas import RunSummary
from ..importer import load_import, preview_import, ImportValidationError
from ..service import perform_reconciliation
from ..auth import require_api_key
from ..example_data import build_example_csvs

router = APIRouter(prefix="/reconcile", tags=["reconcile"])


def _wipe_all_data(db: Session):
    """Delete in dependency order (children before parents). Used by both
    /seed and /import so neither one silently piles on top of old data."""
    db.query(AuditLogEntry).delete()
    db.query(ExceptionRecord).delete()
    db.query(ReconciliationRun).delete()
    db.query(LedgerEntry).delete()
    db.query(BankStatementLine).delete()
    db.query(SettlementItem).delete()
    db.query(SettlementBatch).delete()
    db.query(Transaction).delete()
    db.commit()


@router.post("/run", response_model=RunSummary, dependencies=[Depends(require_api_key)])
def trigger_reconciliation(db: Session = Depends(get_db)):
    return perform_reconciliation(db)


@router.get("/runs", response_model=list[RunSummary])
def list_runs(db: Session = Depends(get_db)):
    return db.query(ReconciliationRun).order_by(ReconciliationRun.started_at.desc()).all()


@router.get("/runs/{run_id}/report.csv")
def export_run_report(run_id: str, db: Session = Depends(get_db)):
    """A downloadable CSV summary of one run: the run's own stats, followed
    by every exception it produced and how it was resolved. Meant to be
    handed to an auditor or attached to a month-end close, not just viewed
    in the dashboard."""
    run = db.query(ReconciliationRun).get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    exceptions = (
        db.query(ExceptionRecord)
        .filter(ExceptionRecord.run_id == run_id)
        .order_by(ExceptionRecord.created_at.asc())
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Reconciliation Run Report"])
    writer.writerow(["run_id", run.id])
    writer.writerow(["started_at", run.started_at])
    writer.writerow(["finished_at", run.finished_at])
    writer.writerow(["status", run.status])
    writer.writerow([])
    writer.writerow(["Summary"])
    for k, v in (run.stats or {}).items():
        writer.writerow([k, v])
    writer.writerow([])
    writer.writerow(["Exceptions"])
    writer.writerow([
        "id", "level", "status", "confidence", "amount_delta",
        "hypothesis", "resolved_by", "resolved_at",
    ])
    for exc in exceptions:
        writer.writerow([
            exc.id, exc.level, exc.status, exc.confidence, exc.amount_delta,
            exc.hypothesis, exc.resolved_by, exc.resolved_at,
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="reconciliation_report_{run_id}.csv"'},
    )


@router.post("/seed", dependencies=[Depends(require_api_key)])
def seed_dataset(db: Session = Depends(get_db)):
    """Wipes all existing data and generates a fresh sample dataset.
    Without the wipe, repeated clicks would keep appending on top of
    whatever's already there, growing the dataset and duplicating exceptions."""
    from ..seed import generate_sample_dataset

    _wipe_all_data(db)
    result = generate_sample_dataset(db)
    return {"message": "Sample dataset generated (previous data cleared)", **result}


@router.post("/import/preview")
async def preview_import_endpoint(
    settlement_csv: UploadFile = File(...),
    bank_csv: UploadFile = File(...),
):
    """Validates and summarizes the two CSVs WITHOUT writing anything to
    the database, so the UI can show row counts and catch format errors
    before the user commits to an import."""
    try:
        settlement_bytes = await settlement_csv.read()
        bank_bytes = await bank_csv.read()
        return preview_import(settlement_bytes, bank_bytes)
    except ImportValidationError as e:
        raise HTTPException(400, str(e))


@router.post("/import", dependencies=[Depends(require_api_key)])
async def import_dataset(
    settlement_csv: UploadFile = File(...),
    bank_csv: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Replaces all existing data with what's in the two uploaded CSVs.
    Same wipe-then-load approach as /seed, for the same reason: an
    accountant re-uploading a corrected file shouldn't have to worry about
    stacking on top of the previous (wrong) one."""
    try:
        settlement_bytes = await settlement_csv.read()
        bank_bytes = await bank_csv.read()
        # Validate before wiping anything, so a bad file doesn't destroy
        # good data.
        preview_import(settlement_bytes, bank_bytes)
        _wipe_all_data(db)
        result = load_import(db, settlement_bytes, bank_bytes)
        return {"message": "Data imported (previous data cleared)", **result}
    except ImportValidationError as e:
        raise HTTPException(400, str(e))


@router.get("/import/template/settlement", response_class=PlainTextResponse)
def settlement_template():
    """Minimal format reference — just enough rows to show every column
    and status value. For something bigger to actually experiment with,
    see /import/example/settlement."""
    return (
        "transaction_id,customer_id,amount,fee,tax,currency,status,created_at,"
        "settlement_utr,settled_net_amount,settlement_date\n"
        "txn_00001,cust_1001,1200.00,24.00,4.32,INR,captured,2026-08-01T10:15:00,"
        "utr_A100,1171.68,2026-08-03T00:00:00\n"
        "txn_00002,cust_1002,850.50,17.01,3.06,INR,captured,2026-08-01T11:02:00,"
        "utr_A100,830.43,2026-08-03T00:00:00\n"
        "txn_00003,cust_1003,500.00,10.00,1.80,INR,refunded,2026-08-01T12:30:00,,,\n"
        "txn_00004,cust_1004,2200.00,0,0,INR,failed,2026-08-01T13:10:00,,,\n"
    )


@router.get("/import/template/bank", response_class=PlainTextResponse)
def bank_template():
    return (
        "value_date,amount,utr_reference,narrative\n"
        "2026-08-03T00:00:00,2002.11,utr_A100,RAZORPAY SETTLEMENT\n"
    )


@router.get("/import/example/settlement", response_class=PlainTextResponse)
def settlement_example():
    """A bigger, richer example dataset (~40 transactions across several
    settlement batches) that exercises every exception pattern the agent
    knows how to investigate — a double-deducted fee, a bank charge that
    matches a known slab, an unexplained shortfall, and a delayed refund.
    Good for actually trying the import flow end-to-end."""
    settlement_csv, _ = build_example_csvs()
    return settlement_csv


@router.get("/import/example/bank", response_class=PlainTextResponse)
def bank_example():
    _, bank_csv = build_example_csvs()
    return bank_csv
