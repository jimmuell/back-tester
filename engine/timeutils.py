from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def to_et(naive: datetime) -> datetime:
    """Attach Eastern tz to a naive datetime."""
    return naive.replace(tzinfo=ET)
