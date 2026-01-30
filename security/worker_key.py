"""
Security Module - Worker Key Validation

Validates X-Worker-Key header for worker-to-backend authentication.
This ensures only authorized workers can access backend ML proxy routes.
"""

import os
from fastapi import Header, HTTPException

# Worker key for worker-to-backend authentication
# Set via WORKER_KEY environment variable
WORKER_KEY = os.getenv("WORKER_KEY", "")


def require_worker_key(x_worker_key: str | None = Header(default=None)):
    """
    FastAPI dependency to validate X-Worker-Key header.
    
    Usage:
        @router.get("/search", dependencies=[Depends(require_worker_key)])
        def ml_search_proxy(...):
            ...
    
    Args:
        x_worker_key: Header value from X-Worker-Key header
        
    Raises:
        HTTPException: 403 if key is missing or invalid
    """
    if not WORKER_KEY:
        # Key not configured on server side - log warning but allow in development
        # In production, this should always be set
        pass
    
    if x_worker_key != WORKER_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

