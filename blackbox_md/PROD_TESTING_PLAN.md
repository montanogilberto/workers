# Production Testing Plan for Azure Functions

## 📋 Project Overview
This is an Azure Functions project with timer-triggered workers that process:
- **publish_jobs_timer**: Processes publish jobs every 30 seconds
- **ml_competitor_timer**: Extracts ML competitor listings every 5 minutes
- **amazon_listings_timer**: Extracts Amazon listings every 15 minutes
- **exchange_rates_timer**: Fetches exchange rates daily at 09:05 Hermosillo

## 🎯 Objective
Update functions to enable production testing with proper deployment and validation.

---

## 📝 Steps to Update Functions for Production Testing

### Step 1: Code Changes (Local Development)

#### 1.1 Modify Configuration for Production
```bash
# Option A: Use separate production settings file
cp local.settings.json production.settings.json

# Edit production.settings.json with production values
# - Update AzureWebJobsStorage with production storage account
# - Update AZURE_SQL_CONNECTION_STRING with production DB
# - Keep ML API settings (same for prod)
```

#### 1.2 Update Environment Variables in Azure Portal
```
FUNCTIONS_WORKER_RUNTIME: python
AzureWebJobsStorage: (production storage connection string)
AZURE_SQL_CONNECTION_STRING: (production DB connection)
SMARTLOANS_BACKEND_URL: https://api.mercadolibre.com
ML_SITE_ID: MLM
ML_MARKET: MX
ML_KEYWORDS: iphone,ps5,airpods
ML_LIMIT: 50
ML_MAX_PAGES: 10
ML_TIMEOUT_SECONDS: 25
ML_CALL_ITEMS_DETAIL: 1
```

#### 1.3 Add Logging and Monitoring
```python
# In each worker, add structured logging
import logging

logger = logging.getLogger(__name__)

def run_ml_sell_listings_worker(mytimer: func.TimerRequest) -> None:
    logger.info("ML Worker started")
    try:
        result = process_ml_listings()
        logger.info(f"ML Worker completed: {result}")
    except Exception as e:
        logger.error(f"ML Worker failed: {e}")
        raise
```

#### 1.4 Add Health Check Endpoints (Optional)
```python
@app.timer_trigger(schedule="0 */30 * * * *", arg_name="healthTimer")
def health_check_timer(healthTimer: func.TimerRequest) -> None:
    """Health check function to verify all workers are running."""
    logging.info("Health check triggered")
```

### Step 2: Local Testing Before Deployment

#### 2.1 Run Functions Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Start Azure Functions host
func start

# Test specific function
func test <function_name>
```

#### 2.2 Test with Production Configuration
```bash
# Use production settings
export AzureWebJobsStorage="<prod-storage-connection>"
export AZURE_SQL_CONNECTION_STRING="<prod-db-connection>"

# Run function locally
python -m mlSellListingsWorker
```

### Step 3: Deploy to Azure

#### 3.1 Using Azure Functions Core Tools
```bash
# Login to Azure
az login

# Create function app (if not exists)
az functionapp create \
  --resource-group smartloans-workers \
  --consumption-plan-location eastus \
  --runtime python \
  --functions-version 4 \
  --name smartloans-workers-prod \
  --storage-account smartloansstorageprod

# Deploy
func azure functionapp publish smartloans-workers-prod
```

#### 3.2 Using GitHub Actions (Recommended)
Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy to Production
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest tests/ -v
          python -m mlSellListingsWorker  # Manual test
      - name: Deploy to Azure
        uses: Azure/functions-action@v1
        with:
          app-name: smartloans-workers-prod
          publish-profile: ${{ secrets.AZURE_FUNCTIONAPP_PUBLISH_PROFILE }}
```

### Step 4: Production Testing Strategies

#### 4.1 Gradual Rollout
```python
# Add feature flag in workers
import os

FEATURE_FLAG = os.getenv("ENABLE_NEW_FEATURE", "false") == "true"

def process_ml_listings():
    if FEATURE_FLAG:
        # New implementation
        return process_ml_listings_v2()
    else:
        # Original implementation
        return process_ml_listings_v1()
```

#### 4.2 Canary Deployment
```python
# Process 10% of jobs with new code
import random

def run_ml_sell_listings_worker(mytimer: func.TimerRequest) -> None:
    if random.random() < 0.1:
        # 10% traffic - new code
        process_ml_listings_v2()
    else:
        # 90% traffic - original code
        process_ml_listings_v1()
```

#### 4.3 Shadow Mode
```python
# Run new code alongside old, compare results
def run_ml_sell_listings_worker(mytimer: func.TimerRequest) -> None:
    # Original
    result_original = process_ml_listings_v1()
    
    # Shadow - results logged but not used
    result_shadow = process_ml_listings_v2()
    
    # Log comparison
    logging.info(f"Original: {result_original}, Shadow: {result_shadow}")
```

### Step 5: Monitoring and Validation

#### 5.1 Application Insights Integration
```python
# Add to function_app.py
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from opentelemetry import trace

# Configure tracing
trace.set_tracer_provider(
    TracerProvider(
        tracing_exporter=AzureMonitorTraceExporter(
            connection_string="InstrumentationKey=..."
        )
    )
)
```

#### 5.2 Log Analysis
```bash
# View logs in Azure
az functionapp logstream --name smartloans-workers-prod

# Or use Application Insights
# Query: traces | where timestamp > ago(1h)
```

#### 5.3 Key Metrics to Monitor
- Function execution duration
- Success/failure rates
- Items processed per run
- API response times
- Database operation times
- Error rates by type

---

## 📂 Files to Modify

| File | Changes Needed |
|------|----------------|
| `function_app.py` | Add logging, health checks, feature flags |
| `mlSellListingsWorker/__init__.py` | Add logging, feature flags, error handling |
| `shared/ml_api.py` | Add logging, timeout monitoring |
| `shared/retry.py` | Add retry metrics |
| `local.settings.json` | Create production copy |

---

## 🚀 Quick Commands

```bash
# Local development
func start

# Test specific worker
python -m mlSellListingsWorker

# Deploy to Azure
func azure functionapp publish smartloans-workers-prod

# View logs
az functionapp logstream --name smartloans-workers-prod

# Restart function app
az functionapp restart --name smartloans-workers-prod --resource-group smartloans-workers
```

---

## ✅ Pre-Production Checklist

- [ ] Code reviewed and tested locally
- [ ] All environment variables configured in Azure
- [ ] Application Insights enabled
- [ ] Logging added to all workers
- [ ] Error handling implemented
- [ ] Timeouts configured appropriately
- [ ] Retry logic tested
- [ ] Database migrations ready (if any)
- [ ] Rollback plan documented
- [ ] Team notified of deployment

