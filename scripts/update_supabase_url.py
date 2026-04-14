#!/usr/bin/env python3
"""
Update Supabase URL in configuration files
"""

import re
from pathlib import Path

def update_env_files(url: str):
    """Update all .env files with new URL"""
    
    files_to_update = [
        Path('.env'),
        Path('web/frontend/.env.local')
    ]
    
    for env_file in files_to_update:
        if not env_file.exists():
            print(f"[WARN] File not found: {env_file}")
            continue
        
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace SUPABASE_URL or VITE_SUPABASE_URL
        updated = re.sub(
            r'(SUPABASE_URL|VITE_SUPABASE_URL)=https?://[^\s]+',
            f'\\1={url}',
            content
        )
        
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(updated)
        
        print(f"[OK] Updated: {env_file}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_supabase_url.py <supabase_url>")
        print("Example: python scripts/update_supabase_url.py https://abc123.supabase.co")
        sys.exit(1)
    
    url = sys.argv[1]
    update_env_files(url)
    print("\n[OK] Configuration updated. Run 'python scripts/test_supabase.py' to verify.")
