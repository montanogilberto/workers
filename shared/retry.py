import time
import random
import requests

RETRIABLE_5XX = {500, 502, 503, 504}
RETRIABLE_429 = {429}
RETRIABLE_403 = {403}

MAX_RETRIES_403 = 2
MAX_RETRIES_OTHER = 6

MAX_SLEEP_SECONDS = 60


def _sleep(seconds: float) -> None:
    time.sleep(max(0.0, seconds))


def _retry_after_seconds(resp: requests.Response) -> float | None:
    """
    If server provides Retry-After, respect it.
    Retry-After can be seconds or HTTP date; we support seconds.
    """
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
):
    """
    Smart backoff with different handling per error type:
    - 403: fail fast (likely WAF/anti-bot)
    - 429: exponential backoff (honor Retry-After if present)
    - 5xx: exponential backoff
    Supports GET/POST/etc with params + json/data.
    """
    http = session if session is not None else requests

    attempt = 0
    last_exc = None

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

            # 403: fail fast with small jitter
            if resp.status_code in RETRIABLE_403:
                if attempt >= MAX_RETRIES_403:
                    resp.raise_for_status()
                _sleep(2.0 + random.uniform(0, 1))
                attempt += 1
                continue

            # 429: rate limiting
            if resp.status_code in RETRIABLE_429:
                ra = _retry_after_seconds(resp)
                if ra is not None:
                    sleep_s = min(MAX_SLEEP_SECONDS, ra) + random.uniform(0, 1)
                else:
                    sleep_s = min(MAX_SLEEP_SECONDS, (2 ** attempt)) + random.uniform(0, 1)
                if attempt >= MAX_RETRIES_OTHER:
                    resp.raise_for_status()
                _sleep(sleep_s)
                attempt += 1
                continue

            # 5xx: server errors
            if resp.status_code in RETRIABLE_5XX:
                if attempt >= MAX_RETRIES_OTHER:
                    resp.raise_for_status()
                sleep_s = min(MAX_SLEEP_SECONDS, (2 ** attempt)) + random.uniform(0, 0.5)
                _sleep(sleep_s)
                attempt += 1
                continue

            # success or non-retriable error
            resp.raise_for_status()
            return resp

        except requests.exceptions.HTTPError as e:
            # If it's 403 and it got here, re-raise immediately
            if e.response is not None and e.response.status_code in RETRIABLE_403:
                raise
            last_exc = e
            if attempt >= MAX_RETRIES_OTHER:
                break
            sleep_s = min(MAX_SLEEP_SECONDS, (2 ** attempt)) + random.uniform(0, 0.5)
            _sleep(sleep_s)
            attempt += 1

        except Exception as e:
            last_exc = e
            if attempt >= MAX_RETRIES_OTHER:
                break
            sleep_s = min(MAX_SLEEP_SECONDS, (2 ** attempt)) + random.uniform(0, 0.5)
            _sleep(sleep_s)
            attempt += 1

    raise RuntimeError(f"HTTP request failed after retries. url={url}. error={last_exc}")
