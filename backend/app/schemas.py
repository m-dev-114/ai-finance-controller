import datetime as dt
from typing import List, Optional, Any
from pydantic import BaseModel


class RunSummary(BaseModel):
    id: str
    started_at: dt.datetime
    finished_at: Optional[dt.datetime]
    status: str
    stats: dict

    class Config:
        from_attributes = True


class ExceptionOut(BaseModel):
    id: str
    run_id: str
    level: str
    reference_ids: List[str]
    status: str
    confidence: Optional[float]
    hypothesis: Optional[str]
    reasoning_trail: List[Any]
    amount_delta: Optional[float]
    created_at: dt.datetime
    resolved_at: Optional[dt.datetime]
    resolved_by: Optional[str]

    class Config:
        from_attributes = True


class ResolveExceptionRequest(BaseModel):
    resolved_by: str  # e.g. "human:priya"
    note: Optional[str] = None
    outcome: str = "resolved"  # resolved | dismissed


class BulkResolveRequest(BaseModel):
    exception_ids: List[str]
    resolved_by: str
    note: Optional[str] = None
    outcome: str = "resolved"  # resolved | dismissed


class BulkResolveResult(BaseModel):
    updated: List[str]
    skipped: List[str]


class AuditLogOut(BaseModel):
    id: str
    exception_id: Optional[str]
    run_id: Optional[str]
    actor: str
    action: str
    detail: Optional[str]
    data_snapshot: dict
    created_at: dt.datetime

    class Config:
        from_attributes = True


class MetricsOut(BaseModel):
    total_runs: int
    latest_run: Optional[RunSummary]
    auto_clear_rate: float
    avg_resolution_minutes: Optional[float]
    exceptions_by_status: dict
    match_rate_by_level: dict
    total_transactions_in_dataset: int = 0


class ThresholdOut(BaseModel):
    auto_clear_confidence: float


class ThresholdUpdate(BaseModel):
    auto_clear_confidence: float


class ThresholdSimulation(BaseModel):
    threshold: float
    would_auto_clear: int
    would_need_review: int
    current_auto_clear_confidence: float


class ReevaluateResult(BaseModel):
    threshold: float
    promoted: List[str]
    remaining_needs_review: int


class TrendPoint(BaseModel):
    run_id: str
    started_at: dt.datetime
    match_rate: float
    total_exceptions: int
    auto_cleared: int
    needs_review: int


class TrendOut(BaseModel):
    points: List[TrendPoint]
