import os
import requests

from .retry import request_with_backoff

BACKEND_BASE = os.getenv(
    "SMARTLOANS_BACKEND_URL",
    "https://smartloansbackend.azurewebsites.net"
).rstrip("/")

TIMEOUT = int(os.getenv("ML_TIMEOUT_SECONDS", "25"))

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Connection": "keep-alive",
}

_session = requests.Session()
_session.headers.update(DEFAULT_HEADERS)

def _get_headers() -> dict:
    """
    Worker -> Backend proxy.
    Backend is responsible for adding ML Authorization (dynamic tokens).
    """
    headers = dict(DEFAULT_HEADERS)

    # Optional: protect your backend endpoints so random people can’t use your proxy.
    worker_key = os.getenv("WORKER_KEY", "").strip()
    if worker_key:
        headers["X-Worker-Key"] = worker_key

    return headers


def ml_search(q: str, *, category: str | None, seller_id: str | None, offset: int, limit: int):
    site_id = os.getenv("ML_SITE_ID", "MLM")

    # IMPORTANT: call your backend ML proxy route (recommended)
    #url = f"{BACKEND_BASE}/ml/sites/{site_id}/search"
    url = f"{BACKEND_BASE}/ml/search"

    params = {"q": q, "offset": offset, "limit": limit}
    if category:
        params["category"] = category
    if seller_id:
        params["seller_id"] = seller_id

    resp = request_with_backoff(
        "GET",
        url,
        params=params,
        timeout=TIMEOUT,
        headers=_get_headers(),
        session=_session
    )
    return resp.json()


def ml_item(item_id: str):
    url = f"{BACKEND_BASE}/ml/items/{item_id}"

    resp = request_with_backoff(
        "GET",
        url,
        timeout=TIMEOUT,
        headers=_get_headers(),
        session=_session
    )
    return resp.json()
