import time
import random
import requests

# 5xx server errors - retry with exponential backoff
RETRIABLE_5XX = {500, 502, 503, 504}
# Rate limiting - retry with exponential backoff
RETRIABLE_429 = {429}
# 403 Forbidden - likely anti-bot/WAF, fail fast (few retries)
RETRIABLE_403 = {403}

# Max retries for 403 (anti-bot) - fail fast
MAX_RETRIES_403 = 2
# Max retries for 429/5xx - more retries allowed
MAX_RETRIES_OTHER = 6


def request_with_backoff(method: str, url: str, *, headers=None, params=None, timeout=25, max_retries=6, session=None):
    """
    Smart backoff with different handling per error type:
    - 403 (anti-bot/WAF): fail fast, few retries with jitter
    - 429 (rate limit): exponential backoff
    - 5xx (server errors): exponential backoff
    
    Args:
        session: Optional requests.Session for cookie persistence
    """
    attempt = 0
    last_exc = None
    http = session if session is not None else requests

    while attempt <= max_retries:
        try:
            resp = http.request(method, url, headers=headers, params=params, timeout=timeout)

            # 403: anti-bot protection - fail fast
            if resp.status_code in RETRIABLE_403:
                if attempt >= MAX_RETRIES_403:
                    # Raise immediately without catching
                    resp.raise_for_status()
                sleep_s = 2 + random.uniform(0, 1)  # Short delay between retries
                time.sleep(sleep_s)
                attempt += 1
                continue

            # 429: rate limiting - exponential backoff
            if resp.status_code in RETRIABLE_429:
                sleep_s = min(60, (2 ** attempt)) + random.uniform(0, 1)
                time.sleep(sleep_s)
                attempt += 1
                continue

            # 5xx: server errors - exponential backoff
            if resp.status_code in RETRIABLE_5XX:
                sleep_s = min(60, (2 ** attempt)) + random.uniform(0, 0.5)
                time.sleep(sleep_s)
                attempt += 1
                continue

            resp.raise_for_status()
            return resp

        except requests.exceptions.HTTPError as e:
            # Only catch HTTP errors that are not 403 (already handled above)
            # For 403 that made it here, re-raise immediately
            if e.response is not None and e.response.status_code in RETRIABLE_403:
                raise e
            last_exc = e
            sleep_s = min(60, (2 ** attempt)) + random.uniform(0, 0.5)
            time.sleep(sleep_s)
            attempt += 1

        except Exception as e:
            last_exc = e
            sleep_s = min(60, (2 ** attempt)) + random.uniform(0, 0.5)
            time.sleep(sleep_s)
            attempt += 1

    raise RuntimeError(f"HTTP request failed after retries. url={url}. error={last_exc}")
