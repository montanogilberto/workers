import os
import logging
import uuid
import requests

from .retry import request_with_backoff

logger = logging.getLogger(__name__)

BACKEND_BASE = os.getenv("SMARTLOANS_BACKEND_URL", "https://smartloansbackend.azurewebsites.net").rstrip("/")
TIMEOUT = int(os.getenv("ML_TIMEOUT_SECONDS", "25"))

WORKER_KEY = os.getenv("WORKER_KEY", "")

if WORKER_KEY:
    masked_key = WORKER_KEY[:8] + "..." + WORKER_KEY[-4:] if len(WORKER_KEY) > 12 else "***"
    logger.info(f"[ML_API] WORKER_KEY loaded: {masked_key}")
else:
    logger.warning("[ML_API] WORKER_KEY not found in environment variables!")


def _mask(value: str, keep: int = 8) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "***"
    return value[:keep] + "..." + value[-4:]


def _build_headers(request_id: str | None = None) -> dict:
    """
    Build headers for backend proxy calls.
    - X-Worker-Key required by backend auth dependency
    - x-request-id helps correlate logs across worker/backend
    """
    rid = request_id or str(uuid.uuid4())

    headers = {
        "Accept": "application/json",
        "x-request-id": rid,
    }

    if WORKER_KEY:
        headers["X-Worker-Key"] = WORKER_KEY
    else:
        logger.warning(f"[ML_API][{rid}] WORKER_KEY missing -> backend likely returns 401/403")

    return headers


def _safe_json(resp: requests.Response) -> dict:
    """
    Always return JSON-like dict, even if backend responds with HTML/text.
    """
    try:
        return resp.json()
    except Exception:
        text = (resp.text or "")
        return {
            "error": "non_json_response",
            "http_status": resp.status_code,
            "body_preview": text[:1200],
            "headers_preview": {
                "content-type": resp.headers.get("content-type"),
                "x-request-id": resp.headers.get("x-request-id"),
            },
        }


# keep one session for pooling; do NOT pre-set dynamic headers here
_session = requests.Session()


def ml_search(
    q: str,
    *,
    category: str | None,
    seller_id: str | None,
    offset: int,
    limit: int,
    request_id: str | None = None,
):
    """
    Search MercadoLibre listings via backend proxy: GET /ml/search
    """
    url = f"{BACKEND_BASE}/ml/search"

    params = {"q": q, "offset": offset, "limit": limit}
    if category:
        params["category"] = category
    if seller_id:
        params["seller_id"] = seller_id

    headers = _build_headers(request_id=request_id)
    rid = headers.get("x-request-id")

    logger.info(f"[ML_API][{rid}] GET {url} params={params} worker_key={_mask(headers.get('X-Worker-Key',''))}")

    resp = request_with_backoff(
        "GET",
        url,
        params=params,
        timeout=TIMEOUT,
        headers=headers,
        session=_session,
    )

    logger.info(f"[ML_API][{rid}] status={resp.status_code}")

    if resp.status_code == 403:
        return {
            "error": "backend_forbidden",
            "http_status": 403,
            "body": _safe_json(resp),
            "request_id": rid,
        }

    return _safe_json(resp)


def ml_product_items(
    product_id: str,
    *,
    offset: int = 0,
    limit: int = 50,
    request_id: str | None = None,
):
    """
    Get ML items for a Product Unify ID via backend proxy.
    Backend route:
      GET /ml/products/{product_id}/items
    """
    url = f"{BACKEND_BASE}/ml/products/{product_id}/items"
    params = {"offset": offset, "limit": limit}

    headers = _build_headers(request_id=request_id)
    rid = headers.get("x-request-id")

    logger.info(
        f"[ML_API][{rid}] GET {url} params={params} product_id={product_id} worker_key={_mask(headers.get('X-Worker-Key',''))}"
    )

    resp = request_with_backoff(
        "GET",
        url,
        params=params,
        timeout=TIMEOUT,
        headers=headers,
        session=_session,
    )

    logger.info(f"[ML_API][{rid}] status={resp.status_code}")

    if resp.status_code == 403:
        return {
            "error": "backend_forbidden",
            "http_status": 403,
            "body": _safe_json(resp),
            "request_id": rid,
        }

    return _safe_json(resp)


def ml_item(item_id: str, request_id: str | None = None):
    """
    Get item details via backend proxy: GET /ml/items/{item_id}
    """
    url = f"{BACKEND_BASE}/ml/items/{item_id}"

    headers = _build_headers(request_id=request_id)
    rid = headers.get("x-request-id")

    logger.info(f"[ML_API][{rid}] GET {url} worker_key={_mask(headers.get('X-Worker-Key',''))}")

    resp = request_with_backoff(
        "GET",
        url,
        timeout=TIMEOUT,
        headers=headers,
        session=_session,
    )

    logger.info(f"[ML_API][{rid}] status={resp.status_code}")

    if resp.status_code == 403:
        return {
            "error": "backend_forbidden",
            "http_status": 403,
            "body": _safe_json(resp),
            "request_id": rid,
        }

    return _safe_json(resp)


def ml_seller_items(seller_id: str, *, offset: int, limit: int, order: str | None = None, request_id: str | None = None):
    url = f"{BACKEND_BASE}/ml/seller_items"
    params = {"seller_id": seller_id, "offset": offset, "limit": limit}
    if order:
        params["order"] = order

    headers = _build_headers(request_id=request_id)
    rid = headers.get("x-request-id")

    logger.info(f"[ML_API][{rid}] GET {url} params={params} worker_key={_mask(headers.get('X-Worker-Key',''))}")

    resp = request_with_backoff(
        "GET",
        url,
        params=params,
        timeout=TIMEOUT,
        headers=headers,
        session=_session,
    )

    return _safe_json(resp)
