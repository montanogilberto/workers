import os
import json
import logging
import requests
import azure.functions as func
from datetime import datetime
from db import exec_sp_json  # usando tu db.py

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"

def main(mytimer: func.TimerRequest) -> None:
    logger.info("exchangeRates worker started")

    # 1) pedir MXN->USD (USD por 1 MXN)
    params = {"base": "MXN", "symbols": "USD"}
    r = requests.get(FRANKFURTER_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    as_of_date = data["date"]              # yyyy-mm-dd
    rate = data["rates"]["USD"]            # decimal

    # 2) upsert a SQL
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
    logger.info("exchangeRates upsert result: %s", res)
