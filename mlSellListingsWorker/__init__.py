import os
import azure.functions as func
import logging
from datetime import datetime, timezone
import json

from shared.ml_api import ml_product_items, ml_item
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
    if sp_resp is None:
        return {}
    if isinstance(sp_resp, dict):
        rows = sp_resp.get("result") or []
        return rows[0] if rows else {}
    if isinstance(sp_resp, list):
        return sp_resp[0] if sp_resp else {}
    return {}


def _is_blocked_payload(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("http_status") == 403:
        return True
    if str(data.get("error", "")).lower() in ("backend_forbidden", "forbidden", "waf_blocked"):
        return True
    return False


def process_ml_listings():
    site_market = os.getenv("ML_MARKET", "MX")
    limit = int(os.getenv("ML_LIMIT", "50"))
    max_pages = int(os.getenv("ML_MAX_PAGES", "10"))

    # IMPORTANT: default OFF because ML blocks /items/{id}
    call_details = os.getenv("ML_CALL_ITEMS_DETAIL", "0") == "1"

    product_ids = parse_csv_env("ML_PRODUCT_IDS")
    seller_ids = parse_csv_env("ML_SELLER_IDS")

    if not product_ids and not seller_ids:
        logger.info("ML Worker: No inputs (ML_PRODUCT_IDS / ML_SELLER_IDS). Nothing to do.")
        return {"success": True, "items_fetched": 0, "items_inserted": 0, "blocked_jobs": 0}

    # ✅ FX required by your DB/SP
    # TEMP: set env FX_RATE_TO_USD. Later: read from DB (exchangeRates table)
    fx_rate_to_usd = float(os.getenv("FX_RATE_TO_USD", "0") or 0)
    fx_as_of_date = os.getenv("FX_AS_OF_DATE") or datetime.now(timezone.utc).date().isoformat()

    if fx_rate_to_usd <= 0:
        # fail fast so you don't insert broken rows
        raise ValueError("FX_RATE_TO_USD env var must be set > 0 (required for sellListings).")

    logger.info("ML Worker: Started")
    logger.info("Config => market=%s limit=%s max_pages=%s call_details=%s", site_market, limit, max_pages, call_details)
    logger.info("Inputs => product_ids=%s seller_ids=%s", len(product_ids), len(seller_ids))
    logger.info("FX => rate_to_usd=%s as_of=%s", fx_rate_to_usd, fx_as_of_date)

    inserted = 0
    total_items = 0
    blocked = 0

    # -----------------------------
    # A) PRODUCT IDS FLOW (recommended)
    # -----------------------------
    for pid in product_ids:
        logger.info("Product job => product_id=%s", pid)

        offset = 0
        page = 0

        while page < max_pages:
            data = ml_product_items(pid, offset=offset, limit=limit)

            if _is_blocked_payload(data):
                logger.error("  product_items blocked (403) product_id=%s request_id=%s", pid, data.get("request_id"))
                blocked += 1
                break

            results = (data.get("results", []) or [])
            paging = (data.get("paging", {}) or {})
            total = int(paging.get("total", 0) or 0)

            if not results:
                logger.info("  No results at offset=%s. Stop product job.", offset)
                break

            item_ids = [r.get("item_id") for r in results if r.get("item_id")]
            total_items += len(item_ids)

            # Default: use listing rows directly (no /items/{id})
            items_detail = results

            # Optional: best-effort enrich (will not stop inserts)
            if call_details:
                enriched = []
                for item_id in item_ids:
                    detail = ml_item(item_id)
                    if _is_blocked_payload(detail):
                        logger.warning("  Item detail blocked (403) id=%s request_id=%s", item_id, detail.get("request_id"))
                        fallback = next((r for r in results if r.get("item_id") == item_id), None)
                        if fallback:
                            fallback = dict(fallback)
                            fallback["details_blocked"] = 1
                            fallback["details_http_status"] = 403
                            enriched.append(fallback)
                        continue
                    enriched.append(detail)
                items_detail = enriched

            # --------------------------------------------------
            # Map to sellListings payload (SP schema)
            # --------------------------------------------------
            sell_listings_payload = []
            for it in items_detail:
                try:
                    mapped = map_ml_item_to_selllisting(
                        it,
                        market=site_market,
                        fx_rate_to_usd=fx_rate_to_usd,
                        fx_as_of_date=fx_as_of_date,
                    )

                    # traceability (optional - SP will ignore unknown fields)
                    mapped["details_source"] = "items" if "id" in it else "product_items"

                    sell_listings_payload.append({**mapped, "action": "1"})
                except Exception as e:
                    logger.error("  Map failed: %s", e)

            if sell_listings_payload:
                payload = {"sellListings": sell_listings_payload}
                logger.info("SELLLISTINGS PAYLOAD (first item): %s", json.dumps(payload["sellListings"][0], ensure_ascii=False)[:2500])

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

    logger.info("ML Worker: Done. total_items=%s inserted_rows=%s blocked_jobs=%s", total_items, inserted, blocked)
    return {"success": True, "items_fetched": total_items, "items_inserted": inserted, "blocked_jobs": blocked}


def run_ml_sell_listings_worker(mytimer: func.TimerRequest) -> None:
    now_utc = datetime.now(timezone.utc).isoformat()
    logger.info("ML Worker: Timer fired at %s | past_due=%s", now_utc, getattr(mytimer, "past_due", False))

    if getattr(mytimer, "past_due", False):
        logger.warning("ML Worker: The timer is past due!")

    result = process_ml_listings()
    logger.info(
        "ML Worker: Result = success=%s items_fetched=%s items_inserted=%s blocked_jobs=%s",
        result.get("success"),
        result.get("items_fetched"),
        result.get("items_inserted"),
        result.get("blocked_jobs"),
    )


# Azure Functions entrypoint
def main(mytimer: func.TimerRequest) -> None:
    run_ml_sell_listings_worker(mytimer)
