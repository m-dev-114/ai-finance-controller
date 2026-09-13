"""
Deterministic matching engine. Runs BEFORE the agent touches anything —
cheap, fast, and exact matches never need an LLM call. Only residue that
fails deterministic matching gets escalated to the investigation agent.

Idempotent: re-running against the same data produces the same exceptions
(keyed by reference_ids), so a reconciliation_run can be safely replayed
when a corrected file lands.
"""
import datetime as dt
from sqlalchemy.orm import Session

from .models import (
    Transaction, SettlementItem, SettlementBatch, BankStatementLine,
    LedgerEntry, ExceptionRecord
)
from .config import AMOUNT_TOLERANCE, SETTLEMENT_LAG_MIN_DAYS, SETTLEMENT_LAG_MAX_DAYS


def _dedup_key(level: str, reference_ids: list) -> str:
    return f"{level}:{'|'.join(sorted(reference_ids))}"


def run_matching(db: Session, run_id: str):
    stats = {
        "l1_matched": 0, "l1_exceptions": 0,
        "l2_matched": 0, "l2_exceptions": 0,
        "l3_matched": 0, "l3_exceptions": 0,
        "already_tracked": 0,
    }
    exceptions = []

    # Idempotency: a discrepancy already surfaced in a previous run (whatever
    # its current status — open, needs_review, auto_cleared, or resolved)
    # must not be re-created here. This is what makes it safe to replay a
    # reconciliation run against unchanged data, or after a corrected file
    # lands, without double-counting the same underlying issue.
    existing_keys = {
        _dedup_key(e.level, e.reference_ids)
        for e in db.query(ExceptionRecord).all()
    }

    # ---------- Level 1: transaction <-> settlement item ----------
    items = db.query(SettlementItem).filter(SettlementItem.transaction_id.isnot(None)).all()
    txn_by_id = {t.id: t for t in db.query(Transaction).filter(Transaction.status == "captured").all()}

    for item in items:
        txn = txn_by_id.get(item.transaction_id)
        if not txn:
            continue
        expected_net = txn.net_amount
        delta = round(item.net_amount - expected_net, 2)
        if abs(delta) <= AMOUNT_TOLERANCE:
            stats["l1_matched"] += 1
        else:
            stats["l1_exceptions"] += 1
            key = _dedup_key("transaction", [txn.id, item.id])
            if key in existing_keys:
                stats["already_tracked"] += 1
                continue
            existing_keys.add(key)
            exceptions.append(ExceptionRecord(
                run_id=run_id, level="transaction",
                reference_ids=[txn.id, item.id],
                amount_delta=delta,
                status="open",
            ))

    # ---------- Level 2: settlement batch total <-> bank credit(s) ----------
    batches = db.query(SettlementBatch).all()
    for batch in batches:
        bank_lines = db.query(BankStatementLine).filter(
            BankStatementLine.utr_reference == batch.id
        ).all()
        bank_total = round(sum(l.amount for l in bank_lines), 2)
        delta = round(bank_total - batch.batch_amount, 2)
        if abs(delta) <= AMOUNT_TOLERANCE:
            stats["l2_matched"] += 1
        else:
            stats["l2_exceptions"] += 1
            ref_ids = [batch.id] + [l.id for l in bank_lines]
            key = _dedup_key("batch", ref_ids)
            if key in existing_keys:
                stats["already_tracked"] += 1
                continue
            existing_keys.add(key)
            exceptions.append(ExceptionRecord(
                run_id=run_id, level="batch",
                reference_ids=ref_ids,
                amount_delta=delta,
                status="open",
            ))

    # ---------- Level 3: ledger <-> settlement (with lag window) ----------
    ledger_entries = db.query(LedgerEntry).all()
    # map transaction_id -> its settlement batch settlement_date (via settlement item)
    item_by_txn = {i.transaction_id: i for i in items}
    batch_by_id = {b.id: b for b in batches}

    for entry in ledger_entries:
        item = item_by_txn.get(entry.transaction_id)
        if entry.entry_type == "revenue":
            if not item:
                stats["l3_exceptions"] += 1
                key = _dedup_key("ledger", [entry.id])
                if key in existing_keys:
                    stats["already_tracked"] += 1
                    continue
                existing_keys.add(key)
                exceptions.append(ExceptionRecord(
                    run_id=run_id, level="ledger",
                    reference_ids=[entry.id],
                    amount_delta=entry.amount,
                    status="open",
                ))
                continue
            batch = batch_by_id.get(item.batch_id)
            lag_days = (batch.settlement_date - entry.recognized_date).days
            if SETTLEMENT_LAG_MIN_DAYS <= lag_days <= SETTLEMENT_LAG_MAX_DAYS:
                stats["l3_matched"] += 1
            else:
                stats["l3_exceptions"] += 1
                ref_ids = [entry.id, item.id]
                key = _dedup_key("ledger", ref_ids)
                if key in existing_keys:
                    stats["already_tracked"] += 1
                    continue
                existing_keys.add(key)
                exceptions.append(ExceptionRecord(
                    run_id=run_id, level="ledger",
                    reference_ids=ref_ids,
                    amount_delta=round(lag_days - SETTLEMENT_LAG_MAX_DAYS, 2),
                    status="open",
                ))
        else:
            # refunds/chargebacks: no offsetting settlement debit modeled yet
            # in this dataset -> always residue for the agent to reason about.
            stats["l3_exceptions"] += 1
            key = _dedup_key("ledger", [entry.id])
            if key in existing_keys:
                stats["already_tracked"] += 1
                continue
            existing_keys.add(key)
            exceptions.append(ExceptionRecord(
                run_id=run_id, level="ledger",
                reference_ids=[entry.id],
                amount_delta=entry.amount,
                status="open",
            ))

    for exc in exceptions:
        db.add(exc)
    db.commit()
    for exc in exceptions:
        db.refresh(exc)

    return stats, exceptions
