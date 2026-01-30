"""
Azure Functions App - Main Entry Point

This module contains all timer trigger functions that call the respective workers.
All schedules are controlled from here - function.json files are ignored.

Schedule Notes:
- All schedules use UTC timezone (Linux consumption default)
- Hermosillo timezone is UTC-7
- For 9:05 Hermosillo = 16:05 UTC → schedule: "0 5 16 * * *"
"""

import azure.functions as func
import logging
from mlSearchWorker import run_ml_search_worker


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = func.FunctionApp()

# Import all worker run functions
from publishJobsWorker import run_publish_jobs_worker
from exchangeRatesWorker import run_exchange_rates_worker
from mlSellListingsWorker import run_ml_sell_listings_worker
from amazonListingsWorker import run_amazon_listings_worker
from ebayListingsWorker import run_ebay_listings_worker

# =============================================================================
# Timer Trigger Functions
# =============================================================================

@app.timer_trigger(
    schedule="*/30 * * * * *",  # Every 30 seconds
    arg_name="mytimer",
    run_on_startup=True,
    use_monitor=False
)
def publish_jobs_timer(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger for processing publish jobs from the database.
    
    Schedule: Every 30 seconds
    Worker: Processes pending jobs that need to be published to external platforms.
    """
    logging.info("publish_jobs_timer fired")
    run_publish_jobs_worker(mytimer)


@app.timer_trigger(
    schedule="0 */5 * * * *",  # Every 5 minutes at :00, :05, :10, etc.
    arg_name="mytimer",
    run_on_startup=True,
    use_monitor=False
)

##
def ml_competitor_timer(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger for MercadoLibre competitor listings extraction.
    
    Schedule: Every 5 minutes
    Worker: Extracts ML listings based on keywords/categories/seller_ids and saves to DB.
    
    Environment Variables:
        ML_KEYWORDS: Comma-separated keywords to search
        ML_CATEGORIES: Optional comma-separated ML categories
        ML_SELLER_IDS: Optional comma-separated seller IDs
        ML_MARKET: Marketplace code (default: MX)
        ML_LIMIT: Results per page (default: 50)
        ML_MAX_PAGES: Maximum pages to fetch (default: 10)
        ML_CALL_ITEMS_DETAIL: Whether to fetch item details (1=true)
    """
    logging.info("ml_competitor_timer fired")
    run_ml_sell_listings_worker(mytimer)

@app.timer_trigger(
    schedule="0 */15 * * * *",  # Every 15 minutes at :00, :15, :30, :45
    arg_name="mytimer",
    run_on_startup=True,
    use_monitor=False
)

def amazon_listings_timer(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger for Amazon listings extraction.
    
    Schedule: Every 15 minutes
    Worker: Extracts Amazon listings based on keywords and saves to DB.
    
    Environment Variables:
        AMAZON_KEYWORDS: Comma-separated keywords to search
        AMAZON_MARKETPLACE: Marketplace code (default: MX)
        AMAZON_API_BASE: Amazon API base URL
        AMAZON_API_KEY: Amazon API authentication key
    """
    logging.info("amazon_listings_timer fired")
    run_amazon_listings_worker(mytimer)

@app.timer_trigger(
    schedule="0 5 16 * * *",  # Daily at 16:05 UTC = 09:05 Hermosillo (UTC-7)
    arg_name="mytimer",
    run_on_startup=True,
    use_monitor=False
)
def exchange_rates_timer(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger for exchange rates fetch.
    
    Schedule: Daily at 16:05 UTC (09:05 Hermosillo)
    Worker: Fetches MXN→USD exchange rate from Frankfurter API and upserts to DB.
    
    Note: Frankfurter API provides ECB reference rates.
    """
    logging.info("exchange_rates_timer fired")
    run_exchange_rates_worker(mytimer)


@app.timer_trigger(
    schedule="0 */20 * * * *",  # Every 20 minutes at :00, :20, :40
    arg_name="mytimer",
    run_on_startup=True,
    use_monitor=False
)
def ebay_listings_timer(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger for eBay listings extraction.
    
    Schedule: Every 20 minutes
    Worker: Extracts eBay listings based on keywords and saves to DB.
    
    Environment Variables:
        EBAY_KEYWORDS: Comma-separated keywords to search
        EBAY_MARKETPLACE: Marketplace code (default: MX)
        EBAY_API_BASE: eBay API base URL
        EBAY_API_KEY: eBay API authentication key
        EBAY_SANDBOX: Use eBay sandbox (1=true)
    """
    logging.info("ebay_listings_timer fired")
    run_ebay_listings_worker(mytimer)

@app.timer_trigger(
    schedule="*/30 * * * * *",  # Every 30 seconds
    arg_name="mytimer",
    run_on_startup=True,
    use_monitor=False
)
def ml_search_timer(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger for ML Search Jobs (Queue-based).
    Schedule: Every 30 seconds
    Worker: Dequeue search jobs from dbo.ml_jobs and process them.
    """
    logging.info("ml_search_timer fired")
    run_ml_search_worker(mytimer)


