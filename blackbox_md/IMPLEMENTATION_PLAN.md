# Implementation Plan: mlSearchWorker + /ml/* Backend Pipeline

## Overview
Isolate the mlSearchWorker + backend /ml/* pipeline so:
- Worker calls ONLY backend (never directly calls ML)
- Backend validates requests via WORKER_KEY
- Backend handles ML auth/browser headers
- Proper error handling for retries

---

## Current State Analysis

### ✅ Already Done
- `shared/ml_api.py` - Routes through `BACKEND_BASE` 
- `mlSearchWorker/main.py` - Calls `ml_search()` properly
- `shared/retry.py` - Has proper backoff logic

### ❌ Missing Components
1. `security/worker_key.py` - Worker key validation dependency
2. `X-Worker-Key` header in `ml_api.py` calls
3. Backend route validation (may need to add to backend repo)

---

## Implementation Plan

### Step 1: Create Security Module
**File:** `security/worker_key.py`

```python
import os
from fastapi import Header, HTTPException

WORKER_KEY = os.getenv("WORKER_KEY", "")

def require_worker_key(x_worker_key: str | None = Header(default=None)):
    if not WORKER_KEY or x_worker_key != WORKER_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
```

### Step 2: Update Worker to Send X-Worker-Key
**File:** `shared/ml_api.py`

- Add `X-Worker-Key` header construction
- Read WORKER_KEY from environment
- Include header in all backend calls

### Step 3: Add Backend Routes (if needed in workers repo)
**File:** `routes_ml_proxy.py` or integrate into `function_app.py`

- Add `/ml/search` route with `Depends(require_worker_key)`
- Use browser-like headers
- Forward to ML API with auth
- Return proper JSONResponse with status code

### Step 4: Test End-to-End
- Verify worker sends `X-Worker-Key`
- Verify backend validates key
- Verify proper error handling

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `security/worker_key.py` | Create | Worker key validation dependency |
| `shared/ml_api.py` | Modify | Add X-Worker-Key header |
| `routes_ml_proxy.py` | Create | Backend ML proxy routes (if in workers repo) |

---

## Environment Variables Required

| Variable | Value | Purpose |
|----------|-------|---------|
| `WORKER_KEY` | `smartloans-worker-ml-2026-secret` | Shared secret for worker→backend auth |
| `SMARTLOANS_BACKEND_URL` | `https://smartloansbackend.azurewebsites.net` | Backend proxy endpoint |

---

## Testing Steps

1. **Test Backend Route Directly:**
```bash
curl -i "https://smartloansbackend.azurewebsites.net/ml/search?q=iphone" \
  -H "X-Worker-Key: smartloans-worker-ml-2026-secret"
```

2. **Expected Responses:**
- `200` with ML results (success)
- `403` if WORKER_KEY mismatch
- `403/401` from ML if token/headers issue

---

## Follow-up Steps After Implementation

1. Set `WORKER_KEY` in Azure Function App settings
2. Set `WORKER_KEY` in Azure Backend App settings
3. Deploy updated workers
4. Monitor Azure logs for proper routing
5. Verify no direct ML API calls in worker logs

---

## Success Criteria

- ✅ Worker calls `smartloansbackend.azurewebsites.net/ml/search`
- ✅ Worker sends `X-Worker-Key` header
- ✅ Backend validates `X-Worker-Key` before proxying to ML
- ✅ No direct calls to `api.mercadolibre.com` from workers
- ✅ Proper retry/backoff on ML errors

