import datetime as dt
from typing import Tuple, Optional
from shared.db import query_one

_fx_cache = {}  # key -> {"rate": float, "date": "YYYY-MM-DD"}

def get_fx_rate_to_usd(currency: str, as_of_date: Optional[str] = None) -> Tuple[float, str]:
    currency = (currency or "USD").upper()

    today = dt.datetime.utcnow().date().isoformat()
    if currency == "USD":
        return 1.0, today

    key = f"{currency}:{as_of_date or 'today'}"
    if key in _fx_cache:
        v = _fx_cache[key]
        return v["rate"], v["date"]

    row = query_one("EXEC dbo.sp_exchangeRates_latestToUsd ?, ?", (currency, as_of_date))
    if not row:
        raise RuntimeError(f"No exchange rate found for currency={currency}")

    rate = float(row.get("rateToUsd"))
    used_date = str(row.get("asOfDate") or today)

    _fx_cache[key] = {"rate": rate, "date": used_date}
    return rate, used_date
