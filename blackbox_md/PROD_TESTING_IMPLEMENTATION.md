# Production Testing Implementation Plan

## 🎯 Current State Analysis

**Azure Function App:**
- Name: `smartloans-workers-func`
- Resource Group: `rg-smartloans-workers`
- Location: East US
- Status: **Stopped** (needs to be started)
- Default Domain: `smartloans-workers-func.azurewebsites.net`
- Plan: `EastUSLinuxDynamicPlan` (Y1)
- Functions: 4 timer triggers already configured but showing errors

**Issue:** "Unable to load some functions" - likely due to:
1. Mixed function app (v1 and v2 function definitions)
2. Missing or corrupted function configurations
3. Code deployment needed

---

## 📋 Implementation Steps

### Step 1: Clean Up Legacy Files (Fix Mixed Function App Warning)
**Status:** ✅ DONE (from TODO.md)
- [x] Deleted `mlSellListingsWorker/function.json`
- [x] Deleted `exchange_rates_timer.OLD/` folder
- [x] Updated `shared/ml_api.py` with browser headers
- [x] Updated `shared/retry.py` with smart backoff

### Step 2: Update Code with Production Enhancements
**Files to modify:**
1. `mlSellListingsWorker/__init__.py` - Add structured logging
2. `exchangeRatesWorker/__init__.py` - Add structured logging  
3. `amazonListingsWorker/__init__.py` - Add structured logging
4. `publishJobsWorker/__init__.py` - Add structured logging
5. `function_app.py` - Add health check endpoint and error handling

### Step 3: Create Production Configuration
**Files to create:**
1. `production.settings.json` - Production environment variables
2. `.github/workflows/deploy.yml` - CI/CD pipeline (optional)

### Step 4: Deploy to Azure
**Commands to execute:**
```bash
# Start the Function App
az functionapp start --name smartloans-workers-func --resource-group rg-smartloans-workers

# Deploy updates
func azure functionapp publish smartloans-workers-func
```

### Step 5: Validate in Production
**Actions:**
1. Check function status in Azure Portal
2. View logs to verify execution
3. Check database for processed items
4. Monitor for errors

---

## 🔧 Specific Code Changes

### Change 1: Add Structured Logging to mlSellListingsWorker
```python
import logging
logger = logging.getLogger(__name__)

def run_ml_sell_listings_worker(mytimer: func.TimerRequest) -> None:
    logger.info("ML Worker started at %s", mytimer.timestamp)
    
    if mytimer.past_due:
        logger.warning("Timer is past due!")
    
    try:
        result = process_ml_listings()
        logger.info("ML Worker completed: items_fetched=%d, items_inserted=%d", 
                   result.get('items_fetched', 0), 
                   result.get('items_inserted', 0))
    except Exception as e:
        logger.error("ML Worker failed: %s", str(e), exc_info=True)
        raise
```

### Change 2: Add Error Handling to All Workers
```python
def run_exchange_rates_worker(mytimer: func.TimerRequest) -> None:
    logger.info("Exchange rates worker started")
    
    try:
        result = process_exchange_rates()
        logger.info("Exchange rates worker completed: %s", result)
    except Exception as e:
        logger.error("Exchange rates worker failed: %s", str(e), exc_info=True)
        # Don't re-raise to avoid timer trigger marking as failed
        # Or re-raise if you want Azure to retry
        raise
```

### Change 3: Create production.settings.json
```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=workercontainer;AccountKey=<YOUR_PROD_KEY>;EndpointSuffix=core.windows.net",
    "AZURE_SQL_CONNECTION_STRING": "<YOUR_PROD_DB_CONNECTION>",
    "SMARTLOANS_BACKEND_URL": "https://api.mercadolibre.com",
    "ML_SITE_ID": "MLM",
    "ML_MARKET": "MX",
    "ML_KEYWORDS": "iphone,ps5,airpods",
    "ML_CATEGORIES": "",
    "ML_SELLER_IDS": "",
    "ML_LIMIT": "50",
    "ML_MAX_PAGES": "10",
    "ML_TIMEOUT_SECONDS": "25",
    "ML_CALL_ITEMS_DETAIL": "1",
    "WEBSITE_RUN_FROM_PACKAGE": "1"
  }
}
```

---

## 🚀 Deployment Commands

### Command 1: Start the Function App
```bash
az functionapp start --name smartloans-workers-func --resource-group rg-smartloans-workers
```

### Command 2: Deploy Updated Code
```bash
func azure functionapp publish smartloans-workers-func --publish-local-settings
```

### Command 3: View Logs
```bash
# Real-time logs
az functionapp logstream --name smartloans-workers-func --resource-group rg-smartloans-workers

# Or use Kudu
# https://smartloans-workers-func.scm.azurewebsites.net/DebugConsole
```

### Command 4: Restart if Needed
```bash
az functionapp restart --name smartloans-workers-func --resource-group rg-smartloans-workers
```

---

## ✅ Validation Checklist

- [ ] Function App status: Running
- [ ] All 4 functions: Enabled (no errors)
- [ ] Logs showing successful executions:
  - [ ] publish_jobs_timer running every 30 seconds
  - [ ] ml_competitor_timer running every 5 minutes
  - [ ] amazon_listings_timer running every 15 minutes
  - [ ] exchange_rates_timer running daily
- [ ] Database records being created/updated
- [ ] No 403 errors in logs (ML API direct calls working)
- [ ] Retry logic triggering on errors
- [ ] Response times within acceptable limits

---

## 🔍 Troubleshooting

### "Unable to load some functions" Error
**Cause:** Mixed function definition types (v1 function.json + v2 decorators)

**Solution:**
```bash
# Remove any remaining function.json files
find . -name "function.json" -type f -exec rm {} \;

# Redeploy
func azure functionapp publish smartloans-workers-func
```

### Functions Not Triggering
**Check:**
1. Timer syntax is correct (CRON expressions)
2. Timer is enabled in Azure Portal
3. Timer hasn't reached next occurrence

**Fix:**
```bash
# Disable and re-enable function
az functionapp function update --name smartloans-workers-func \
  --resource-group rg-smartloans-workers \
  --function-name ml_competitor_timer \
  --bindings '{}'
```

### Database Connection Issues
**Check:**
1. Connection string is correct in Application Settings
2. Firewall rules allow Azure IP ranges
3. Credentials are valid

**Fix:**
```bash
# Update Application Settings
az functionapp config appsettings set \
  --name smartloans-workers-func \
  --resource-group rg-smartloans-workers \
  --settings AZURE_SQL_CONNECTION_STRING="<new-connection-string>"
```

---

## 📝 Next Actions

1. **Confirm this plan** - Do you approve these changes?
2. **Specify any customizations** - Different logging levels, specific functions to focus on?
3. **Production credentials** - Do you have the production storage account key and database connection string ready?
4. **Start deployment** - Once approved, I'll:
   - Add structured logging to all workers
   - Create production configuration
   - Execute deployment commands
   - Validate in production

---

## ⏱️ Estimated Time

- Code updates: 10-15 minutes
- Deployment: 5-10 minutes
- Validation: 10-15 minutes
- **Total: ~30-40 minutes**

Would you like me to proceed with this plan?
