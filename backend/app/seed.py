"""
Generates a realistic (but synthetic) dataset spanning:
  - transactions        (gateway captures)
  - settlement_batches / settlement_items  (gateway settlement report, UTR-batched)
  - bank_statement_lines (what actually hit the bank)
  - ledger_entries       (internal books: revenue + refunds)

Mismatches are deliberately injected so the matching engine and agent have
real work to do:
  L1 (txn <-> settlement item): a handful of items settle short (fee misapplied)
  L2 (batch total <-> bank line): one batch is split across two bank credits;
      one batch has a bank-side shortfall (bank charge deducted)
  L3 (ledger <-> settlement):    a refund recognized in the ledger before the
      matching debit settles (timing lag beyond the matching window); one
      failed-then-retried transaction produces two ledger/txn rows for one sale
"""
import random
import datetime as dt
from .models import (
    Transaction, SettlementBatch, SettlementItem, BankStatementLine, LedgerEntry,
    ReconciliationRun, ExceptionRecord, AuditLogEntry,
)

RAZORPAY_FEE_RATE = 0.02
GST_ON_FEE_RATE = 0.18

random.seed(42)


def reset_dataset(db):
    """Wipe every table before reseeding, so 'Generate sample data' always
    produces exactly one clean dataset instead of appending on top of
    whatever was already there. Deletes in FK-safe order (children first)."""
    db.query(AuditLogEntry).delete()
    db.query(ExceptionRecord).delete()
    db.query(ReconciliationRun).delete()
    db.query(LedgerEntry).delete()
    db.query(BankStatementLine).delete()
    db.query(SettlementItem).delete()
    db.query(SettlementBatch).delete()
    db.query(Transaction).delete()
    db.commit()


def _fee_tax(amount: float):
    fee = round(amount * RAZORPAY_FEE_RATE, 2)
    tax = round(fee * GST_ON_FEE_RATE, 2)
    return fee, tax


def generate_sample_dataset(db, n_transactions: int = 120):
    base_date = dt.datetime.utcnow() - dt.timedelta(days=10)
    transactions = []

    for i in range(n_transactions):
        created = base_date + dt.timedelta(
            hours=random.randint(0, 24 * 7), minutes=random.randint(0, 59)
        )
        amount = round(random.uniform(200, 15000), 2)
        fee, tax = _fee_tax(amount)
        txn = Transaction(
            customer_id=f"cust_{random.randint(1000, 1999)}",
            amount=amount,
            fee=fee,
            tax=tax,
            status="captured",
            created_at=created,
        )
        db.add(txn)
        transactions.append(txn)
    db.flush()

    # --- Inject a failed-then-retried transaction (L3 residue) ---
    retry_source = transactions[5]
    failed_dup = Transaction(
        customer_id=retry_source.customer_id,
        amount=retry_source.amount,
        fee=0.0,
        tax=0.0,
        status="failed",
        created_at=retry_source.created_at - dt.timedelta(minutes=3),
    )
    db.add(failed_dup)
    db.flush()

    # Group captured transactions into daily settlement batches, T+2 lag
    by_day = {}
    for txn in transactions:
        day = txn.created_at.date()
        by_day.setdefault(day, []).append(txn)

    l1_short_ids = random.sample(range(len(transactions)), 4)
    l1_double_fee_ids = set(l1_short_ids[:2])   # clean double-fee-deduction pattern
    l1_random_noise_ids = set(l1_short_ids[2:])  # unexplained shortfall
    txn_index_lookup = {t.id: idx for idx, t in enumerate(transactions)}

    batches = []
    for day, txns_today in sorted(by_day.items()):
        settlement_date = dt.datetime.combine(day, dt.time()) + dt.timedelta(days=2)
        items = []
        batch_total = 0.0
        for txn in txns_today:
            idx = txn_index_lookup[txn.id]
            net = txn.net_amount
            if idx in l1_double_fee_ids:
                # Fee deducted twice on the gateway side -> a clean, recognizable pattern
                net = round(net - txn.fee, 2)
            elif idx in l1_random_noise_ids:
                # Unexplained shortfall -> no clean pattern, needs a human
                net = round(net - random.uniform(5, 25), 2)
            item = SettlementItem(transaction_id=txn.id, net_amount=net)
            items.append(item)
            batch_total += net

        batch = SettlementBatch(
            settlement_date=settlement_date,
            batch_amount=round(batch_total, 2),
        )
        db.add(batch)
        db.flush()
        for item in items:
            item.batch_id = batch.id
            db.add(item)
        batches.append(batch)
    db.flush()

    # --- Bank statement lines: normally one credit per batch UTR ---
    for batch in batches:
        if batch is batches[2] if len(batches) > 2 else False:
            # Split settlement: bank credits the batch in two tranches
            half = round(batch.batch_amount / 2, 2)
            db.add(BankStatementLine(
                value_date=batch.settlement_date, amount=half,
                utr_reference=batch.id, narrative="RAZORPAY SETTLEMENT (1/2)",
            ))
            db.add(BankStatementLine(
                value_date=batch.settlement_date + dt.timedelta(hours=6),
                amount=round(batch.batch_amount - half, 2),
                utr_reference=batch.id, narrative="RAZORPAY SETTLEMENT (2/2)",
            ))
        elif batch is batches[4] if len(batches) > 4 else False:
            # Bank deducts a known wire-processing charge slab (recognizable pattern)
            shortfall = 25.0
            db.add(BankStatementLine(
                value_date=batch.settlement_date,
                amount=round(batch.batch_amount - shortfall, 2),
                utr_reference=batch.id, narrative="RAZORPAY SETTLEMENT (bank chg)",
            ))
        elif batch is batches[5] if len(batches) > 5 else False:
            # An unexplained, non-slab shortfall -> genuinely needs a human
            shortfall = round(random.uniform(10, 45), 2)
            db.add(BankStatementLine(
                value_date=batch.settlement_date,
                amount=round(batch.batch_amount - shortfall, 2),
                utr_reference=batch.id, narrative="RAZORPAY SETTLEMENT (unknown deduction)",
            ))
        else:
            db.add(BankStatementLine(
                value_date=batch.settlement_date, amount=batch.batch_amount,
                utr_reference=batch.id, narrative="RAZORPAY SETTLEMENT",
            ))

    # --- Ledger entries: revenue recognized at capture time ---
    for txn in transactions:
        db.add(LedgerEntry(
            transaction_id=txn.id, entry_type="revenue",
            amount=txn.net_amount, recognized_date=txn.created_at,
        ))

    # --- A refund recognized in the ledger with a timing lag beyond the
    #     matching window (genuine L3 exception, not just noise) ---
    refund_txn = transactions[30]
    db.add(LedgerEntry(
        transaction_id=refund_txn.id, entry_type="refund",
        amount=-refund_txn.amount,
        recognized_date=refund_txn.created_at + dt.timedelta(days=9),
    ))

    db.commit()
    return {
        "transactions": len(transactions) + 1,
        "settlement_batches": len(batches),
        "ledger_entries": len(transactions) + 1,
    }
