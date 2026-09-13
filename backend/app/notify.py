import requests
from .config import SLACK_WEBHOOK_URL, NOTIFY_MIN_NEEDS_REVIEW


def notify_run_complete(run_id: str, stats: dict, top_exceptions: list):
    """Best-effort Slack notification. Silently does nothing if no webhook
    is configured, and never raises — a failed notification must not fail
    the reconciliation run itself."""
    if not SLACK_WEBHOOK_URL:
        return
    needs_review = stats.get("needs_review", 0)
    if needs_review < NOTIFY_MIN_NEEDS_REVIEW:
        return

    lines = [
        f"*Reconciliation run `{run_id}` completed*",
        f"{stats.get('auto_cleared', 0)} auto-cleared, "
        f"{needs_review} need review, "
        f"{stats.get('already_tracked', 0)} already tracked from prior runs.",
    ]
    if top_exceptions:
        lines.append("Largest open discrepancies:")
        for exc in top_exceptions[:5]:
            lines.append(
                f"  \u2022 {exc['level']} \u2014 \u20b9{abs(exc['amount_delta'] or 0):,.2f} "
                f"({int((exc['confidence'] or 0) * 100)}% confidence) \u2014 {exc['hypothesis']}"
            )

    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": "\n".join(lines)}, timeout=5)
    except Exception:
        pass  # notification failures should never break the reconciliation run
