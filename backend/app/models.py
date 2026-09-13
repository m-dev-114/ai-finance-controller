import uuid
import datetime as dt

from sqlalchemy import (
    Column, String, Float, DateTime, Boolean, Integer, ForeignKey, Text, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Transaction(Base):
    """A single payment captured by the gateway (Razorpay-side)."""
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: gen_id("txn"))
    customer_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)          # gross amount charged to customer
    fee = Column(Float, nullable=False, default=0.0)  # gateway fee
    tax = Column(Float, nullable=False, default=0.0)  # tax on fee (e.g. GST on fee)
    currency = Column(String, default="INR")
    status = Column(String, default="captured")      # captured | refunded | failed
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    settlement_item_id = Column(String, ForeignKey("settlement_items.id"), nullable=True)

    @property
    def net_amount(self) -> float:
        return round(self.amount - self.fee - self.tax, 2)


class SettlementBatch(Base):
    """A single settlement UTR from the gateway, bundling many transactions."""
    __tablename__ = "settlement_batches"

    id = Column(String, primary_key=True, default=lambda: gen_id("utr"))
    settlement_date = Column(DateTime, nullable=False)
    batch_amount = Column(Float, nullable=False)  # total the gateway says it settled
    currency = Column(String, default="INR")
    items = relationship("SettlementItem", back_populates="batch")


class SettlementItem(Base):
    """One transaction's line within a settlement batch (net of fees)."""
    __tablename__ = "settlement_items"

    id = Column(String, primary_key=True, default=lambda: gen_id("si"))
    batch_id = Column(String, ForeignKey("settlement_batches.id"))
    transaction_id = Column(String, nullable=True)  # denormalized ref, matched or not
    net_amount = Column(Float, nullable=False)
    batch = relationship("SettlementBatch", back_populates="items")


class BankStatementLine(Base):
    """A line from the actual bank statement (ground truth of cash movement)."""
    __tablename__ = "bank_statement_lines"

    id = Column(String, primary_key=True, default=lambda: gen_id("bank"))
    value_date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    utr_reference = Column(String, nullable=True)  # bank often echoes the UTR
    narrative = Column(Text, nullable=True)
    matched_batch_id = Column(String, nullable=True)


class LedgerEntry(Base):
    """Internal books: revenue recognized, refunds/chargebacks issued."""
    __tablename__ = "ledger_entries"

    id = Column(String, primary_key=True, default=lambda: gen_id("led"))
    transaction_id = Column(String, nullable=True)
    entry_type = Column(String, default="revenue")  # revenue | refund | chargeback
    amount = Column(Float, nullable=False)
    recognized_date = Column(DateTime, nullable=False)
    matched_settlement_item_id = Column(String, nullable=True)


class ReconciliationRun(Base):
    """One execution of the reconciliation job. Immutable, replay-safe."""
    __tablename__ = "reconciliation_runs"

    id = Column(String, primary_key=True, default=lambda: gen_id("run"))
    started_at = Column(DateTime, default=dt.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # running | completed | failed
    stats = Column(JSON, default=dict)  # counts: matched_l1/l2/l3, exceptions, auto_cleared


class ExceptionRecord(Base):
    """A discrepancy left over after deterministic matching."""
    __tablename__ = "exceptions"

    id = Column(String, primary_key=True, default=lambda: gen_id("exc"))
    run_id = Column(String, ForeignKey("reconciliation_runs.id"))
    level = Column(String, nullable=False)  # transaction | batch | ledger
    reference_ids = Column(JSON, default=list)  # ids of the records involved
    status = Column(String, default="open")  # open | auto_cleared | needs_review | resolved
    confidence = Column(Float, nullable=True)
    hypothesis = Column(Text, nullable=True)
    reasoning_trail = Column(JSON, default=list)  # ordered list of investigation steps
    amount_delta = Column(Float, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)  # "agent" | "human:<name>"


class AppSetting(Base):
    """Single-row-per-key runtime config, editable via the API/UI instead
    of requiring a redeploy to change (e.g. the auto-clear confidence
    threshold)."""
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class AuditLogEntry(Base):
    """Immutable audit trail. Every automated or human decision is logged here."""
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=lambda: gen_id("audit"))
    exception_id = Column(String, ForeignKey("exceptions.id"), nullable=True)
    run_id = Column(String, nullable=True)
    actor = Column(String, nullable=False)  # "system" | "agent" | "human:<name>"
    action = Column(String, nullable=False)  # e.g. "auto_cleared", "flagged", "resolved"
    detail = Column(Text, nullable=True)
    data_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
