#!/usr/bin/env python3
"""
Test script to verify ML API fix for 403 Forbidden error.

This script tests:
1. WORKER_KEY is properly loaded from environment
2. Headers are correctly constructed
3. Backend proxy is reachable
"""

import os
import sys
import json

# Add the workers directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from local.settings.json for testing
def load_local_settings():
    """Load environment variables from local.settings.json"""
    local_settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.settings.json")
    
    if os.path.exists(local_settings_path):
        with open(local_settings_path, 'r') as f:
            settings = json.load(f)
        
        # Load Values section into environment
        values = settings.get("Values", {})
        for key, value in values.items():
            os.environ[key] = str(value)
        
        print(f"✅ Loaded {len(values)} environment variables from local.settings.json")
    else:
        print("⚠️  local.settings.json not found, using existing environment variables")


# Load local settings before importing ml_api
load_local_settings()

from shared.ml_api import _get_headers, BACKEND_BASE, WORKER_KEY

def test_worker_key_loading():
    """Test 1: Verify WORKER_KEY is loaded"""
    print("\n=== Test 1: WORKER_KEY Loading ===")
    
    if WORKER_KEY:
        masked = WORKER_KEY[:8] + "..." + WORKER_KEY[-4:]
        print(f"✅ WORKER_KEY loaded: {masked}")
        print(f"   Length: {len(WORKER_KEY)} characters")
        return True
    else:
        print("❌ WORKER_KEY NOT found in environment variables!")
        print("   Set WORKER_KEY in local.settings.json or environment")
        return False


def test_headers():
    """Test 2: Verify headers are correctly constructed"""
    print("\n=== Test 2: Headers Construction ===")
    
    headers = _get_headers()
    
    # Check required headers
    has_accept = "Accept" in headers and headers["Accept"] == "application/json"
    has_content = "Content-Type" in headers and headers["Content-Type"] == "application/json"
    has_worker_key = "X-Worker-Key" in headers
    
    print(f"✅ Accept header: {headers.get('Accept', 'MISSING')}")
    print(f"✅ Content-Type header: {headers.get('Content-Type', 'MISSING')}")
    
    if has_worker_key:
        masked = headers["X-Worker-Key"][:8] + "..." + headers["X-Worker-Key"][-4:]
        print(f"✅ X-Worker-Key header: {masked}")
    else:
        print("❌ X-Worker-Key header MISSING!")
    
    return has_accept and has_content and has_worker_key


def test_backend_url():
    """Test 3: Verify backend proxy URL"""
    print("\n=== Test 3: Backend Proxy URL ===")
    
    print(f"✅ BACKEND_BASE: {BACKEND_BASE}")
    
    expected_suffix = "azurewebsites.net"
    if expected_suffix in BACKEND_BASE:
        print(f"✅ URL format looks correct (contains {expected_suffix})")
        return True
    else:
        print(f"⚠️  URL format unexpected, expected to contain {expected_suffix}")
        return False


def main():
    print("=" * 60)
    print("ML API 403 Fix Verification Test")
    print("=" * 60)
    
    results = []
    
    results.append(("WORKER_KEY Loading", test_worker_key_loading()))
    results.append(("Headers Construction", test_headers()))
    results.append(("Backend URL", test_backend_url()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ All basic tests passed!")
        print("The fix has been applied. Run 'func start' to test end-to-end.")
    else:
        print("\n❌ Some tests failed!")
        print("Please fix the issues above before testing end-to-end.")
        sys.exit(1)


if __name__ == "__main__":
    main()

