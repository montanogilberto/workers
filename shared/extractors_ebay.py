# shared/extractors_ebay.py
from __future__ import annotations
from typing import Any, Dict, List
import logging


class EbayExtractor:
    channel = "ebay"
    market = "US"

    def __init__(self, client: Any, *, query: str):
        """
        client must implement:
          search(query: str, offset: int, limit: int) -> list[dict]
        each dict must contain:
          itemId/title/price/currency/timestamp(optional)
        """
        self.client = client
        self.query = query

    def fetch_last_listings(self, limit: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        offset = 0
        page_size = 200

        while len(out) < limit:
            take = min(page_size, limit - len(out))
            items = self.client.search(query=self.query, offset=offset, limit=take)
            if not items:
                break

            for it in items:
                out.append({
                    "itemId": it.get("itemId"),
                    "id": it.get("itemId"),
                    "title": it.get("title") or "",
                    "price": it.get("price") or 0,
                    "currency_id": it.get("currency") or "USD",
                    "ts": it.get("timestamp"),
                    "details_source": "ebay",
                })

            offset += len(items)
            if len(items) < take:
                break

        logging.info(f"[eBay extractor] query='{self.query}' fetched={len(out)}")
        return out
