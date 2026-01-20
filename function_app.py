"""
Azure Functions App - Publish Jobs Worker

This module contains the timer trigger function for processing publish jobs.
"""

import azure.functions as func
import datetime
import json
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = func.FunctionApp()

# Import the publish jobs worker function
from publishJobsWorker import run_publish_jobs_worker

# Register the timer trigger function
# Schedule: every 5 minutes (0 */5 * * * *)
# @app.timer_trigger(schedule="0 */5 * * * *", arg_name="mytimer", run_on_startup=True)
@app.timer_trigger(schedule="*/30 * * * * *", arg_name="mytimer", run_on_startup=True)
def publish_jobs_timer(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger function for the publish jobs worker.
    
    Args:
        mytimer: Azure Functions timer trigger context.
    """
    run_publish_jobs_worker(mytimer)



@app.timer_trigger(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def ml_competitor_timer(myTimer: func.TimerRequest) -> None:
    
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def amazon_listings_timer(myTimer: func.TimerRequest) -> None:
    
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def exchange_rates_timer(myTimer: func.TimerRequest) -> None:
    
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')