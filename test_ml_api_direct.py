#!/usr/bin/env python3
"""
Direct test script to debug ML API 403 error.
This script makes a direct HTTP request and prints all headers sent.
"""

import os
import sys
import json
import requests

# Load environment variables from local.settings.json
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

# Get WORKER_KEY from environment
WORKER_KEY = os.getenv("WORKER_KEY", "")
BACKEND_BASE = os.getenv("SMARTLOANS_BACKEND_URL", "https://smartloansbackend.azurewebsites.net")

print("\n" + "=" * 60)
print("Direct ML API Test")
print("=" * 60)

# Build headers
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Worker-Key": WORKER_KEY,
}

print(f"\n📡 Backend URL: {BACKEND_BASE}")
print(f"🔑 WORKER_KEY: {WORKER_KEY[:8]}...{WORKER_KEY[-4]}")
print(f"\n📋 Headers being sent:")
for key, value in headers.items():
    if key == "X-Worker-Key":
        masked = value[:8] + "..." + value[-4:]
        print(f"   {key}: {masked}")
    else:
        print(f"   {key}: {value}")

# Make the request
url = f"{BACKEND_BASE}/ml/search"
params = {"q": "iphone", "offset": 0, "limit": 10}

print(f"\n🌐 Making request: GET {url}")
print(f"   Params: {params}")

try:
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    
    print(f"\n📊 Response Status: {resp.status_code}")
    print(f"   Headers: {dict(resp.headers)}")
    
    if resp.status_code == 200:
        print("\n✅ SUCCESS! Request worked.")
        data = resp.json()
        print(f"   Results count: {len(data.get('results', []))}")
    else:
        print(f"\n❌ FAILED with status {resp.status_code}")
        print(f"   Response body: {resp.text[:500]}")
        
        # Check if the error might be from ML or the backend
        if "smartloansbackend" in url:
            print("\n🔍 This 403 is coming from the BACKEND, not from MercadoLibre.")
            print("   Possible causes:")
            print("   1. WORKER_KEY in backend doesn't match this WORKER_KEY")
            print("   2. Backend's require_worker_key function is not properly configured")
            print("   3. Azure WAF is blocking the request")
            
except requests.exceptions.RequestException as e:
    print(f"\n❌ Request failed: {e}")
    print(f"   Type: {type(e).__name__}")

print("\n" + "=" * 60)

