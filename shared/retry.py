import time
import random
import requests

RETRIABLE_5XX = {500, 502, 503, 504}
RETRIABLE_429 = {429}
RETRIABLE_403 = {403}

MAX_RETRIES_403 = 2          # keep small: if it's WAF/auth, retries won't help
MAX_RETRIES_OTHER = 6

MAX_SLEEP_SECONDS = 120


def _sleep(seconds: float) -> None:
    time.sleep(max(0.0, seconds))


def _retry_after_seconds(resp: requests.Response) -> float | None:
    ra = resp.headers.get("Retry-After")
    if not ra:
        return None
    try:
        return float(ra)
    except Exception:
        return None


def request_with_backoff(
    method: str,
    url: str,
    *,
    headers=None,
    params=None,
    json=None,
    data=None,
    timeout=25,
    session=None,
) -> requests.Response:
    """
    Smart backoff:
    - 403: retry a couple times, then RETURN resp (do not raise)
    - 429: exponential backoff + Retry-After
    - 5xx: exponential backoff
    - others: return resp (caller decides)
    """
    http = session if session is not None else requests

    attempt = 0
    last_exc: Exception | None = None

    while True:
        try:
            resp = http.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                timeout=timeout,
            )

            # 403: small jitter retries, then return (caller handles)
            if resp.status_code in RETRIABLE_403:
                if attempt >= MAX_RETRIES_403:
                    return resp
                _sleep(1.5 + random.uniform(0, 0.8))
                attempt += 1
                continue

            # 429: rate limiting
            if resp.status_code in RETRIABLE_429:
                if attempt >= MAX_RETRIES_OTHER:
                    return resp
                ra = _retry_after_seconds(resp)
                sleep_s = min(MAX_SLEEP_SECONDS, ra if ra is not None else (2 ** attempt))
                _sleep(sleep_s + random.uniform(0, 1))
                attempt += 1
                continue

            # 5xx: server errors
            if resp.status_code in RETRIABLE_5XX:
                if attempt >= MAX_RETRIES_OTHER:
                    return resp
                sleep_s = min(MAX_SLEEP_SECONDS, (2 ** attempt)) + random.uniform(0, 0.5)
                _sleep(sleep_s)
                attempt += 1
                continue

            # Anything else: return resp (caller can raise or parse)
            return resp

        except Exception as e:
            last_exc = e
            if attempt >= MAX_RETRIES_OTHER:
                break
            sleep_s = min(MAX_SLEEP_SECONDS, (2 ** attempt)) + random.uniform(0, 0.5)
            _sleep(sleep_s)
            attempt += 1

    raise RuntimeError(f"HTTP request failed after retries. url={url}. error={last_exc}")
