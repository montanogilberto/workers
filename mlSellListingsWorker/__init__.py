import os
import azure.functions as func

from shared.ml_api import ml_search, ml_item
from shared.selllistings_mapper import map_ml_item_to_selllisting
#from shared.db import exec_sp
from shared.db import exec_sp_json

def parse_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "") or ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def process_ml_listings():
    """
    Main logic: fetch ML listings and upsert to database.
    
    Returns:
        dict: Result with statistics.
    """
    site_market = os.getenv("ML_MARKET", "MX")
    limit = int(os.getenv("ML_LIMIT", "50"))
    max_pages = int(os.getenv("ML_MAX_PAGES", "10"))
    call_details = os.getenv("ML_CALL_ITEMS_DETAIL", "1") == "1"

    keywords = parse_csv_env("ML_KEYWORDS")
    categories = parse_csv_env("ML_CATEGORIES")  # optional
    seller_ids = parse_csv_env("ML_SELLER_IDS")  # optional

    # Basic guard
    if not keywords and not categories and not seller_ids:
        print("ML Worker: No inputs (ML_KEYWORDS / ML_CATEGORIES / ML_SELLER_IDS). Nothing to do.")
        return {"success": True, "items_fetched": 0, "items_inserted": 0}

    print("ML Worker: Started")
    print(f"Config => market={site_market} limit={limit} max_pages={max_pages} call_details={call_details}")

    # Build search jobs (fan-out)
    search_jobs = []

    if keywords:
        for q in keywords:
            search_jobs.append({"q": q, "category": None, "seller_id": None})

    if categories:
        for c in categories:
            # category-only search needs a keyword; ML requires q or category works with empty q sometimes.
            # We'll use q="*" to attempt broad search.
            search_jobs.append({"q": "*", "category": c, "seller_id": None})

    if seller_ids:
        for sid in seller_ids:
            search_jobs.append({"q": "*", "category": None, "seller_id": sid})

    inserted = 0
    total_items = 0

    for job in search_jobs:
        q = job["q"]
        category = job["category"]
        seller_id = job["seller_id"]

        print(f"Search job => q={q} category={category} seller_id={seller_id}")

        offset = 0
        page = 0

        while page < max_pages:
            data = ml_search(q, category=category, seller_id=seller_id, offset=offset, limit=limit)
            results = data.get("results", [])
            paging = data.get("paging", {}) or {}
            total = int(paging.get("total", 0) or 0)

            if not results:
                print(f"  No results at offset={offset}. Stop job.")
                break

            item_ids = [r.get("id") for r in results if r.get("id")]
            total_items += len(item_ids)

            # Detail calls
            items_detail = []
            if call_details:
                for batch in chunk(item_ids, 20):
                    for item_id in batch:
                        try:
                            items_detail.append(ml_item(item_id))
                        except Exception as e:
                            print(f"  Item detail failed id={item_id}: {e}")
            else:
                # use search results as minimal "item"
                items_detail = results

            # Map to sellListings payload
            sell_listings_payload = []
            for it in items_detail:
                try:
                    mapped = map_ml_item_to_selllisting(it, market=site_market)
                    sell_listings_payload.append({**mapped, "action": "1"})
                except Exception as e:
                    print(f"  Map failed: {e}")

            if sell_listings_payload:
                payload = {"sellListings": sell_listings_payload}
                out = exec_sp_json("sp_sellListings", payload)
                inserted += len(sell_listings_payload)
                print(f"  Inserted batch: {len(sell_listings_payload)} | SP msg={out.get('msg')} error={out.get('error')}")

            offset += limit
            page += 1

            # stop if we already reached total
            if total and offset >= total:
                break

    print(f"ML Worker: Done. total_items={total_items} inserted_rows={inserted}")
    return {"success": True, "items_fetched": total_items, "items_inserted": inserted}


def run_ml_sell_listings_worker(mytimer: func.TimerRequest) -> None:
    """
    Azure Functions timer trigger entry point for ML sell listings worker.
    
    Args:
        mytimer: Azure Functions timer trigger context.
    """
    if mytimer.past_due:
        print("ML Worker: The timer is past due!")
    
    result = process_ml_listings()
    print(f"ML Worker: Result = {result}")


# Standalone function for direct execution (non-Azure)
def main():
    """Run ML listings worker outside of Azure Functions."""
    result = process_ml_listings()
    print(f"ML listings worker completed: {result}")
