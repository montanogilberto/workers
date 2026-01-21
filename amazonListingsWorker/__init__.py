"""
Amazon Listings Worker - Azure Function Wrapper

This module provides the Azure Functions timer trigger wrapper for Amazon listings extraction.
"""

import os
import json
import logging
import azure.functions as func
from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.db import exec_sp_json

logger = logging.getLogger(__name__)

# Amazon API configuration
AMAZON_API_BASE = os.getenv("AMAZON_API_BASE", "https://api.amazon.com")
AMAZON_API_KEY = os.getenv("AMAZON_API_KEY")


def parse_csv_env(name: str, default: str = "") -> List[str]:
    """Parse a comma-separated environment variable into a list."""
    raw = os.getenv(name, default) or ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts


def chunk(lst: List[Any], n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def fetch_amazon_listings(keyword: str, marketplace: str = "MX") -> List[Dict[str, Any]]:
    """
    Fetch listings from Amazon API for a given keyword.
    
    Args:
        keyword: Search keyword.
        marketplace: Amazon marketplace (MX, US, etc.).
    
    Returns:
        List of item dictionaries.
    """
    # Placeholder for actual Amazon API integration
    # Replace with real API calls when available
    logger.info(f"Fetching Amazon listings for keyword='{keyword}' marketplace='{marketplace}'")
    
    # TODO: Implement actual Amazon API call
    # Example structure:
    # url = f"{AMAZON_API_BASE}/products/search"
    # params = {"q": keyword, "marketplace": marketplace}
    # headers = {"Authorization": f"Bearer {AMAZON_API_KEY}"}
    # response = requests.get(url, params=params, headers=headers, timeout=30)
    
    # For now, return empty list (no-op mode)
    logger.warning("Amazon API not configured - no listings fetched")
    return []


def map_amazon_item_to_selllisting(item: Dict[str, Any], market: str) -> Dict[str, Any]:
    """
    Map Amazon item to sellListing format.
    
    Args:
        item: Amazon item dictionary.
        market: Marketplace code.
    
    Returns:
        Mapped sellListing dictionary.
    """
    return {
        "channel": "amazon",
        "market": market,
        "channelItemId": str(item.get("asin")),
        "title": item.get("title"),
        "sellPriceOriginal": float(item.get("price", 0)),
        "currencyOriginal": item.get("currency", "MXN"),
        "sellPriceUsd": 0.0,  # Will be calculated if needed
        "fxRateToUsd": None,
        "fxAsOfDate": None,
        "fulfillmentType": item.get("fulfillment_type"),
        "shippingTimeDays": item.get("shipping_time_days"),
        "rating": item.get("rating"),
        "reviewsCount": item.get("reviews_count"),
        "listingTimestamp": datetime.utcnow().isoformat(),
        "unifiedProductId": item.get("upc"),
        "action": "1",
    }


def process_amazon_listings():
    """
    Main logic: fetch Amazon listings and upsert to database.
    
    Returns:
        dict: Result with statistics.
    """
    keywords = parse_csv_env("AMAZON_KEYWORDS")
    marketplace = os.getenv("AMAZON_MARKETPLACE", "MX")
    
    if not keywords:
        logger.info("No AMAZON_KEYWORDS configured - skipping Amazon listings extraction")
        return {"success": True, "keywords_processed": 0, "items_fetched": 0, "items_inserted": 0}
    
    total_fetched = 0
    total_inserted = 0
    
    for keyword in keywords:
        try:
            items = fetch_amazon_listings(keyword, marketplace)
            total_fetched += len(items)
            
            if items:
                # Map to sellListings format
                sell_listings_payload = []
                for item in items:
                    try:
                        mapped = map_amazon_item_to_selllisting(item, marketplace)
                        sell_listings_payload.append(mapped)
                    except Exception as e:
                        logger.error(f"Failed to map Amazon item: {e}")
                
                if sell_listings_payload:
                    payload = {"sellListings": sell_listings_payload}
                    result = exec_sp_json("dbo.sp_sellListings", payload)
                    total_inserted += len(sell_listings_payload)
                    logger.info(f"Inserted {len(sell_listings_payload)} Amazon listings for keyword='{keyword}'")
            
        except Exception as e:
            logger.error(f"Failed to process keyword='{keyword}': {str(e)}")
            continue
    
    return {
        "success": True,
        "keywords_processed": len(keywords),
        "items_fetched": total_fetched,
        "items_inserted": total_inserted
    }


def run_amazon_listings_worker(mytimer: func.TimerRequest) -> None:
    """
    Azure Functions timer trigger entry point for Amazon listings worker.
    
    Args:
        mytimer: Azure Functions timer trigger context.
    """
    logger.info("amazon_listings_worker started")
    
    if mytimer.past_due:
        logger.warning('The timer is past due!')
    
    try:
        result = process_amazon_listings()
        logger.info(
            f"amazon_listings_worker completed: "
            f"keywords={result['keywords_processed']}, "
            f"fetched={result['items_fetched']}, "
            f"inserted={result['items_inserted']}"
        )
    except Exception as e:
        logger.error(f"amazon_listings_worker failed: {str(e)}", exc_info=True)
        raise


# Standalone function for direct execution (non-Azure)
def main():
    """Run Amazon listings worker outside of Azure Functions."""
    result = process_amazon_listings()
    print(f"Amazon listings worker completed: {result}")
    return result

