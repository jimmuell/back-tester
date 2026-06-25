from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class Trade:
    trade_id: int
    direction: Literal["long", "short"]
    entry_time: datetime   # tz-aware (US/Eastern)
    entry_price: float
    exit_time: datetime    # tz-aware
    exit_price: float
    qty: int
    pnl: float             # net P&L in USD (after commission)
