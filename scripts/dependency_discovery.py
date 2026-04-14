#!/usr/bin/env python3
"""
Dependency Discovery Engine for Kaelis

通过 AST 静态分析自动发现模块间依赖关系，实现真正的"零配置"联动修正。

突破：依赖图谱静态化 → 动态自动发现

Usage:
    python scripts/dependency_discovery.py
    python scripts/dependency_discovery.py --output .kaelis/auto_dependencies.json
    python scripts/dependency_discovery.py --watch  # 持续监控
"""

import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
CACHE_FILE = PROJECT_ROOT / ".kaelis" / "auto_dependencies.json"


@dataclass
class DependencyInfo:
    """依赖信息"""
    source: str                          # 源文件路径
    dependencies: Set[str] = field(default_factory=set)   # 依赖的模块/文件
    api_endpoints: Set[str] = field(default_factory=set)  # 调用的 API 端点
    env_variables: Set[str] = field(default_factory=set)  # 使用的环境变量
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "dependencies": sorted(list(self.dependencies)),
            "api_endpoints": sorted(list(self.api_endpoints)),
            "env_variables": sorted(list(self.env_variables)),
        }


class PythonDependencyAnalyzer:
    """Python AST 依赖分析器"""
    
    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = root
        self.dependencies: Dict[str, DependencyInfo] = {}
    
    def analyze_file(self, filepath: Path) -> Optional[DependencyInfo]:
        """
        分析单个 Python 文件的依赖
        
        Args:
            filepath: Python 文件路径
            
        Returns:
            DependencyInfo 或 None（如果解析失败）
        """
        try:
            content = filepath.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"  ⚠️  Syntax error in {filepath}: {e}")
            return None
        except Exception as e:
            print(f"  ⚠️  Error parsing {filepath}: {e}")
            return None
        
        rel_path = str(filepath.relative_to(self.root))
        info = DependencyInfo(source=rel_path)
        
        for node in ast.walk(tree):
            # 1. import xxx
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info.dependencies.add(f"py:{alias.name}")
            
            # 2. from xxx import yyy
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    info.dependencies.add(f"py:{node.module}")
                    
                    # 特殊处理：从 api.routes 导入 → 依赖 OpenAPI
                    if node.module.startswith("api.routes"):
                        info.dependencies.add("openapi:api")
            
            # 3. os.getenv("VAR") / os.environ.get("VAR")
            elif isinstance(node, ast.Call):
                self._extract_env_var(node, info)
            
            # 4. 直接访问 os.environ["VAR"]
            elif isinstance(node, ast.Subscript):
                self._extract_environ_access(node, info)
        
        return info
    
    def _extract_env_var(self, node: ast.Call, info: DependencyInfo):
        """提取 os.getenv 调用中的环境变量名"""
        if not isinstance(node.func, ast.Attribute):
            return
        
        # os.getenv(...) 或 os.environ.get(...)
        func_name = node.func.attr
        if func_name not in ['getenv', 'get']:
            return
        
        # 检查是否是 os 模块
        if isinstance(node.func.value, ast.Name):
            if node.func.value.id != 'os':
                return
        elif isinstance(node.func.value, ast.Attribute):
            # os.environ.get
            if (node.func.value.attr != 'environ' or 
                not isinstance(node.func.value.value, ast.Name) or
                node.func.value.value.id != 'os'):
                return
        else:
            return
        
        # 提取变量名
        if node.args and isinstance(node.args[0], ast.Constant):
            if isinstance(node.args[0].value, str):
                info.env_variables.add(node.args[0].value)
    
    def _extract_environ_access(self, node: ast.Subscript, info: DependencyInfo):
        """提取 os.environ["VAR"] 中的环境变量名"""
        if not isinstance(node.value, ast.Attribute):
            return
        
        if (node.value.attr == 'environ' and 
            isinstance(node.value.value, ast.Name) and
            node.value.value.id == 'os'):
            
            if isinstance(node.slice, ast.Constant):
                if isinstance(node.slice.value, str):
                    info.env_variables.add(node.slice.value)
    
    def scan_directory(self, pattern: str = "**/*.py") -> List[DependencyInfo]:
        """
        扫描目录中的所有 Python 文件
        
        Args:
            pattern: glob 模式
            
        Returns:
            DependencyInfo 列表
        """
        results = []
        exclude_patterns = [
            "__pycache__",
            ".venv",
            "venv",
            ".git",
            ".pytest_cache",
            "node_modules",
        ]
        
        for pyfile in self.root.glob(pattern):
            # 排除目录
            if any(p in str(pyfile) for p in exclude_patterns):
                continue
            
            info = self.analyze_file(pyfile)
            if info:
                results.append(info)
                self.dependencies[info.source] = info
        
        return results


class TypeScriptDependencyAnalyzer:
    """TypeScript 依赖分析器（基于正则）"""
    
    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = root
        self.dependencies: Dict[str, DependencyInfo] = {}
    
    def analyze_file(self, filepath: Path) -> Optional[DependencyInfo]:
        """
        分析单个 TypeScript 文件的依赖
        
        Args:
            filepath: TypeScript 文件路径
            
        Returns:
            DependencyInfo 或 None
        """
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ⚠️  Error reading {filepath}: {e}")
            return None
        
        rel_path = str(filepath.relative_to(self.root))
        info = DependencyInfo(source=rel_path)
        
        # 1. import ... from '...'
        for match in re.finditer(
            r'import\s+(?:(?:\{[^}]*\})|(?:[^,{}]*))\s+from\s+[\'"]([^\'"]+)[\'"]',
            content
        ):
            module = match.group(1)
            info.dependencies.add(f"ts:{module}")
            
            # 特殊处理 API 客户端导入
            if "api/schema" in module or "api/client" in module:
                info.dependencies.add("openapi:api")
        
        # 2. fetch('/api/...') 或 fetch("/api/...")
        for match in re.finditer(
            r'fetch\s*\(\s*[\'"]([^\'"]+)[\'"]',
            content
        ):
            url = match.group(1)
            if url.startswith('/api/'):
                info.api_endpoints.add(url)
                info.dependencies.add("openapi:api")
        
        # 3. axios.get('/api/...')
        for match in re.finditer(
            r'(?:axios|api)\.(?:get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            content
        ):
            url = match.group(1)
            if url.startswith('/api/'):
                info.api_endpoints.add(url)
                info.dependencies.add("openapi:api")
        
        # 4. import.meta.env.VITE_*
        for match in re.finditer(
            r'import\.meta\.env\.(VITE_[A-Z_]+)',
            content
        ):
            info.env_variables.add(match.group(1))
        
        return info
    
    def scan_directory(self, pattern: str = "web/frontend/src/**/*") -> List[DependencyInfo]:
        """
        扫描目录中的所有 TypeScript 文件
        
        Args:
            pattern: glob 模式
            
        Returns:
            DependencyInfo 列表
        """
        results = []
        exclude_patterns = ["node_modules", ".next", "dist", "build"]
        
        for ext in ["*.ts", "*.tsx"]:
            for tsfile in self.root.glob(f"{pattern}/{ext}"):
                # 排除目录
                if any(p in str(tsfile) for p in exclude_patterns):
                    continue
                
                info = self.analyze_file(tsfile)
                if info:
                    results.append(info)
                    self.dependencies[info.source] = info
        
        return results


class DependencyDiscoverer:
    """依赖图谱自动发现引擎"""
    
    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = root
        self.python_analyzer = PythonDependencyAnalyzer(root)
        self.typescript_analyzer = TypeScriptDependencyAnalyzer(root)
        self.reverse_index: Dict[str, Set[str]] = defaultdict(set)
    
    def run_full_scan(self) -> Dict:
        """
        执行完整扫描
        
        Returns:
            扫描结果字典
        """
        print("🔍 Running full dependency scan...")
        print()
        
        # 1. 扫描 Python 文件
        print("1️⃣  Scanning Python files...")
        python_results = []
        for pattern in ["api/**/*.py", "core/**/*.py", "scripts/**/*.py"]:
            results = self.python_analyzer.scan_directory(pattern)
            python_results.extend(results)
        print(f"   ✓ Scanned {len(python_results)} Python files")
        
        # 2. 扫描 TypeScript 文件
        print("\n2️⃣  Scanning TypeScript files...")
        ts_results = self.typescript_analyzer.scan_directory()
        print(f"   ✓ Scanned {len(ts_results)} TypeScript files")
        
        # 3. 构建反向索引
        print("\n3️⃣  Building reverse index...")
        self._build_reverse_index()
        print(f"   ✓ Indexed {len(self.reverse_index)} dependencies")
        
        # 4. 生成联动规则
        print("\n4️⃣  Generating linkage rules...")
        rules = self._generate_linkage_rules()
        print(f"   ✓ Generated {len(rules)} linkage rules")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "python_files": len(python_results),
            "typescript_files": len(ts_results),
            "dependencies": {
                k: v.to_dict() 
                for k, v in {**self.python_analyzer.dependencies, **self.typescript_analyzer.dependencies}.items()
            },
            "reverse_index": {k: sorted(list(v)) for k, v in self.reverse_index.items()},
            "linkage_rules": rules,
        }
    
    def _build_reverse_index(self):
        """构建反向索引：依赖目标 → 被哪些文件依赖"""
        all_deps = {**self.python_analyzer.dependencies, **self.typescript_analyzer.dependencies}
        
        for source, info in all_deps.items():
            # Python/TypeScript 模块依赖
            for dep in info.dependencies:
                self.reverse_index[dep].add(source)
            
            # API 端点依赖
            for endpoint in info.api_endpoints:
                self.reverse_index[f"api:{endpoint}"].add(source)
            
            # 环境变量依赖
            for var in info.env_variables:
                self.reverse_index[f"env:{var}"].add(source)
    
    def _generate_linkage_rules(self) -> Dict[str, List[str]]:
        """
        生成联动规则（替代手动 DEPENDENCIES）
        
        Returns:
            源文件 → 受影响目标文件列表 的映射
        """
        rules = defaultdict(list)
        
        # 规则 1: OpenAPI 变更 → 所有 API 相关文件
        openapi_dependents = set()
        openapi_dependents.update(self.reverse_index.get("openapi:api", set()))
        openapi_dependents.update(self.reverse_index.get("py:api.routes", set()))
        
        # 添加 api/routes/*.py 文件
        for key in self.python_analyzer.dependencies:
            if key.startswith("api/routes/"):
                openapi_dependents.add(key)
        
        if openapi_dependents:
            rules["contracts/openapi.yaml"] = sorted(list(openapi_dependents))
        
        # 规则 2: 配置 Schema 变更 → 使用环境变量的文件
        for var, files in self.reverse_index.items():
            if var.startswith("env:"):
                var_name = var[4:]  # 去掉 "env:" 前缀
                rules[f"env:{var_name}"] = sorted(list(files))
        
        # 规则 3: 核心模块变更 → 依赖它的文件
        core_modules = [
            "core/self_evolving.py",
            "core/skill_manager.py",
            "core/memory.py",
        ]
        for module in core_modules:
            module_key = f"py:{module.replace('/', '.').replace('.py', '')}"
            if module_key in self.reverse_index:
                rules[module] = sorted(list(self.reverse_index[module_key]))
        
        return dict(rules)
    
    def get_affected_files(self, changed_file: str) -> List[str]:
        """
        获取受变更影响的文件列表
        
        Args:
            changed_file: 变更的文件路径
            
        Returns:
            受影响的文件列表
        """
        affected = set()
        
        # 从联动规则查找
        rules = self._generate_linkage_rules()
        if changed_file in rules:
            affected.update(rules[changed_file])
        
        # 从反向索引查找
        # 如果是 Python 模块变更，查找导入它的文件
        if changed_file.endswith(".py"):
            module_key = f"py:{changed_file.replace('/', '.').replace('.py', '')}"
            affected.update(self.reverse_index.get(module_key, set()))
        
        return sorted(list(affected))
    
    def save_cache(self, output_path: Path = CACHE_FILE):
        """保存扫描结果到缓存文件"""
        result = self.run_full_scan()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Saved to: {output_path}")
        return result
    
    def load_cache(self, cache_path: Path = CACHE_FILE) -> Optional[Dict]:
        """从缓存文件加载扫描结果"""
        if not cache_path.exists():
            return None
        
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Dependency Discovery Engine for Kaelis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/dependency_discovery.py
    python scripts/dependency_discovery.py --output .kaelis/auto_dependencies.json
    python scripts/dependency_discovery.py --watch  # 持续监控
    python scripts/dependency_discovery.py --affected contracts/openapi.yaml
        """
    )
    
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file for scan results"
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Watch mode: continuously monitor changes"
    )
    parser.add_argument(
        "--affected",
        help="Show files affected by changing the specified file"
    )
    parser.add_argument(
        "--stats", "-s",
        action="store_true",
        help="Show statistics only"
    )
    
    args = parser.parse_args()
    
    discoverer = DependencyDiscoverer()
    
    if args.affected:
        # 加载缓存或重新扫描
        cache = discoverer.load_cache()
        if cache:
            # 重建反向索引
            discoverer.reverse_index = defaultdict(set)
            for k, v in cache.get("reverse_index", {}).items():
                discoverer.reverse_index[k] = set(v)
        
        affected = discoverer.get_affected_files(args.affected)
        print(f"🔍 Files affected by changing: {args.affected}")
        print()
        if affected:
            for f in affected:
                print(f"  → {f}")
        else:
            print("  (no files affected)")
        return
    
    if args.stats:
        cache = discoverer.load_cache()
        if cache:
            print("📊 Dependency Statistics")
            print("=" * 50)
            print(f"Python files: {cache.get('python_files', 0)}")
            print(f"TypeScript files: {cache.get('typescript_files', 0)}")
            print(f"Total dependencies: {len(cache.get('dependencies', {}))}")
            print(f"Linkage rules: {len(cache.get('linkage_rules', {}))}")
        else:
            print("❌ No cache found. Run scan first.")
        return
    
    # 执行完整扫描
    if args.output:
        result = discoverer.save_cache(args.output)
    else:
        result = discoverer.run_full_scan()
        if args.watch:
            print("\n👀 Watch mode enabled. Press Ctrl+C to stop.")
            # TODO: Implement file watching
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 Scan Summary")
    print("=" * 60)
    print(f"Python files scanned: {result['python_files']}")
    print(f"TypeScript files scanned: {result['typescript_files']}")
    print(f"Dependencies indexed: {len(result['dependencies'])}")
    print(f"Linkage rules generated: {len(result['linkage_rules'])}")
    
    # 打印关键联动规则
    print("\n🔗 Key Linkage Rules:")
    for source, targets in list(result['linkage_rules'].items())[:5]:
        print(f"   {source}")
        print(f"     → affects {len(targets)} file(s)")


if __name__ == "__main__":
    main()
