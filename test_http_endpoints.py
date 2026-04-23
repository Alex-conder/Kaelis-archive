#!/usr/bin/env python3
"""Quick HTTP endpoint smoke tests for backend."""
import requests, json, sys

base = "http://localhost:5000"

def health_check():
    try:
        r = requests.get(f"{base}/api/kg-flywheel/health", timeout=5)
        print("Server health:", r.status_code, r.json())
        return True
    except Exception as e:
        print("Server not running:", e)
        return False

def test_chat():
    print("\n=== Testing /api/kg-flywheel/chat ===")
    r = requests.post(f"{base}/api/kg-flywheel/chat", json={
        "message": "我叫王五，是一名Python开发者",
        "user_id": "test_user",
        "session_id": "test_session"
    }, timeout=30)
    print(f"Status: {r.status_code}")
    data = r.json()
    reply = data.get('reply', '')[:80]
    print(f"Reply: {reply.encode('ascii', 'replace').decode('ascii')}...")
    state = data.get('state', '')
    print(f"State: {state.encode('ascii', 'replace').decode('ascii')}")
    strategy = data.get('data', {}).get('strategy')
    print(f"Strategy: {strategy}")
    new_user_info = data.get('data', {}).get('new_user_info')
    print(f"New user info: {new_user_info}")
    assert r.status_code == 200
    assert data.get("state")
    assert data.get("data", {}).get("strategy")
    print("PASS")

def test_memory_search():
    print("\n=== Testing /api/memory/search ===")
    r = requests.post(f"{base}/api/memory/search", json={
        "layer": "L2",
        "query": "*",
        "top_k": 5
    }, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Results: {len(data.get('data', []))} memories")
    assert r.status_code == 200
    print("PASS")

def test_proactive_push():
    print("\n=== Testing /api/memory/proactive/push ===")
    r = requests.post(f"{base}/api/memory/proactive/push", json={
        "user_id": "test_user",
        "context": "Python programming"
    }, timeout=10)
    print(f"Status: {r.status_code}")
    assert r.status_code == 200
    print("PASS")

if __name__ == "__main__":
    if not health_check():
        print("\nSkipping HTTP tests (server not running)")
        sys.exit(0)
    
    try:
        test_chat()
        test_memory_search()
        test_proactive_push()
        print("\n========================================")
        print("All HTTP endpoint tests PASSED!")
        print("========================================")
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
