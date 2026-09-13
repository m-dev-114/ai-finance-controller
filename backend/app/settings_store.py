from sqlalchemy.orm import Session
from .models import AppSetting
from .config import AUTO_CLEAR_CONFIDENCE as DEFAULT_AUTO_CLEAR_CONFIDENCE

AUTO_CLEAR_KEY = "auto_clear_confidence"


def get_auto_clear_confidence(db: Session) -> float:
    row = db.query(AppSetting).get(AUTO_CLEAR_KEY)
    if row is None:
        return DEFAULT_AUTO_CLEAR_CONFIDENCE
    try:
        return float(row.value)
    except (TypeError, ValueError):
        return DEFAULT_AUTO_CLEAR_CONFIDENCE


def set_auto_clear_confidence(db: Session, value: float) -> float:
    value = max(0.5, min(0.99, value))
    row = db.query(AppSetting).get(AUTO_CLEAR_KEY)
    if row is None:
        row = AppSetting(key=AUTO_CLEAR_KEY, value=str(value))
        db.add(row)
    else:
        row.value = str(value)
    db.commit()
    return value


REALISTIC_CONFIDENCE_CEILING = 0.92  # see agent.py — no single check currently
                                       # scores above this, so a threshold set
                                       # higher than this will never auto-clear
                                       # anything at all.
