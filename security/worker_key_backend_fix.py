"""
Security Module - Worker Key Validation (FIXED VERSION)

This version reads WORKER_KEY at request time to avoid timing issues
with environment variables being loaded after module import.
"""

import os
from fastapi import Header, HTTPException


def get_worker_key() -> str:
    """
    Get WORKER_KEY from environment at request time.
    This fixes timing issues where env vars aren't loaded at module import.
    """
    return os.getenv("WORKER_KEY", "")


def require_worker_key(x_worker_key: str | None = Header(default=None)):
    """
    FastAPI dependency to validate X-Worker-Key header.
    
    FIXED: Now reads WORKER_KEY at request time, not at module load time.
    This ensures the environment variable is properly loaded.
    
    Usage:
        @router.get("/search", dependencies=[Depends(require_worker_key)])
        def ml_search_proxy(...):
            ...
    
    Args:
        x_worker_key: Header value from X-Worker-Key header
        
    Raises:
        HTTPException: 403 if key is missing or invalid
    """
    worker_key = get_worker_key()
    
    if not worker_key:
        # Key not configured on server side - log warning but allow in development
        # In production, this should always be set
        return
    
    if x_worker_key != worker_key:
        raise HTTPException(status_code=403, detail="Forbidden")


# For testing purposes
def test_worker_key():
    """Test that WORKER_KEY is properly loaded"""
    key = get_worker_key()
    if key:
        masked = key[:8] + "..." + key[-4:]
        print(f"✅ WORKER_KEY loaded: {masked}")
        return True
    else:
        print("❌ WORKER_KEY not found!")
        return False


if __name__ == "__main__":
    test_worker_key()

