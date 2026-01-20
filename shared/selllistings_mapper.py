from shared.fx import get_fx_rate_to_usd
import datetime as dt

def safe_get(d: dict, path: list, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

def map_ml_item_to_selllisting(item: dict, market: str):
    sell_price_original = float(item.get("price") or 0)
    currency = (item.get("currency_id") or "MXN").upper()

    fx_rate, fx_date = get_fx_rate_to_usd(currency)
    sell_price_usd = round(sell_price_original * fx_rate, 6)

    return {
        "channel": "mercadolibre",
        "market": market,
        "channelItemId": str(item.get("id")),
        "title": item.get("title"),
        "sellPriceOriginal": sell_price_original,
        "currencyOriginal": currency,
        "sellPriceUsd": sell_price_usd,
        "fxRateToUsd": fx_rate,
        "fxAsOfDate": fx_date,
        "fulfillmentType": (item.get("shipping") or {}).get("mode"),
        "shippingTimeDays": None,
        "rating": None,
        "reviewsCount": None,
        "listingTimestamp": dt.datetime.utcnow().isoformat(),
        "unifiedProductId": None,
        "action": "1",
    }
