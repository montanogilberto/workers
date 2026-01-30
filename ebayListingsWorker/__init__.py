"""
eBay Listings Worker - Azure Function Wrapper

This module provides the Azure Functions timer trigger wrapper for eBay listings extraction.
Implements stable timestamp approach to avoid duplicate rows in the database.
"""

import os
import json
import logging
import azure.functions as func
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.db import exec_sp_json

logger = logging.getLogger(__name__)

# eBay API configuration
EBAY_API_BASE = os.getenv("EBAY_API_BASE", "https://api.ebay.com")
EBAY_API_KEY = os.getenv("EBAY_API_KEY")
EBAY_SANDBOX = os.getenv("EBAY_SANDBOX", "0") == "1"


def _stable_listing_ts(fx_as_of_date: str) -> str:
    """
    Generate a stable listing timestamp at midnight UTC from fxAsOfDate.
    
    This ensures the same listing processed multiple times on the same day
    will update the same database row instead of creating duplicates.
    
    Args:
        fx_as_of_date: Date string in 'YYYY-MM-DD' format.
    
    Returns:
        ISO format timestamp at 00:00:00 UTC.
    """
    if not fx_as_of_date:
        return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    dt = datetime.fromisoformat(fx_as_of_date).replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def parse_csv_env(name: str, default: str = "") -> List[str]:
    """Parse a comma-separated environment variable into a list."""
    raw = os.getenv(name, default) or ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts


def chunk(lst: List[Any], n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def fetch_ebay_listings(keyword: str, marketplace: str = "EBAY_MX") -> List[Dict[str, Any]]:
    """
    Fetch listings from eBay API for a given keyword.
    
    Args:
        keyword: Search keyword.
        marketplace: eBay marketplace code.
    
    Returns:
        List of item dictionaries.
    """
    # Placeholder for actual eBay API integration
    # Replace with real API calls when available
    logger.info(f"Fetching eBay listings for keyword='{keyword}' marketplace='{marketplace}'")
    
    # TODO: Implement actual eBay API call
    # Example structure:
    # url = f"{EBAY_API_BASE}/buy/browse/v1/item_summary/search"
    # params = {"q": keyword, "filter": f"marketplaceIds:{marketplace}"}
    # headers = {"Authorization": f"Bearer {EBAY_API_KEY}"}
    # response = requests.get(url, params=params, headers=headers, timeout=30)
    
    # For now, return empty list (no-op mode)
    logger.warning("eBay API not configured - no listings fetched")
    return []


def map_ebay_item_to_selllisting(item: Dict[str, Any], market: str, fx_as_of_date: str = None) -> Dict[str, Any]:
    """
    Map eBay item to sellListing format with stable timestamp.
    
    This follows the same pattern as ML and Amazon workers to ensure
    consistent behavior across all channels.
    
    Args:
        item: eBay item dictionary.
        market: Marketplace code.
        fx_as_of_date: Date string in 'YYYY-MM-DD' format for stable timestamp.
    
    Returns:
        Mapped sellListing dictionary.
    """
    # Use provided fxAsOfDate or default to current date (midnight UTC)
    fx_date = fx_as_of_date or datetime.now(timezone.utc).date().isoformat()
    
    # Calculate USD price if conversion rate available
    fx_rate = float(os.getenv("FX_RATE_TO_USD", "0") or 0)
    price = float(item.get("price", 0) or 0)
    price_usd = price * fx_rate if fx_rate > 0 else 0.0
    
    return {
        "channel": "ebay",
        "market": market,
        "channelItemId": str(item.get("itemId") or item.get("id")),
        "title": item.get("title"),
        "sellPriceOriginal": price,
        "currencyOriginal": item.get("currency") or "MXN",
        "sellPriceUsd": price_usd,
        "fxRateToUsd": fx_rate if fx_rate > 0 else None,
        "fxAsOfDate": fx_date,
        "fulfillmentType": item.get("fulfillment_type"),
        "shippingTimeDays": item.get("shipping_time_days"),
        "rating": item.get("rating"),
        "reviewsCount": item.get("reviews_count"),
        "listingTimestamp": _stable_listing_ts(fx_date),
        "unifiedProductId": item.get("upc") or item.get("epid"),
        "action": "1",
    }


def process_ebay_listings():
    """
    Main logic: fetch eBay listings and upsert to database with stable timestamps.
    
    Returns:
        dict: Result with statistics.
    """
    keywords = parse_csv_env("EBAY_KEYWORDS")
    marketplace = os.getenv("EBAY_MARKETPLACE", "MX")
    # Use FX_AS_OF_DATE for stable timestamp, or default to today (midnight UTC)
    fx_as_of_date = os.getenv("FX_AS_OF_DATE") or datetime.now(timezone.utc).date().isoformat()
    
    if not keywords:
        logger.info("No EBAY_KEYWORDS configured - skipping eBay listings extraction")
        return {"success": True, "keywords_processed": 0, "items_fetched": 0, "items_inserted": 0}
    
    total_fetched = 0
    total_inserted = 0
    
    for keyword in keywords:
        try:
            items = fetch_ebay_listings(keyword, marketplace)
            total_fetched += len(items)
            
            if items:
                # Map to sellListings format with stable timestamp
                sell_listings_payload = []
                for item in items:
                    try:
                        mapped = map_ebay_item_to_selllisting(item, marketplace, fx_as_of_date)
                        sell_listings_payload.append(mapped)
                    except Exception as e:
                        logger.error(f"Failed to map eBay item: {e}")
                
                if sell_listings_payload:
                    payload = {"sellListings": sell_listings_payload}
                    result = exec_sp_json("dbo.sp_sellListings", payload)
                    total_inserted += len(sell_listings_payload)
                    logger.info(f"Inserted {len(sell_listings_payload)} eBay listings for keyword='{keyword}'")
            
        except Exception as e:
            logger.error(f"Failed to process keyword='{keyword}': {str(e)}")
            continue
    
    return {
        "success": True,
        "keywords_processed": len(keywords),
        "items_fetched": total_fetched,
        "items_inserted": total_inserted
    }


def run_ebay_listings_worker(mytimer: func.TimerRequest) -> None:
    """
    Azure Functions timer trigger entry point for eBay listings worker.
    
    Args:
        mytimer: Azure Functions timer trigger context.
    """
    logger.info("ebay_listings_worker started")
    
    if mytimer.past_due:
        logger.warning('The timer is past due!')
    
    try:
        result = process_ebay_listings()
        logger.info(
            f"ebay_listings_worker completed: "
            f"keywords={result['keywords_processed']}, "
            f"fetched={result['items_fetched']}, "
            f"inserted={result['items_inserted']}"
        )
    except Exception as e:
        logger.error(f"ebay_listings_worker failed: {str(e)}", exc_info=True)
        raise


# Standalone function for direct execution (non-Azure)
def main():
    """Run eBay listings worker outside of Azure Functions."""
    result = process_ebay_listings()
    print(f"eBay listings worker completed: {result}")
    return result

