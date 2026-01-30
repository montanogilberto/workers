"""
MercadoLibre OAuth Authentication Module

Handles access token refresh and management for ML API requests.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

ML_API_BASE = "https://api.mercadolibre.com"


def get_ml_credentials() -> dict:
    """Get ML OAuth credentials from environment variables."""
    return {
        "client_id": os.getenv("ML_CLIENT_ID"),
        "client_secret": os.getenv("ML_CLIENT_SECRET"),
        "refresh_token": os.getenv("ML_REFRESH_TOKEN"),
        "access_token": os.getenv("ML_ACCESS_TOKEN"),
    }


def refresh_access_token() -> tuple[bool, str | None]:
    """
    Refresh the ML access token using the refresh token.
    
    Returns:
        tuple: (success: bool, new_access_token: str | None)
    """
    creds = get_ml_credentials()
    
    if not all([creds["client_id"], creds["client_secret"], creds["refresh_token"]]):
        logger.error("Missing ML credentials for token refresh")
        return False, None
    
    url = f"{ML_API_BASE}/oauth/token"
    
    payload = {
        "grant_type": "refresh_token",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    try:
        logger.info("Attempting to refresh ML access token...")
        resp = requests.post(url, data=payload, headers=headers, timeout=25)
        
        if resp.status_code == 200:
            data = resp.json()
            new_access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token")
            
            logger.info("Token refresh successful!")
            
            # Optionally save new tokens (in production, update env or secure storage)
            if new_refresh_token:
                logger.info("New refresh token received")
            
            return True, new_access_token
        else:
            logger.error(f"Token refresh failed: {resp.status_code} - {resp.text}")
            return False, None
            
    except Exception as e:
        logger.error(f"Token refresh exception: {e}")
        return False, None


def set_access_token_env(token: str) -> None:
    """Set the access token in the current process environment."""
    os.environ["ML_ACCESS_TOKEN"] = token
    logger.info("ML_ACCESS_TOKEN updated in environment")


def refresh_and_update_token() -> tuple[bool, str | None]:
    """
    Refresh token and update environment.
    
    Returns:
        tuple: (success: bool, new_token: str | None)
    """
    success, new_token = refresh_access_token()
    
    if success and new_token:
        set_access_token_env(new_token)
        return True, new_token
    
    return False, None

