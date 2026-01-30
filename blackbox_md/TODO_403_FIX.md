# TODO: Fix 403 Error - Route ML API Calls Through Backend Proxy

## Problem
Workers are calling Mercado Libre directly (`https://api.mercadolibre.com`) instead of going through the backend proxy (`https://smartloansbackend.azurewebsites.net/ml/search`), causing 403 errors from ML's WAF/PolicyAgent.

## Root Cause
In `shared/ml_api.py`:
- `ml_search()` uses `ML_API_BASE` which points to `https://api.mercadolibre.com`
- `ml_item()` also uses `ML_API_BASE` for direct ML calls

## Solution
Update `shared/ml_api.py` to use the backend proxy for all ML API calls.

## Changes Required

### 1. Update `shared/ml_api.py`

**Current (problematic):**
```python
ML_API_BASE = "https://api.mercadolibre.com"

def ml_search(q: str, *, category: str | None, seller_id: str | None, offset: int, limit: int):
    site_id = os.getenv("ML_SITE_ID", "MLM")
    url = f"{ML_API_BASE}/sites/{site_id}/search"  # Direct ML call - BAD!
```

**Fixed:**
```python
# Backend proxy URL (from environment)
BACKEND_BASE = os.getenv("SMARTLOANS_BACKEND_URL", "https://smartloansbackend.azurewebsites.net")

def ml_search(q: str, *, category: str | None, seller_id: str | None, offset: int, limit: int):
    url = f"{BACKEND_BASE}/ml/search"  # Proxy through backend - GOOD!
```

### 2. Update `ml_item()` function similarly
```python
def ml_item(item_id: str):
    url = f"{BACKEND_BASE}/ml/item/{item_id}"  # Proxy through backend
```

### 3. Remove 403 token refresh logic from ml_api.py
Since the backend handles auth, we don't need token refresh in workers anymore.

## Files to Edit
- `shared/ml_api.py` - Main file requiring changes

## After Fix
- Workers call: `https://smartloansbackend.azurewebsites.net/ml/search`
- Backend injects ML auth headers and forwards to ML
- Azure logs should show backend URLs, not direct ML URLs

## Deployment Steps
1. Update `shared/ml_api.py` with the fix
2. Deploy to Azure Function App
3. Verify in Azure logs that calls go through backend proxy

