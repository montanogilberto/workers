# TODO_403_FIX.md - Progress Tracker

## Status: 🔴 ROOT CAUSE - BACKEND WORKER_KEY VALIDATION TIMING ISSUE

## CONFIRMED: Worker is sending correct WORKER_KEY

From logs:
```
[ML_API] X-Worker-Key header: 171fe53e...33ed
```

## Changes Made to Worker (COMPLETED)

✅ **shared/ml_api.py** - Enhanced logging:
- WORKER_KEY loading verification
- X-Worker-Key header logging in all requests
- Request/response status logging

✅ **Test scripts created:**
- `test_ml_api_fix.py` - Basic verification
- `test_ml_api_direct.py` - Direct HTTP test
- `test_worker_key_full.py` - Comprehensive test
- `security/worker_key_backend_fix.py` - Backend code fix suggestion

## 🔴 THE 403 IS COMING FROM THE BACKEND

The backend is rejecting the request even though WORKER_KEY matches.

### Possible Causes:

1. **Environment variable timing issue** - `os.getenv("WORKER_KEY")` returns empty at module import time but is set later

2. **Backend code reads WORKER_KEY at import time** - The `security/worker_key.py` file in the backend reads WORKER_KEY when the module is imported, before the environment variable is loaded

### Solution for Backend:

**Option A:** Update the backend's `security/worker_key.py` to read WORKER_KEY at **request time** (not at import time):

```python
# WRONG - reads at import time
WORKER_KEY = os.getenv("WORKER_KEY", "")  # Might be empty!

def require_worker_key(x_worker_key: str | None = Header(default=None)):
    if x_worker_key != WORKER_KEY:  # Compares with empty string!
        raise HTTPException(status_code=403, detail="Forbidden")
```

**Option B:** Restart the backend after setting WORKER_KEY in Azure Portal

## 🚨 ACTION REQUIRED ON AZURE BACKEND

1. Go to **Azure Portal** → **App Services** → **smartloansbackend**
2. Go to **Configuration** → **Environment variables**
3. Add `WORKER_KEY`: `171fe53e88a19c2e388906c9ad0a5a561400114d5a473f1ab787c4f8668c33ed`
4. **RESTART the app**
5. Check **Log Stream** for any errors

## Verification After Fix

```bash
source .venv/bin/activate && python3 test_ml_api_direct.py
```

Expected: `📊 Response Status: 200`

