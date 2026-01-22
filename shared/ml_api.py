import os
import requests

from .retry import request_with_backoff

BACKEND_BASE = os.getenv(
    "SMARTLOANS_BACKEND_URL",
    "https://smartloansbackend.azurewebsites.net"
).rstrip("/")

TIMEOUT = int(os.getenv("ML_TIMEOUT_SECONDS", "25"))

# Browser-like headers to avoid 403 from proxy/WAF
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Connection": "keep-alive",
}

# Create a session for cookie persistence
_session = requests.Session()
_session.headers.update(DEFAULT_HEADERS)


def _get_headers() -> dict:
    """Get headers with optional ML access token."""
    headers = dict(DEFAULT_HEADERS)
    token = os.getenv("ML_ACCESS_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ml_search(q: str, *, category: str | None, seller_id: str | None, offset: int, limit: int):
    # ML API: https://api.mercadolibre.com/sites/{site_id}/search
    site_id = os.getenv("ML_SITE_ID", "MLM")
    url = f"{BACKEND_BASE}/sites/{site_id}/search"

    params = {"q": q, "offset": offset, "limit": limit}
    if category:
        params["category"] = category
    if seller_id:
        params["seller_id"] = seller_id

    resp = request_with_backoff("GET", url, params=params, timeout=TIMEOUT, headers=_get_headers(), session=_session)
    return resp.json()


def ml_item(item_id: str):
    # ML API: https://api.mercadolibre.com/items/{item_id}
    url = f"{BACKEND_BASE}/items/{item_id}"
    resp = request_with_backoff("GET", url, timeout=TIMEOUT, headers=_get_headers(), session=_session)
    return resp.json()
