from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional



def _get(d: Dict[str, Any], key: str, default=None):
    return d.get(key, default) if isinstance(d, dict) else default


def _stable_listing_ts(fx_as_of_date: str) -> str:
    # fx_as_of_date = "YYYY-MM-DD"
    dt = datetime.fromisoformat(fx_as_of_date).replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _safe_float(x) -> float:
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def map_ml_item_to_selllisting(
    it: Dict[str, Any],
    *,
    market: str = "MX",
    fx_rate_to_usd: float,
    fx_as_of_date: str,
    listing_timestamp: str | None = None,
) -> Dict[str, Any]:
    """
    Mapea ML item (completo o row de /products/{id}/items) a tu estructura de dbo.sellListings / sp_sellListings.

    Campos NOT NULL que tu DB/SP requieren:
      channel, market, channelItemId,
      sellPriceOriginal, currencyOriginal,
      sellPriceUsd, fxRateToUsd, fxAsOfDate,
      listingTimestamp
    """

    # Si es respuesta especial de tu ml_api (403 payload), no se debe mapear
    if isinstance(it, dict) and it.get("http_status") == 403:
        raise ValueError("Blocked payload (403). Cannot map.")

    # item_id puede venir como id (items) o item_id (products/*/items)
    item_id = _get(it, "id") or _get(it, "item_id")
    if not item_id:
        raise ValueError("Missing item id (id/item_id).")

    price = _safe_float(_get(it, "price"))
    currency = _get(it, "currency_id") or "MXN"
    title = _get(it, "title") or ""  # product_items muchas veces no trae title

    ts = listing_timestamp or _get(it, "date_created") or _iso_utc_now()

    fx = float(fx_rate_to_usd or 0.0)
    if fx <= 0:
        raise ValueError("fx_rate_to_usd must be > 0")

    sell_usd = price * fx

    mapped = {
        # NOT NULL
        "channel": "mercadolibre",
        "market": (market or "MX").upper(),
        "channelItemId": str(item_id),
        "title": title,
        "sellPriceOriginal": price,
        "currencyOriginal": currency,
        "sellPriceUsd": sell_usd,
        "fxRateToUsd": fx,
        "fxAsOfDate": fx_as_of_date,
        "listingTimestamp": _stable_listing_ts(fx_as_of_date),

        # opcionales (tu tabla permite NULL)
        "fulfillmentType": None,
        "shippingTimeDays": None,
        "rating": None,
        "reviewsCount": None,
        "unifiedProductId": None,
    }

    return mapped
