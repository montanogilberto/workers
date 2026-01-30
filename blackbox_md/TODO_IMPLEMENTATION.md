# mlSearchWorker + /ml/* Pipeline Implementation

## ✅ Completed Files

### Workers Side
| File | Purpose |
|------|---------|
| `security/worker_key.py` | FastAPI dependency for X-Worker-Key validation |
| `shared/ml_api.py` | Worker sends X-Worker-Key header to backend |

### Backend Side (routes_ml_proxy.py)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ml/search` | GET | Proxy to ML sites search |
| `/ml/items/{item_id}` | GET | Proxy to ML item details |
| `/ml/whoami` | GET | Debug endpoint - verify token validity |
| `/ml/public_ping` | GET | Test public ML API connectivity |

## Architecture
```
Azure Functions Workers
    │
    ├── mlSearchWorker/main.py
    │       └── try_ml_public_search()
    │               └── ml_api.ml_search()
    │                       │
    │                       ▼
    │               X-Worker-Key header
    │                       │
    │                       ▼
    └── SMARTLOANS_BACKEND_URL/ml/search
            │
            ▼
    Backend (smartloansbackend.azurewebsites.net)
            │
            ├── Validates X-Worker-Key
            ├── Gets ML token from DB (get_valid_access_token)
            ├── Adds browser headers (User-Agent, Referer, Origin)
            ├── Forwards to ML with Bearer token
            └── Returns JSONResponse with status code
                    │
                    ▼
            MercadoLibre API
```

## Key Features
- **Token Refresh**: If ML returns 401 invalid_token, backend refreshes and retries once
- **403 Fallback**: If 403 WITH token, retries WITHOUT token (public endpoint fallback)
- **Safe Logging**: Tokens masked in logs (first 6 + last 3 chars only)
- **Request IDs**: Each request gets unique ID for tracing

## Environment Variables
| Variable | Workers | Backend | Purpose |
|----------|---------|---------|---------|
| `WORKER_KEY` | ✅ | ✅ | Worker-to-backend auth |
| `SMARTLOANS_BACKEND_URL` | ✅ | - | Workers know where backend is |
| `ML_ACCESS_TOKEN` | - | ✅ | Used by backend for ML auth |
| `ML_REFRESH_TOKEN` | - | ✅ | Used by backend to refresh tokens |

