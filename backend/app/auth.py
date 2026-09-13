from fastapi import Header, HTTPException
from typing import Optional
from .config import RECONCILE_API_KEY


def require_api_key(x_api_key: Optional[str] = Header(None)):
    """No-op if RECONCILE_API_KEY is unset (open local dev). If it's set,
    the header must match — this is what lets a scheduled cron job call
    /reconcile/run without the endpoint being open to the public internet."""
    if RECONCILE_API_KEY and x_api_key != RECONCILE_API_KEY:
        raise HTTPException(401, "Missing or invalid X-Api-Key header.")
