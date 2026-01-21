"""
Exchange Rates Worker - Azure Function Wrapper

This module provides the Azure Functions timer trigger wrapper for the exchange rates worker.
"""

import os
import json
import logging
import requests
import azure.functions as func
from datetime import datetime

from shared.db import exec_sp_json

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"


def fetch_exchange_rates():
    """
    Fetch exchange rates from Frankfurter API.
    
    Returns:
        dict: Exchange rate data with date and rates.
    """
    params = {"base": "MXN", "symbols": "USD"}
    r = requests.get(FRANKFURTER_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def process_exchange_rates():
    """
    Main logic: fetch FX rates and upsert to database.
    
    Returns:
        dict: Result with status and message.
    """
    data = fetch_exchange_rates()
    
    as_of_date = data["date"]  # yyyy-mm-dd
    rate = data["rates"]["USD"]  # decimal
    
    payload = {
        "exchangeRates": [{
            "fromCurrency": "MXN",
            "toCurrency": "USD",
            "rate": rate,
            "asOfDate": as_of_date,
            "source": "frankfurter_ecb"
        }]
    }
    
    res = exec_sp_json("dbo.sp_exchangeRates_upsert", payload)
    return {
        "success": True,
        "date": as_of_date,
        "rate": rate,
        "db_result": res
    }


def run_exchange_rates_worker(mytimer: func.TimerRequest) -> None:
    """
    Azure Functions timer trigger entry point for exchange rates worker.
    
    Args:
        mytimer: Azure Functions timer trigger context.
    """
    logger.info("exchangeRates_worker started")
    
    if mytimer.past_due:
        logger.warning('The timer is past due!')
    
    try:
        result = process_exchange_rates()
        logger.info(
            f"exchangeRates_worker completed: date={result['date']}, "
            f"rate={result['rate']}, db_result={result['db_result']}"
        )
    except Exception as e:
        logger.error(f"exchangeRates_worker failed: {str(e)}", exc_info=True)
        raise


# Standalone function for direct execution (non-Azure)
def main():
    """Run exchange rates worker outside of Azure Functions."""
    result = process_exchange_rates()
    print(f"Exchange rates updated: {result}")
    return result

