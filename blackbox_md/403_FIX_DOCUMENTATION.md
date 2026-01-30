# 403 Error Fix - Complete Documentation

## Problem
Workers getting 403 Forbidden errors from Mercado Libre API when calling `https://api.mercadolibre.com/sites/MLM/search`

## Root Cause Analysis

### Investigation Results

| File | Status | Issue |
|------|--------|-------|
| `shared/ml_api.py` | ✅ Fixed | Was calling ML directly |
| `mlSearchWorker/main.py` | ✅ Fixed | Had placeholder that returned hardcoded 403 |
| `mlSellListingsWorker/__init__.py` | ✅ OK | Already imports from ml_api |
| `shared/ml_auth.py` | ✅ OK | OAuth calls to ML (expected) |

### What Was Wrong

1. **`shared/ml_api.py`** - Used `ML_API_BASE = "https://api.mercadolibre.com"` directly
   - Workers called ML directly, hitting WAF/PolicyAgent

2. **`mlSearchWorker/main.py`** - Had a **placeholder function** that never called ML API:
   ```python
   def try_ml_public_search(payload):
       # This just returned hardcoded 403 - never called the API!
       return (False, 403, {"code": "PolicyAgent"}, None)
   ```

## Solution Implemented

### 1. Updated `shared/ml_api.py`

**Before:**
```python
ML_API_BASE = "https://api.mercadolibre.com"

def ml_search(q: str, ...):
    url = f"{ML_API_BASE}/sites/{site_id}/search"  # Direct ML call
    ...
```

**After:**
```python
BACKEND_BASE = os.getenv("SMARTLOANS_BACKEND_URL", "https://smartloansbackend.azurewebsites.net")

def ml_search(q: str, ...):
    url = f"{BACKEND_BASE}/ml/search"  # Proxy through backend
    ...
```

### 2. Updated `mlSearchWorker/main.py`

**Before:**
```python
# Placeholder that returned hardcoded 403
def try_ml_public_search(payload):
    return (False, 403, {"code": "PolicyAgent"}, None)
```

**After:**
```python
from shared.ml_api import ml_search

def try_ml_public_search(payload):
    # Actually calls ml_search() which routes through backend proxy
    results = ml_search(q=query_text, ...)
    return (True, 200, None, results)
```

## Architecture After Fix

```
Azure Functions Workers
    │
    ├── mlSearchWorker/main.py
    │       └── try_ml_public_search()
    │               └── ml_api.ml_search()
    │                       │
    ├── mlSellListingsWorker/__init__.py
    │       └── ml_api.ml_search()
    │               │
    └── ml_api.py
            └── SMARTLOANS_BACKEND_URL (env var)
                    │
                    ▼
            Backend Proxy
            https://smartloansbackend.azurewebsites.net/ml/search
                    │
                    ├── Injects ML Authorization header
                    ├── Adds browser-like headers
                    └── Forwards to ML
                            │
                            ▼
                    MercadoLibre API
                    https://api.mercadolibre.com/...
```

## Environment Variables Required

Ensure these are set in Azure Function App settings:

| Variable | Value | Purpose |
|----------|-------|---------|
| `SMARTLOANS_BACKEND_URL` | `https://smartloansbackend.azurewebsites.net` | Backend proxy endpoint |
| `ML_ACCESS_TOKEN` | (token) | Used by backend for ML auth |
| `ML_REFRESH_TOKEN` | (token) | Used by backend to refresh |

## Deployment Steps

1. **Deploy updated code:**
   ```bash
   func azure functionapp publish smartloans-workers --python
   ```
   Or use your CI/CD pipeline (GitHub Actions, Azure DevOps)

2. **Verify in Azure Portal:**
   - Go to Function App → Monitor → Log stream
   - Look for calls to `smartloansbackend.azurewebsites.net/ml/search`

3. **Check for direct ML calls (should NOT exist):**
   - Search logs for `api.mercadolibre.com`
   - If found, those are still direct calls - need investigation

## Verification Checklist

- [ ] `mlSearchWorker` imports `ml_search` from `shared.ml_api`
- [ ] `mlSellListingsWorker` imports `ml_search` from `shared.ml_api`
- [ ] `shared/ml_api.py` uses `BACKEND_BASE` from environment
- [ ] `SMARTLOANS_BACKEND_URL` set in Azure Function App settings
- [ ] Azure logs show calls to `smartloansbackend.azurewebsites.net`
- [ ] Azure logs do NOT show calls to `api.mercadolibre.com`

## Expected Logs After Fix

```
# Should see this (worker calling backend):
GET https://smartloansbackend.azurewebsites.net/ml/search?q=iphone&offset=0&limit=50

# Should NOT see this (direct ML call):
GET https://api.mercadolibre.com/sites/MLM/search?q=iphone
```

## If Still Getting 403

1. **Check backend logs** - The backend might be returning 403 if:
   - ML token is expired
   - Backend not forwarding headers correctly
   - Backend not using browser-like headers

2. **Verify environment variables:**
   ```bash
   az functionapp config appsettings list --name smartloans-workers
   ```

3. **Test backend directly:**
   ```bash
   curl "https://smartloansbackend.azurewebsites.net/ml/search?q=iphone"
   ```

## Files Modified

1. `/shared/ml_api.py` - Route through backend proxy
2. `/mlSearchWorker/main.py` - Use real ml_search() call
3. `/403_FIX_DOCUMENTATION.md` - This documentation

