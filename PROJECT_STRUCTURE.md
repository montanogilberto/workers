# SmartLoans Workers - Project Structure

## Overview
Azure Functions-based workers for extracting competitor listings from MercadoLibre and Amazon, processing jobs, and fetching exchange rates.

## Directory Structure

```
workers/
├── 📄 function_app.py              # Main Azure Functions entry point with timer triggers
├── 📄 host.json                    # Azure Functions host configuration
├── 📄 local.settings.json          # Local environment variables (not committed)
├── 📄 production.settings.json     # Production environment variables template
├── 📄 requirements.txt             # Python dependencies
├── 📄 README.md                    # Project documentation
├── 📄 deploy_to_production.sh      # Deployment script
│
├── 📁 amazonListingsWorker/        # Amazon listings extraction worker
│   └── 📄 __init__.py              # Amazon worker implementation
│
├── 📁 exchangeRatesWorker/         # Exchange rates fetching worker
│   └── 📄 __init__.py              # FX worker implementation
│
├── 📁 mlSearchWorker/              # ML search jobs queue processor
│   ├── 📄 __init__.py              # Timer trigger wrapper
│   └── 📄 main.py                  # ML search job processor
│
├── 📁 mlSellListingsWorker/        # ML competitor listings extraction (main worker)
│   ├── 📄 __init__.py              # Timer trigger + process_ml_listings()
│   └── 📄 main.py                  # Main ML worker logic
│
├── 📁 publishJobsWorker/           # Publish jobs from DB to external platforms
│   └── 📄 __init__.py              # Job publisher implementation
│
├── 📁 shared/                      # Shared modules used by all workers
│   ├── 📄 db.py                    # Azure SQL database operations
│   ├── 📄 fx.py                    # Exchange rate fetching
│   ├── 📄 ml_api.py                # ML API calls via backend proxy ✅ MODIFIED (403 fix)
│   ├── 📄 ml_auth.py               # MercadoLibre OAuth authentication
│   ├── 📄 retry.py                 # Smart backoff retry logic with 403 handling
│   └── 📄 selllistings_mapper.py   # ML item to sellListing mapping
│
├── 📁 security/                    # Security-related modules
│   ├── 📄 worker_key.py            # Worker-to-backend authentication
│   └── 📄 worker_key_backend_fix.py # Suggested fix for backend timing issue
│
└── 📁 blackbox_md/                 # Documentation and planning
    ├── 📄 TODO_403_FIX.md          # 403 error fix tracking
    ├── 📄 TODO_PROGRESS.md         # Progress tracker
    ├── 📄 403_FIX_DOCUMENTATION.md # 403 fix documentation
    ├── 📄 IMPLEMENTATION_PLAN.md   # Implementation details
    ├── 📄 PROJECT_DOCUMENTATION.md # Project overview
    └── 📄 PROD_TESTING_PLAN.md     # Production testing plan
```

## Key Files Description

### function_app.py
**Main Azure Functions app** - Contains all timer trigger functions:
- `publish_jobs_timer` - Every 30 seconds
- `ml_search_timer` - Every 30 seconds (queue-based ML search jobs)
- `ml_competitor_timer` - Every 5 minutes (main ML listings extraction)
- `amazon_listings_timer` - Every 15 minutes
- `exchange_rates_timer` - Daily at 16:05 UTC

### mlSellListingsWorker/__init__.py
**Main ML competitor extraction worker** that:
1. Reads ML_KEYWORDS, ML_CATEGORIES, ML_SELLER_IDS from environment
2. Calls `ml_search()` via backend proxy
3. Fetches item details with `ml_item()`
4. Maps results to sellListings and saves to DB via `sp_sellListings`

### shared/ml_api.py
**ML API client** - Routes ML API calls through backend proxy:
- `ml_search()` - Search ML listings via backend
- `ml_item()` - Get ML item details via backend
- Includes X-Worker-Key header for authentication
- ✅ **MODIFIED**: Added debug logging for 403 fix

### shared/retry.py
**Smart retry logic** with different handling per error:
- 403: Fail fast (likely WAF/anti-bot)
- 429: Exponential backoff with Retry-After support
- 5xx: Exponential backoff

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SMARTLOANS_BACKEND_URL` | Backend proxy URL | ✅ |
| `WORKER_KEY` | Worker-to-backend authentication | ✅ |
| `ML_MARKET` | ML market (MX) | ✅ |
| `ML_KEYWORDS` | Keywords to search (comma-separated) | ✅ |
| `ML_LIMIT` | Results per page (50) | Optional |
| `ML_MAX_PAGES` | Max pages to fetch (10) | Optional |
| `ML_CALL_ITEMS_DETAIL` | Fetch item details (1=true) | Optional |

## Testing Scripts

| Script | Purpose |
|--------|---------|
| `test_ml_api_fix.py` | Basic WORKER_KEY verification |
| `test_ml_api_direct.py` | Direct HTTP request to backend |
| `test_worker_key_full.py` | Comprehensive authentication test |

## Current Status

### ✅ Completed (Worker Side)
- Enhanced logging in `ml_api.py` for debugging
- WORKER_KEY loading verification
- Header debugging logs

### 🔴 Requires Action (Backend Side)
- Verify `WORKER_KEY` is set in Azure Portal
- Restart backend app after configuration
- Check backend logs for errors

## Related Documentation

- See `blackbox_md/TODO_PROGRESS.md` for 403 fix tracking
- See `blackbox_md/403_FIX_DOCUMENTATION.md` for detailed fix info

