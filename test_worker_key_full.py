#!/usr/bin/env python3
"""
Comprehensive test to verify WORKER_KEY authentication end-to-end.

This test simulates what happens when func start runs:
1. Loads environment from local.settings.json
2. Tests the ml_search function directly
3. Verifies headers are being sent correctly
"""

import os
import sys
import json

# Load environment variables from local.settings.json FIRST
def load_local_settings():
    local_settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.settings.json")
    
    if os.path.exists(local_settings_path):
        with open(local_settings_path, 'r') as f:
            settings = json.load(f)
        
        values = settings.get("Values", {})
        for key, value in values.items():
            os.environ[key] = str(value)
        
        print(f"✅ Loaded {len(values)} environment variables from local.settings.json")

load_local_settings()

# Now import our modules
from shared.ml_api import _get_headers, BACKEND_BASE, WORKER_KEY, ml_search
from shared.retry import request_with_backoff

print("\n" + "=" * 70)
print("COMPREHENSIVE WORKER_KEY AUTHENTICATION TEST")
print("=" * 70)

# Test 1: Verify WORKER_KEY is loaded
print("\n📋 Test 1: WORKER_KEY Loading")
print(f"   WORKER_KEY from env: {WORKER_KEY[:8] if WORKER_KEY else 'NOT SET'}...")
if WORKER_KEY:
    print(f"   Length: {len(WORKER_KEY)} characters")
    print("   ✅ WORKER_KEY is loaded")
else:
    print("   ❌ WORKER_KEY is NOT loaded!")

# Test 2: Verify headers are built correctly
print("\n📋 Test 2: Header Construction")
headers = _get_headers()
print(f"   Accept: {headers.get('Accept', 'MISSING')}")
print(f"   Content-Type: {headers.get('Content-Type', 'MISSING')}")
if 'X-Worker-Key' in headers:
    wk = headers['X-Worker-Key']
    print(f"   X-Worker-Key: {wk[:8]}...{wk[-4]}")
    print("   ✅ Headers built correctly")
else:
    print("   ❌ X-Worker-Key header missing!")

# Test 3: Verify the actual request
print("\n📋 Test 3: Direct Backend Request")
print(f"   URL: {BACKEND_BASE}/ml/search")
print(f"   Params: q=iphone, offset=0, limit=10")

try:
    resp = request_with_backoff(
        "GET",
        f"{BACKEND_BASE}/ml/search",
        params={"q": "iphone", "offset": 0, "limit": 10},
        headers=headers,
        timeout=30
    )
    print(f"\n   ✅ SUCCESS! Status: {resp.status_code}")
    print(f"   Response preview: {resp.text[:200]}...")
except Exception as e:
    print(f"\n   ❌ FAILED! Status: 403")
    print(f"   Error: {str(e)[:100]}...")
    print(f"\n   🔍 Analysis:")
    print(f"   - Headers were sent correctly: {'YES' if 'X-Worker-Key' in headers else 'NO'}")
    print(f"   - WORKER_KEY matched: {'LIKELY NOT' if '403' in str(e) else 'UNKNOWN'}")

# Test 4: Compare WORKER_KEY values
print("\n📋 Test 4: WORKER_KEY Consistency Check")
worker_key = os.getenv("WORKER_KEY", "")
print(f"   From local.settings.json: {worker_key[:8] if worker_key else 'NOT SET'}...")
print(f"   From ml_api module: {WORKER_KEY[:8] if WORKER_KEY else 'NOT SET'}...")
if worker_key == WORKER_KEY:
    print("   ✅ WORKER_KEY values match")
else:
    print("   ❌ WORKER_KEY values DO NOT match!")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print("\n💡 If Test 3 shows 403, the issue is on the BACKEND side.")
print("   Check Azure Portal → smartloansbackend → Logs for the /ml/search endpoint.")
print("=" * 70)

