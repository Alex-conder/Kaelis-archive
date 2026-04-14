#!/usr/bin/env python3
"""
Supabase Connection Test Script
验证 Supabase 配置和数据库连接
"""

import os
import sys
from pathlib import Path

# 加载环境变量
env_file = Path('.env')
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_ANON_KEY', '')

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def print_result(test_name, success, details=""):
    status = "[PASS]" if success else "[FAIL]"
    print(f"  {status} - {test_name}")
    if details:
        print(f"       {details}")

def test_configuration():
    """测试配置是否正确"""
    print_header("TEST 1: Configuration Check")
    
    # 检查 URL
    url_ok = bool(SUPABASE_URL and 'supabase.co' in SUPABASE_URL)
    print_result("SUPABASE_URL configured", url_ok, 
                 f"URL: {SUPABASE_URL[:40]}..." if url_ok else "Missing or invalid")
    
    # 检查 Key
    key_ok = bool(SUPABASE_KEY and len(SUPABASE_KEY) > 20)
    print_result("SUPABASE_ANON_KEY configured", key_ok,
                 f"Key length: {len(SUPABASE_KEY)} chars" if key_ok else "Missing or too short")
    
    return url_ok and key_ok

def test_supabase_connection():
    """测试 Supabase 连接"""
    print_header("TEST 2: Supabase Connection")
    
    try:
        from supabase import create_client
        
        print("  [INFO] Connecting to Supabase...")
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 尝试获取会话信息（无需登录）
        print_result("Supabase client created", True)
        
        # 测试匿名访问（如果表允许RLS匿名读取）
        try:
            result = client.table('workflows').select('count', count='exact').limit(0).execute()
            count = result.count if hasattr(result, 'count') else 0
            print_result("Database accessible", True, "Workflows table exists")
        except Exception as e:
            error_msg = str(e)
            if "does not exist" in error_msg:
                print_result("Database tables", False, "Tables not created yet. Run schema.sql in Supabase SQL Editor")
            elif "permission denied" in error_msg or "403" in error_msg:
                print_result("Database accessible", True, "RLS enabled (expected)")
            else:
                print_result("Database access", False, error_msg[:60])
        
        return True
        
    except ImportError:
        print_result("supabase-py installed", False, "pip install supabase")
        return False
    except Exception as e:
        print_result("Supabase connection", False, str(e)[:60])
        return False

def test_auth_api():
    """测试认证 API"""
    print_header("TEST 3: Authentication API")
    
    import urllib.request
    import urllib.error
    import json
    
    base_url = "http://localhost:5000"
    
    # 测试健康检查
    try:
        req = urllib.request.Request(f"{base_url}/api/auth/health")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            supabase_configured = data.get('supabase_configured', False)
            print_result("Auth API running", True, f"Supabase configured: {supabase_configured}")
    except Exception as e:
        print_result("Auth API health check", False, f"Is Flask running? {str(e)[:50]}")
        return False
    
    return True

def test_workflow_api():
    """测试工作流同步 API"""
    print_header("TEST 4: Workflow Sync API")
    
    import urllib.request
    import json
    
    base_url = "http://localhost:5000"
    
    # 测试健康检查
    try:
        req = urllib.request.Request(f"{base_url}/api/sync/health")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            status = data.get('status', 'unknown')
            supabase_status = data.get('supabase', 'disconnected')
            print_result("Sync API running", status == 'healthy', f"Supabase: {supabase_status}")
    except Exception as e:
        print_result("Sync API health check", False, f"Is Flask running? {str(e)[:50]}")
        return False
    
    return True

def test_frontend_env():
    """测试前端环境变量"""
    print_header("TEST 5: Frontend Environment")
    
    env_file = Path('web/frontend/.env.local')
    if not env_file.exists():
        print_result("Frontend .env.local exists", False, "File not found")
        return False
    
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_url = 'VITE_SUPABASE_URL' in content and 'supabase.co' in content
    has_key = 'VITE_SUPABASE_ANON_KEY' in content and len(content) > 100
    
    print_result("VITE_SUPABASE_URL configured", has_url)
    print_result("VITE_SUPABASE_ANON_KEY configured", has_key)
    
    return has_url and has_key

def test_database_schema():
    """测试数据库 Schema 是否已创建"""
    print_header("TEST 6: Database Schema")
    
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        tables_to_check = ['profiles', 'workflows', 'sync_logs']
        all_exist = True
        
        for table in tables_to_check:
            try:
                # 尝试查询表结构
                result = client.table(table).select('*').limit(1).execute()
                print_result(f"Table '{table}' exists", True)
            except Exception as e:
                error_msg = str(e)
                if "does not exist" in error_msg:
                    print_result(f"Table '{table}' exists", False, "Table not found")
                    all_exist = False
                elif "permission denied" in error_msg:
                    print_result(f"Table '{table}' exists", True, "RLS protected (OK)")
                else:
                    print_result(f"Table '{table}'", False, error_msg[:50])
                    all_exist = False
        
        if not all_exist:
            print("\n  [WARN] Some tables are missing!")
            print("  [INFO] Please run config/supabase/schema.sql in Supabase SQL Editor")
        
        return all_exist
        
    except Exception as e:
        print_result("Schema check", False, str(e)[:60])
        return False

def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("  Kaelis Supabase Connection Test")
    print("="*60)
    
    results = []
    
    # 运行所有测试
    results.append(("Configuration", test_configuration()))
    results.append(("Supabase Connection", test_supabase_connection()))
    results.append(("Auth API", test_auth_api()))
    results.append(("Sync API", test_workflow_api()))
    results.append(("Frontend Environment", test_frontend_env()))
    results.append(("Database Schema", test_database_schema()))
    
    # 汇总
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} - {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  [SUCCESS] All tests passed! Supabase is ready to use.")
        return 0
    else:
        print("\n  [WARN] Some tests failed. Please check the errors above.")
        print("\n  Troubleshooting:")
        print("    1. Ensure .env file has correct Supabase credentials")
        print("    2. Run 'python launch.py' to start the Flask server")
        print("    3. Execute config/supabase/schema.sql in Supabase SQL Editor")
        return 1

if __name__ == '__main__':
    sys.exit(main())
