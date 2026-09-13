"""
Imports real reconciliation data from two CSVs, replacing the synthetic
seed for production use. Column formats below are intentionally close to
what a Razorpay settlement report and a bank statement export actually
look like — adjust the column names in `SETTLEMENT_COLUMNS` /
`BANK_COLUMNS` if your export differs.

Settlement CSV — one row per transaction line item:
    transaction_id, customer_id, amount, fee, tax, currency, status,
    created_at, settlement_utr, settled_net_amount, settlement_date

    - status: "captured" | "failed" | "refunded"
    - settlement_utr: blank for transactions not yet settled
    - settled_net_amount: what was actually credited for this line within
      the settlement batch (compared against amount - fee - tax)

Bank statement CSV — one row per bank credit:
    value_date, amount, utr_reference, narrative

    - utr_reference should match a settlement_utr from the settlement CSV
      so the two can be linked at the batch level.
"""
import csv
import io
import datetime as dt
from collections import defaultdict

from .models import (
    Transaction, SettlementBatch, SettlementItem, BankStatementLine, LedgerEntry
)

SETTLEMENT_COLUMNS = [
    "transaction_id", "customer_id", "amount", "fee", "tax", "currency",
    "status", "created_at", "settlement_utr", "settled_net_amount", "settlement_date",
]
BANK_COLUMNS = ["value_date", "amount", "utr_reference", "narrative"]


class ImportValidationError(Exception):
    pass


def _parse_date(value: str) -> dt.datetime:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ImportValidationError(f"Unrecognized date format: {value!r}")


def _read_csv(file_bytes: bytes, required_columns: list) -> list[dict]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ImportValidationError("CSV appears to be empty.")
    missing = [c for c in required_columns if c not in reader.fieldnames]
    if missing:
        raise ImportValidationError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Found columns: {', '.join(reader.fieldnames)}"
        )
    return list(reader)


def preview_import(settlement_bytes: bytes, bank_bytes: bytes) -> dict:
    """Parse and validate without writing to the database — lets the UI
    show row counts and catch format errors before committing."""
    settlement_rows = _read_csv(settlement_bytes, SETTLEMENT_COLUMNS)
    bank_rows = _read_csv(bank_bytes, BANK_COLUMNS)

    statuses = defaultdict(int)
    utrs = set()
    for row in settlement_rows:
        statuses[row.get("status", "captured") or "captured"] += 1
        if row.get("settlement_utr"):
            utrs.add(row["settlement_utr"])

    return {
        "settlement_rows": len(settlement_rows),
        "bank_rows": len(bank_rows),
        "status_breakdown": dict(statuses),
        "distinct_settlement_batches": len(utrs),
    }


def load_import(db, settlement_bytes: bytes, bank_bytes: bytes) -> dict:
    settlement_rows = _read_csv(settlement_bytes, SETTLEMENT_COLUMNS)
    bank_rows = _read_csv(bank_bytes, BANK_COLUMNS)

    # --- group settlement rows into batches by UTR ---
    batches_by_utr: dict[str, SettlementBatch] = {}
    batch_dates: dict[str, dt.datetime] = {}
    batch_totals: dict[str, float] = defaultdict(float)

    txn_count = settled_count = refund_count = failed_count = 0

    for row in settlement_rows:
        status = (row.get("status") or "captured").strip().lower()
        amount = float(row["amount"])
        fee = float(row.get("fee") or 0)
        tax = float(row.get("tax") or 0)
        created_at = _parse_date(row["created_at"])

        txn = Transaction(
            id=row["transaction_id"] or None,
            customer_id=row["customer_id"],
            amount=amount, fee=fee, tax=tax,
            currency=row.get("currency") or "INR",
            status=status,
            created_at=created_at,
        )
        db.add(txn)
        txn_count += 1

        if status == "captured":
            db.add(LedgerEntry(
                transaction_id=txn.id, entry_type="revenue",
                amount=round(amount - fee - tax, 2), recognized_date=created_at,
            ))
        elif status == "refunded":
            db.add(LedgerEntry(
                transaction_id=txn.id, entry_type="refund",
                amount=-amount, recognized_date=created_at,
            ))
            refund_count += 1
        elif status == "failed":
            failed_count += 1

        utr = row.get("settlement_utr")
        if utr and status == "captured":
            settled_count += 1
            batch_totals[utr] += float(row["settled_net_amount"])
            if utr not in batch_dates:
                batch_dates[utr] = _parse_date(row.get("settlement_date") or row["created_at"])

    db.flush()

    for utr, total in batch_totals.items():
        batch = SettlementBatch(
            id=utr, settlement_date=batch_dates[utr], batch_amount=round(total, 2),
        )
        db.add(batch)
        batches_by_utr[utr] = batch
    db.flush()

    for row in settlement_rows:
        utr = row.get("settlement_utr")
        if utr and (row.get("status") or "captured").strip().lower() == "captured":
            db.add(SettlementItem(
                batch_id=utr,
                transaction_id=row["transaction_id"],
                net_amount=float(row["settled_net_amount"]),
            ))

    for row in bank_rows:
        db.add(BankStatementLine(
            value_date=_parse_date(row["value_date"]),
            amount=float(row["amount"]),
            utr_reference=row.get("utr_reference") or None,
            narrative=row.get("narrative") or None,
        ))

    db.commit()

    return {
        "transactions_imported": txn_count,
        "captured": settled_count + (txn_count - settled_count - refund_count - failed_count),
        "settled_line_items": settled_count,
        "refunds": refund_count,
        "failed": failed_count,
        "settlement_batches": len(batches_by_utr),
        "bank_lines_imported": len(bank_rows),
    }
