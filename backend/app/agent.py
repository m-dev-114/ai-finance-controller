"""
Investigation agent — invoked ONLY on exceptions the deterministic matching
engine could not resolve (see matching.py). Cheap rule-based checks run
first and build a reasoning trail; an LLM is used only to phrase the final
explanation in plain English, and only if a provider key is configured.
With no key, a deterministic template produces the same structured output,
so the whole pipeline runs end-to-end with zero external dependencies.

Built as a LangGraph StateGraph so each investigative step is a discrete,
inspectable node — the reasoning_trail returned to the API is literally the
node-by-node path the agent took, not a black-box verdict.
"""
from typing import TypedDict, List, Dict, Any, Optional
import datetime as dt

from langgraph.graph import StateGraph, END

from .config import (
    AUTO_CLEAR_CONFIDENCE, LLM_PROVIDER, GROQ_API_KEY, OPENAI_API_KEY,
    SETTLEMENT_LAG_MAX_DAYS,
)


class InvestigationState(TypedDict):
    exception: Dict[str, Any]          # serialized ExceptionRecord
    context: Dict[str, Any]            # related records pulled from the DB
    checks: List[Dict[str, Any]]       # reasoning trail, appended to by each node
    hypothesis: Optional[str]
    confidence: float
    decision: Optional[str]            # "auto_clear" | "needs_review"
    threshold: float                   # auto-clear confidence threshold for this run


def _add_step(state: InvestigationState, step: str, finding: str, weight: float):
    state["checks"].append({"step": step, "finding": finding})
    return state


def gather_context(state: InvestigationState) -> InvestigationState:
    # Context is pre-populated by the caller (investigate_exception) since it
    # needs a DB session; this node just marks the trail explicitly so the
    # trail reads as a complete, ordered investigation from the start.
    _add_step(state, "gather_context",
              f"Pulled {len(state['context'])} related record(s) for exception "
              f"{state['exception']['id']} (level={state['exception']['level']}).", 0)
    return state


# Known recurring bank-side charge slabs (NEFT/RTGS/wire processing fees).
# A shortfall that matches one of these exactly is a well-understood, low-risk
# pattern worth auto-clearing; an arbitrary shortfall is not.
KNOWN_BANK_CHARGE_SLABS = [5.0, 11.8, 25.0, 40.0]


def check_fee_mismatch(state: InvestigationState) -> InvestigationState:
    exc = state["exception"]
    if exc["level"] != "transaction":
        return state
    delta = exc.get("amount_delta") or 0
    txn = state["context"].get("transaction", {})
    fee = txn.get("fee", 0) or 0
    if fee and abs(abs(delta) - fee) <= 0.5:
        # Shortfall matches this transaction's own fee almost exactly —
        # a well-understood pattern (fee deducted twice on the gateway side).
        state["confidence"] += 0.92
        _add_step(state, "check_fee_mismatch",
                  f"Settlement shortfall (₹{abs(delta):.2f}) matches this "
                  f"transaction's own gateway fee (₹{fee:.2f}) almost exactly "
                  f"— the fee was deducted twice on the gateway side. This is "
                  f"a known, recurring pattern safe to auto-clear.", 0.92)
    elif fee and abs(abs(delta) - fee) <= max(fee * 0.5, 2):
        state["confidence"] += 0.45
        _add_step(state, "check_fee_mismatch",
                  f"Settlement shortfall (₹{abs(delta):.2f}) is roughly in "
                  f"line with this transaction's gateway fee (₹{fee:.2f}), "
                  f"but not an exact match — worth a second look.", 0.45)
    elif abs(delta) > 0:
        state["confidence"] += 0.15
        _add_step(state, "check_fee_mismatch",
                  f"Settlement amount differs from expected net by ₹{delta:.2f}, "
                  f"which doesn't cleanly match a single fee deduction or any "
                  f"known pattern — recommend manual review.", 0.15)
    return state


def check_split_or_shortfall(state: InvestigationState) -> InvestigationState:
    exc = state["exception"]
    if exc["level"] != "batch":
        return state
    bank_lines = state["context"].get("bank_lines", [])
    delta = exc.get("amount_delta") or 0
    matched_slab = next(
        (s for s in KNOWN_BANK_CHARGE_SLABS if abs(abs(delta) - s) <= 0.05), None
    )
    if len(bank_lines) >= 2:
        state["confidence"] += 0.4
        _add_step(state, "check_split_or_shortfall",
                  f"Batch was credited across {len(bank_lines)} separate bank "
                  f"lines; residual delta of ₹{delta:.2f} suggests a rounding "
                  f"or partial-tranche mismatch rather than a missing payout.", 0.4)
    elif delta < 0 and matched_slab is not None:
        state["confidence"] += 0.92
        _add_step(state, "check_split_or_shortfall",
                  f"Shortfall of ₹{abs(delta):.2f} matches the known "
                  f"₹{matched_slab:.2f} bank wire-processing charge slab "
                  f"exactly — a known, recurring deduction safe to auto-clear.", 0.92)
    elif delta < 0:
        state["confidence"] += 0.5
        _add_step(state, "check_split_or_shortfall",
                  f"Single bank credit is short by ₹{abs(delta):.2f} versus the "
                  f"reported settlement total — doesn't match any known bank "
                  f"charge slab, so treat as an unexplained shortfall.", 0.5)
    return state


def check_timing_lag(state: InvestigationState) -> InvestigationState:
    exc = state["exception"]
    if exc["level"] != "ledger":
        return state
    entry = state["context"].get("ledger_entry", {})
    entry_type = entry.get("entry_type", "revenue")
    if entry_type in ("refund", "chargeback"):
        state["confidence"] += 0.35
        _add_step(state, "check_timing_lag",
                  f"This is a {entry_type} recognized in the ledger, but no "
                  f"offsetting settlement debit has arrived yet. Refund payouts "
                  f"commonly settle on a separate, slower cycle than the "
                  f"original capture.", 0.35)
    else:
        lag = exc.get("amount_delta") or 0  # days beyond the max lag window
        state["confidence"] += 0.3
        _add_step(state, "check_timing_lag",
                  f"Revenue was recognized {lag + SETTLEMENT_LAG_MAX_DAYS:.0f} "
                  f"day(s) before its settlement — {lag:.0f} day(s) outside the "
                  f"normal T+{SETTLEMENT_LAG_MAX_DAYS} settlement window.", 0.3)
        if not state["context"].get("has_settlement_item"):
            state["confidence"] += 0.15
            _add_step(state, "check_timing_lag",
                      "No settlement item is linked to this transaction at all "
                      "— it may not have settled yet, or settled under a "
                      "different reference.", 0.15)
    return state


def _deterministic_explanation(state: InvestigationState) -> str:
    findings = "; ".join(c["finding"] for c in state["checks"][1:])
    return findings or "No strong signal found; recommend manual review."


def _llm_explanation(state: InvestigationState) -> str:
    prompt = (
        "You are a finance-operations assistant. Given this investigation "
        "trail for a payment-reconciliation exception, write a single, "
        "concise (<=2 sentence) explanation a finance controller could act "
        "on immediately. Be concrete and reference the numbers given.\n\n"
        f"Exception: {state['exception']}\n"
        f"Investigation steps: {state['checks'][1:]}\n"
    )
    try:
        if LLM_PROVIDER == "groq":
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
            )
            return resp.choices[0].message.content.strip()
        elif LLM_PROVIDER == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
            )
            return resp.choices[0].message.content.strip()
    except Exception as e:
        return _deterministic_explanation(state) + f" (LLM phrasing unavailable: {e})"
    return _deterministic_explanation(state)


def explain(state: InvestigationState) -> InvestigationState:
    if LLM_PROVIDER == "none":
        hypothesis = _deterministic_explanation(state)
    else:
        hypothesis = _llm_explanation(state)
    state["hypothesis"] = hypothesis
    _add_step(state, "explain", f"Generated hypothesis via {LLM_PROVIDER} "
              f"{'LLM' if LLM_PROVIDER != 'none' else 'rule-based'} explainer.", 0)
    return state


def decide(state: InvestigationState) -> InvestigationState:
    state["confidence"] = min(round(state["confidence"], 2), 0.99)
    threshold = state.get("threshold") or AUTO_CLEAR_CONFIDENCE
    if state["confidence"] >= threshold:
        state["decision"] = "auto_clear"
    else:
        state["decision"] = "needs_review"
    _add_step(state, "decide",
              f"Confidence {state['confidence']:.2f} -> {state['decision']} "
              f"(threshold {threshold}).", 0)
    return state


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("gather_context", gather_context)
    graph.add_node("check_fee_mismatch", check_fee_mismatch)
    graph.add_node("check_split_or_shortfall", check_split_or_shortfall)
    graph.add_node("check_timing_lag", check_timing_lag)
    graph.add_node("explain", explain)
    graph.add_node("decide", decide)

    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "check_fee_mismatch")
    graph.add_edge("check_fee_mismatch", "check_split_or_shortfall")
    graph.add_edge("check_split_or_shortfall", "check_timing_lag")
    graph.add_edge("check_timing_lag", "explain")
    graph.add_edge("explain", "decide")
    graph.add_edge("decide", END)
    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def investigate_exception(exception_dict: Dict[str, Any], context: Dict[str, Any],
                           threshold: float = None) -> Dict[str, Any]:
    """Run the LangGraph investigation for a single exception and return the
    final state (hypothesis, confidence, decision, reasoning_trail)."""
    initial: InvestigationState = {
        "exception": exception_dict,
        "context": context,
        "checks": [],
        "hypothesis": None,
        "confidence": 0.0,
        "decision": None,
        "threshold": threshold if threshold is not None else AUTO_CLEAR_CONFIDENCE,
    }
    final_state = get_graph().invoke(initial)
    return final_state
