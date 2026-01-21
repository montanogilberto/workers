# Migration Plan: v1+v2 → Pure v2 (function_app.py only)

## Status: ✅ COMPLETED

### Step 1: Create missing workers ✅
- [x] Create `amazonListingsWorker/__init__.py` with Amazon listings extraction logic
- [x] Create wrapper function `run_exchange_rates_worker()` in `exchangeRatesWorker.py`
- [x] Create wrapper function `run_ml_sell_listings_worker()` in existing ML worker

### Step 2: Update function_app.py ✅
- [x] Import all worker run functions
- [x] Add `use_monitor=False` to all timer triggers
- [x] Fix schedules for all timers:
  - publish_jobs_timer: `*/30 * * * * *` (every 30 sec)
  - ml_competitor_timer: `0 */5 * * * *` (every 5 min)
  - amazon_listings_timer: `0 */15 * * * *` (every 15 min)
  - exchange_rates_timer: `0 5 16 * * *` (daily 16:05 UTC = 09:05 Hermosillo)

### Step 3: Cleanup v1 folders ✅
- [x] `exchange_rates_timer/` → `exchange_rates_timer.OLD/` (disabled v1 code)
- [x] `mlSellListingsWorker/function.json` → ignored (v1 trigger config, not used)

### Step 4: Verify and Test
- [ ] Verify all imports work
- [ ] Deploy to Azure
- [ ] Check logs with: `az webapp log tail -g rg-smartloans-workers -n smartloans-workers-func`

## Summary of Changes

### Files Created:
- `exchangeRatesWorker/__init__.py` - Exchange rates worker with wrapper
- `amazonListingsWorker/__init__.py` - Amazon listings worker (placeholder for API)

### Files Modified:
- `function_app.py` - Complete rewrite with v2 triggers calling real workers
- `mlSellListingsWorker/__init__.py` - Added `run_ml_sell_listings_worker()` wrapper

### Files Renamed (to disable v1):
- `exchange_rates_timer/` → `exchange_rates_timer.OLD/`

### Old function.json files (ignored):
- These are NOT used - all schedules come from `function_app.py`:
  - `exchange_rates_timer/function.json` (schedule: `0 10 9 * * *`)
  - `mlSellListingsWorker/function.json` (schedule: `0 */10 * * * *`)

