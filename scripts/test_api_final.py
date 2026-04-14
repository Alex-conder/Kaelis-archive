#!/usr/bin/env python3
"""
Final API Test with Environment Setup
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

# Load environment variables from .env
env_file = Path('.env')
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

BASE_URL = "http://localhost:5000"

def test_endpoint(path, expected_status=200):
    """Test a single endpoint"""
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode('utf-8'))
            return True, data
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)[:50]

def main():
    print("=" * 60)
    print("Kaelis API Final Test")
    print("=" * 60)
    
    tests = [
        ("/", "Root API"),
        ("/api/auth/health", "Auth Health"),
        ("/api/sync/health", "Sync Health"),
        ("/api/ai/health", "AI Native Health"),
    ]
    
    passed = 0
    failed = 0
    
    for path, name in tests:
        ok, result = test_endpoint(path)
        if ok:
            print(f"[PASS] {name}: {json.dumps(result)[:60]}...")
            passed += 1
        else:
            print(f"[FAIL] {name}: {result}")
            failed += 1
    
    print("=" * 60)
    print(f"Result: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n[SUCCESS] All API endpoints are working!")
        print("\nNext steps:")
        print("1. Ensure Supabase tables are created (run quick_setup.sql)")
        print("2. Start frontend: cd web/frontend && npm run dev")
        print("3. Open http://localhost:5173 and test login/register")
    else:
        print("\n[ERROR] Some endpoints failed.")
        print("Make sure Flask server is running: python launch.py")
    
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
