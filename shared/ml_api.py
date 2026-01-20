import os
from .retry import request_with_backoff

ML_SITE_ID = os.getenv("ML_SITE_ID", "MLM")
ML_TIMEOUT = int(os.getenv("ML_TIMEOUT_SECONDS", "25"))

def ml_search(q: str, *, category: str | None, seller_id: str | None, offset: int, limit: int):
    url = f"https://api.mercadolibre.com/sites/{ML_SITE_ID}/search"
    params = {"q": q, "offset": offset, "limit": limit}
    if category:
        params["category"] = category
    if seller_id:
        params["seller_id"] = seller_id

    resp = request_with_backoff("GET", url, params=params, timeout=ML_TIMEOUT)
    return resp.json()

def ml_item(item_id: str):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    resp = request_with_backoff("GET", url, timeout=ML_TIMEOUT)
    return resp.json()
