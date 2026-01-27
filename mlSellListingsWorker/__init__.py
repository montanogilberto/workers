import os
import azure.functions as func
import logging
from datetime import datetime, timezone

from shared.ml_api import ml_search, ml_item
from shared.selllistings_mapper import map_ml_item_to_selllisting
from shared.db import exec_sp_json

logger = logging.getLogger(__name__)


def parse_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "") or ""
    return [p.strip() for p in raw.split(",") if p.strip()]


def chunk(lst, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _sp_first_row(sp_resp):
    """
    exec_sp_json() in your project may return:
      - dict: {"result":[{...}]}
      - list: [{...}]
      - None
    This helper returns the first row dict (or {}).
    """
    if sp_resp is None:
        return {}
    if isinstance(sp_resp, dict):
        rows = sp_resp.get("result") or []
        return rows[0] if rows else {}
    if isinstance(sp_resp, list):
        return sp_resp[0] if sp_resp else {}
    return {}


def process_ml_listings():
    site_market = os.getenv("ML_MARKET", "MX")
    limit = int(os.getenv("ML_LIMIT", "50"))
    max_pages = int(os.getenv("ML_MAX_PAGES", "10"))
    call_details = os.getenv("ML_CALL_ITEMS_DETAIL", "1") == "1"

    keywords = parse_csv_env("ML_KEYWORDS")
    categories = parse_csv_env("ML_CATEGORIES")
    seller_ids = parse_csv_env("ML_SELLER_IDS")

    if not keywords and not categories and not seller_ids:
        logger.info("ML Worker: No inputs (ML_KEYWORDS / ML_CATEGORIES / ML_SELLER_IDS). Nothing to do.")
        return {"success": True, "items_fetched": 0, "items_inserted": 0}

    logger.info("ML Worker: Started")
    logger.info("Config => market=%s limit=%s max_pages=%s call_details=%s", site_market, limit, max_pages, call_details)

    search_jobs = []

    for q in keywords:
        search_jobs.append({"q": q, "category": None, "seller_id": None})

    for c in categories:
        search_jobs.append({"q": "*", "category": c, "seller_id": None})

    for sid in seller_ids:
        search_jobs.append({"q": "*", "category": None, "seller_id": sid})

    inserted = 0
    total_items = 0

    for job in search_jobs:
        q = job["q"]
        category = job["category"]
        seller_id = job["seller_id"]

        logger.info("Search job => q=%s category=%s seller_id=%s", q, category, seller_id)

        offset = 0
        page = 0

        while page < max_pages:
            data = ml_search(q, category=category, seller_id=seller_id, offset=offset, limit=limit)
            results = data.get("results", []) or []
            paging = data.get("paging", {}) or {}
            total = int(paging.get("total", 0) or 0)

            if not results:
                logger.info("  No results at offset=%s. Stop job.", offset)
                break

            item_ids = [r.get("id") for r in results if r.get("id")]
            total_items += len(item_ids)

            # Detail calls
            if call_details:
                items_detail = []
                for batch in chunk(item_ids, 20):
                    for item_id in batch:
                        try:
                            items_detail.append(ml_item(item_id))
                        except Exception as e:
                            logger.error("  Item detail failed id=%s: %s", item_id, e)
            else:
                items_detail = results

            # Map to sellListings payload
            sell_listings_payload = []
            for it in items_detail:
                try:
                    mapped = map_ml_item_to_selllisting(it, market=site_market)
                    sell_listings_payload.append({**mapped, "action": "1"})
                except Exception as e:
                    logger.error("  Map failed: %s", e)

            if sell_listings_payload:
                payload = {"sellListings": sell_listings_payload}
                sp_out = exec_sp_json("sp_sellListings", payload)
                inserted += len(sell_listings_payload)

                row0 = _sp_first_row(sp_out)
                logger.info(
                    "  Inserted batch: %s | SP value=%s msg=%s error=%s",
                    len(sell_listings_payload),
                    row0.get("value"),
                    row0.get("msg"),
                    row0.get("error"),
                )

            offset += limit
            page += 1

            if total and offset >= total:
                break

    logger.info("ML Worker: Done. total_items=%s inserted_rows=%s", total_items, inserted)
    return {"success": True, "items_fetched": total_items, "items_inserted": inserted}


def run_ml_sell_listings_worker(mytimer: func.TimerRequest) -> None:
    # ✅ FIX: TimerRequest has no .timestamp
    now_utc = datetime.now(timezone.utc).isoformat()
    logger.info("ML Worker: Timer fired at %s | past_due=%s", now_utc, getattr(mytimer, "past_due", False))

    if mytimer.past_due:
        logger.warning("ML Worker: The timer is past due!")

    try:
        result = process_ml_listings()
        logger.info(
            "ML Worker: Result = success=%s items_fetched=%s items_inserted=%s",
            result.get("success"),
            result.get("items_fetched"),
            result.get("items_inserted"),
        )
    except Exception as e:
        logger.error("ML Worker: Failed with error: %s", str(e), exc_info=True)
        raise


def main():
    result = process_ml_listings()
    print(f"ML listings worker completed: {result}")
