import time
import random
import requests

RETRIABLE_STATUS = {429, 500, 502, 503, 504}

def request_with_backoff(method: str, url: str, *, headers=None, params=None, timeout=25, max_retries=6):
    """
    Simple exponential backoff with jitter for 429/5xx.
    """
    attempt = 0
    last_exc = None

    while attempt <= max_retries:
        try:
            resp = requests.request(method, url, headers=headers, params=params, timeout=timeout)
            if resp.status_code in RETRIABLE_STATUS:
                # backoff
                sleep_s = min(60, (2 ** attempt)) + random.uniform(0, 0.5)
                time.sleep(sleep_s)
                attempt += 1
                continue

            resp.raise_for_status()
            return resp

        except Exception as e:
            last_exc = e
            sleep_s = min(60, (2 ** attempt)) + random.uniform(0, 0.5)
            time.sleep(sleep_s)
            attempt += 1

    raise RuntimeError(f"HTTP request failed after retries. url={url}. error={last_exc}")
