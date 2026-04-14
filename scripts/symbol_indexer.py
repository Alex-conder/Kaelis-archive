#!/usr/bin/env python3
"""
Kaelis v2.0 - 动态符号索引器 (Symbol Indexer)
功能: 构建代码符号表供幻觉检测使用

设计原则:
- 增量更新，避免全量重建
- 多语言支持 (Python, YAML/JSON)
- 快速查询，支持前缀匹配

作者: Kaelis v2.0
版本: 2.0.0
"""

import os
import sys
import ast
import json
import yaml
import hashlib
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, asdict


# 路径配置
SYMBOL_DIR = Path(".kaelis/symbols")
SYMBOL_FILE = SYMBOL_DIR / "symbols.json"
SYMBOL_META_FILE = SYMBOL_DIR / "meta.json"

# 默认监视路径
DEFAULT_WATCH_PATHS = [
    "api/**/*.py",
    "agent/**/*.py",
    "core/**/*.py",
    "scripts/**/*.py",
    "config/**/*.yaml",
    "config/**/*.yml",
    "config/**/*.json",
]


@dataclass
class SymbolIndex:
    """符号索引"""
    functions: Dict[str, List[str]]  # module -> [function_names]
    classes: Dict[str, List[str]]    # module -> [class_names]
    routes: List[str]                # [route_paths]
    config_keys: List[str]           # [config_key_paths]
    file_hashes: Dict[str, str]      # filepath -> hash (用于增量更新)
    last_updated: str
    
    def to_dict(self) -> dict:
        return {
            'functions': self.functions,
            'classes': self.classes,
            'routes': self.routes,
            'config_keys': self.config_keys,
            'file_hashes': self.file_hashes,
            'last_updated': self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SymbolIndex':
        return cls(
            functions=data.get('functions', {}),
            classes=data.get('classes', {}),
            routes=data.get('routes', []),
            config_keys=data.get('config_keys', []),
            file_hashes=data.get('file_hashes', {}),
            last_updated=data.get('last_updated', datetime.now().isoformat())
        )


class SymbolIndexer:
    """
    符号索引器
    
    动态构建项目代码符号表，支持增量更新。
    """
    
    def __init__(self, watch_paths: List[str] = None):
        self.watch_paths = watch_paths or DEFAULT_WATCH_PATHS
        self.index = SymbolIndex(
            functions={},
            classes={},
            routes=[],
            config_keys=[],
            file_hashes={},
            last_updated=datetime.now().isoformat()
        )
        
        # 确保目录存在
        SYMBOL_DIR.mkdir(parents=True, exist_ok=True)
    
    def load_existing_index(self) -> bool:
        """加载现有索引"""
        if SYMBOL_FILE.exists():
            try:
                with open(SYMBOL_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.index = SymbolIndex.from_dict(data)
                return True
            except Exception as e:
                print(f"[WARN] Failed to load existing index: {e}")
        return False
    
    def get_file_hash(self, filepath: Path) -> str:
        """计算文件哈希"""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def is_file_changed(self, filepath: Path) -> bool:
        """检查文件是否变更"""
        current_hash = self.get_file_hash(filepath)
        stored_hash = self.index.file_hashes.get(str(filepath))
        return current_hash != stored_hash
    
    def index_python_file(self, filepath: Path) -> bool:
        """索引 Python 文件"""
        try:
            content = filepath.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            try:
                module = str(filepath.relative_to(Path.cwd()))
            except ValueError:
                # 如果文件不在当前工作目录下，使用绝对路径
                module = str(filepath)
            
            # 提取函数和类
            functions = []
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
            
            # 提取路由
            routes = []
            import re
            for match in re.finditer(r'@\w+\.route\s*\(\s*[\'"]([^\'"]+)[\'"]', content):
                routes.append(match.group(1))
            
            # 更新索引
            if functions:
                self.index.functions[module] = functions
            if classes:
                self.index.classes[module] = classes
            if routes:
                self.index.routes.extend(routes)
            
            # 更新哈希
            self.index.file_hashes[str(filepath)] = self.get_file_hash(filepath)
            
            return True
            
        except Exception as e:
            print(f"[WARN] Failed to index {filepath}: {e}")
            return False
    
    def index_yaml_file(self, filepath: Path) -> bool:
        """索引 YAML 文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            keys = self._extract_all_keys(data)
            
            # 添加配置键
            for key in keys:
                if key not in self.index.config_keys:
                    self.index.config_keys.append(key)
            
            # 更新哈希
            self.index.file_hashes[str(filepath)] = self.get_file_hash(filepath)
            
            return True
            
        except Exception as e:
            print(f"[WARN] Failed to index {filepath}: {e}")
            return False
    
    def index_json_file(self, filepath: Path) -> bool:
        """索引 JSON 文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            keys = self._extract_all_keys(data)
            
            for key in keys:
                if key not in self.index.config_keys:
                    self.index.config_keys.append(key)
            
            self.index.file_hashes[str(filepath)] = self.get_file_hash(filepath)
            
            return True
            
        except Exception as e:
            print(f"[WARN] Failed to index {filepath}: {e}")
            return False
    
    def _extract_all_keys(self, data, prefix: str = "") -> List[str]:
        """递归提取所有键"""
        keys = []
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                keys.append(full_key)
                keys.extend(self._extract_all_keys(value, full_key))
        return keys
    
    def get_files_to_index(self) -> List[Path]:
        """获取需要索引的文件列表"""
        files = []
        
        for pattern in self.watch_paths:
            # 标准化路径分隔符
            pattern = pattern.replace('/', os.sep)
            
            # 支持 /**/ 递归匹配
            if '**' in pattern:
                base_path = pattern.split('**')[0].rstrip(os.sep)
                suffix = pattern.split('**')[1].replace(os.sep, '')
                
                base = Path(base_path) if base_path else Path('.')
                if base.exists():
                    for f in base.rglob(f"*{suffix}"):
                        if f.is_file():
                            files.append(f)
            else:
                # 简单 glob 匹配
                for f in Path('.').glob(pattern):
                    if f.is_file():
                        files.append(f)
        
        return sorted(set(files))
    
    def run_full_index(self):
        """运行全量索引"""
        print("=" * 60)
        print("Kaelis Symbol Indexer v2.0")
        print("=" * 60)
        
        files = self.get_files_to_index()
        print(f"\n[OK] Found {len(files)} files to index")
        
        indexed = 0
        failed = 0
        
        for filepath in files:
            suffix = filepath.suffix.lower()
            
            if suffix == '.py':
                if self.index_python_file(filepath):
                    indexed += 1
                else:
                    failed += 1
            elif suffix in ('.yaml', '.yml'):
                if self.index_yaml_file(filepath):
                    indexed += 1
                else:
                    failed += 1
            elif suffix == '.json':
                if self.index_json_file(filepath):
                    indexed += 1
                else:
                    failed += 1
        
        # 更新元数据
        self.index.last_updated = datetime.now().isoformat()
        
        # 保存索引
        self.save_index()
        
        print(f"\n[OK] Indexed: {indexed}, Failed: {failed}")
        print(f"[OK] Total symbols:")
        print(f"       Functions: {sum(len(v) for v in self.index.functions.values())}")
        print(f"       Classes: {sum(len(v) for v in self.index.classes.values())}")
        print(f"       Routes: {len(self.index.routes)}")
        print(f"       Config keys: {len(self.index.config_keys)}")
        print(f"\n[OK] Index saved to: {SYMBOL_FILE}")
    
    def run_incremental(self):
        """运行增量索引"""
        print("=" * 60)
        print("Kaelis Symbol Indexer (Incremental)")
        print("=" * 60)
        
        # 加载现有索引
        if not self.load_existing_index():
            print("\n[INFO] No existing index, running full index...")
            return self.run_full_index()
        
        files = self.get_files_to_index()
        changed_files = [f for f in files if self.is_file_changed(f)]
        
        if not changed_files:
            print("\n[OK] No files changed, index is up to date")
            return
        
        print(f"\n[OK] Found {len(changed_files)} changed files")
        
        indexed = 0
        for filepath in changed_files:
            suffix = filepath.suffix.lower()
            
            if suffix == '.py':
                if self.index_python_file(filepath):
                    indexed += 1
            elif suffix in ('.yaml', '.yml'):
                if self.index_yaml_file(filepath):
                    indexed += 1
            elif suffix == '.json':
                if self.index_json_file(filepath):
                    indexed += 1
        
        self.index.last_updated = datetime.now().isoformat()
        self.save_index()
        
        print(f"\n[OK] Incremental update complete: {indexed} files updated")
    
    def save_index(self):
        """保存索引到文件"""
        with open(SYMBOL_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.index.to_dict(), f, indent=2, ensure_ascii=False)
        
        # 同时保存元数据
        meta = {
            'last_updated': self.index.last_updated,
            'total_files': len(self.index.file_hashes),
            'total_functions': sum(len(v) for v in self.index.functions.values()),
            'total_classes': sum(len(v) for v in self.index.classes.values()),
            'total_routes': len(self.index.routes),
            'total_config_keys': len(self.index.config_keys)
        }
        with open(SYMBOL_META_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
    
    def query(self, symbol_type: str, pattern: str = None) -> List[str]:
        """查询符号"""
        if symbol_type == 'function':
            results = []
            for module, funcs in self.index.functions.items():
                for func in funcs:
                    full_name = f"{module}:{func}"
                    if pattern is None or pattern in full_name:
                        results.append(full_name)
            return results
        
        elif symbol_type == 'class':
            results = []
            for module, classes in self.index.classes.items():
                for cls in classes:
                    full_name = f"{module}:{cls}"
                    if pattern is None or pattern in full_name:
                        results.append(full_name)
            return results
        
        elif symbol_type == 'route':
            return [r for r in self.index.routes if pattern is None or pattern in r]
        
        elif symbol_type == 'config':
            return [k for k in self.index.config_keys if pattern is None or pattern in k]
        
        return []


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis Symbol Indexer - Build symbol table for hallucination detection"
    )
    parser.add_argument('--full', '-f', action='store_true',
                       help='Run full index (default: incremental)')
    parser.add_argument('--query', '-q', metavar='TYPE:PATTERN',
                       help='Query symbols (e.g., function:login, route:/api)')
    parser.add_argument('--watch', '-w', nargs='+',
                       help='Additional watch paths')
    
    args = parser.parse_args()
    
    watch_paths = args.watch or DEFAULT_WATCH_PATHS
    indexer = SymbolIndexer(watch_paths=watch_paths)
    
    if args.query:
        # 加载索引并查询
        if not indexer.load_existing_index():
            print("[ERROR] No index found, run indexer first")
            return 1
        
        parts = args.query.split(':', 1)
        symbol_type = parts[0]
        pattern = parts[1] if len(parts) > 1 else None
        
        results = indexer.query(symbol_type, pattern)
        print(f"Found {len(results)} symbols:")
        for r in results[:20]:  # 最多显示20个
            print(f"  - {r}")
        if len(results) > 20:
            print(f"  ... and {len(results) - 20} more")
    
    elif args.full:
        indexer.run_full_index()
    
    else:
        indexer.run_incremental()
    
    return 0


if __name__ == "__main__":
    exit(main())
