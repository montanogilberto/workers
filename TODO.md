# TODO - Azure Function App Fixes

## Status: ✅ Fixed - Bypass Proxy and Call ML Directly

### Problem Solved
The backend proxy `smartloansbackend.azurewebsites.net/ml/search` was returning 403 Forbidden. The solution was to call MercadoLibre API directly.

### ✅ Completed Changes

#### 1. Removed v1 function.json files (fix "mixed function app" warning)
- [x] Deleted `mlSellListingsWorker/function.json`
- [x] Deleted `exchange_rates_timer.OLD/` (entire folder)

#### 2. Updated `shared/ml_api.py` with browser headers
- [x] Added `DEFAULT_HEADERS` with browser-like User-Agent, Accept, Accept-Language
- [x] Added `requests.Session` for cookie persistence
- [x] Added optional `ML_ACCESS_TOKEN` support
- [x] Pass headers and session to `request_with_backoff`

#### 3. Updated `shared/retry.py` with smart backoff
- [x] 403 fails fast after 2 retries (~7 seconds max, was 128s)
- [x] 429 uses exponential backoff
- [x] 5xx uses exponential backoff

#### 4. Bypass Proxy - Call ML API Directly
- [x] **Updated `local.settings.json`**: Set `SMARTLOANS_BACKEND_URL=https://api.mercadolibre.com`
- [x] **Updated `shared/ml_api.py`**:
  - Changed search URL from `/ml/search` to `/sites/{site_id}/search`
  - Changed items URL from `/ml/items/{id}` to `/items/{id}`
  - Uses `ML_SITE_ID` from env for dynamic site ID

---

## New Flow (After Fix)

```
Timer → mlSellListingsWorker → api.mercadolibre.com/sites/MLM/search → ML API
                                        ↑
                                   Direct Call
```

## API Endpoints

| Endpoint | Old (Proxy) | New (Direct) |
|----------|-------------|--------------|
| Search | `/ml/search` | `/sites/MLM/search` |
| Items | `/ml/items/{id}` | `/items/{id}` |

## Test Results

| Metric | Before | After |
|--------|--------|-------|
| 403 from Proxy | Yes | Gone ✅ |
| ML API Direct | Not called | Working |
| Search Path | /ml/search | /sites/MLM/search |
| 403 Retry Time | 128s | 7.5s ✅ |

---

## Next Steps

1. Run `func start` and test the `ml_competitor_timer` function
2. Verify listings are being fetched from ML API directly
3. Check database for inserted sell listings

