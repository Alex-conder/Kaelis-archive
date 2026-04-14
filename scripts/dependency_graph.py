#!/usr/bin/env python3
"""
Dependency Graph Engine for Kaelis

架构收敛与模块联动修正系统。

核心功能：
1. 定义源-目标依赖关系映射
2. 检测文件变更并找出受影响模块
3. 生成联动修正任务清单
4. 执行自动同步
5. 一致性校验

设计原则：
- 单一事实源：contracts/openapi.yaml 驱动所有下游代码
- 声明式依赖：在 DEPENDENCIES 中明确定义变更传播路径
- 自动同步：修改一处，自动修正所有关联模块
"""

import fnmatch
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
CONFIG_DIR = PROJECT_ROOT / "config"
KELIS_DIR = PROJECT_ROOT / ".kaelis"
AUDIT_DIR = KELIS_DIR / "audit"

# ============================================================================
# 依赖关系映射表
# 定义：当【源文件】变更时，需要同步的【目标文件】列表
# ============================================================================
DEPENDENCIES: dict[str, list[str]] = {
    # ------------------------------------------------------------------------
    # OpenAPI 契约 - 单一事实源
    # ------------------------------------------------------------------------
    "contracts/openapi.yaml": [
        # 后端路由 - 基于标签生成
        "api/routes/system.py",
        "api/routes/knowledge_graph.py",
        "api/routes/intent.py",
        "api/routes/symbols.py",
        "api/routes/team.py",
        "api/routes/omics.py",
        "api/routes/reports.py",
        "api/routes/misc.py",
        # 前端类型
        "web/frontend/src/api/schema.d.ts",
        # 测试 - 自动生成
        "tests/test_api_system.py",
        "tests/test_api_knowledge_graph.py",
        "tests/test_api_intent.py",
        "tests/test_api_symbols.py",
        "tests/test_api_team.py",
        "tests/test_api_omics.py",
        "tests/test_api_reports.py",
        "tests/test_api_misc.py",
        "tests/conftest.py",
        # Postman 集合
        "postman/kaelis_collection.json",
        "postman/kaelis_environment.json",
        # 文档 - 自动同步
        "README_API.md",
    ],
    
    # ------------------------------------------------------------------------
    # SLO 配置
    # ------------------------------------------------------------------------
    "config/slo.yaml": [
        "infrastructure/monitoring/prometheus/rules.yml",
        "infrastructure/monitoring/grafana/dashboards/slo.json",
        "scripts/slo_validator.py",
        "docs/operations/slo.md",
    ],
    
    # ------------------------------------------------------------------------
    # 模板配置
    # ------------------------------------------------------------------------
    "config/templates/approved/*.yaml": [
        "scripts/kaelis",
        "config/ack.yaml",
    ],
    
    # ------------------------------------------------------------------------
    # 核心配置文件
    # ------------------------------------------------------------------------
    ".env.example": [
        "docker-compose.yml",
        "Makefile",
    ],
    
    "config/kaelis.yaml": [
        "docker-compose.yml",
    ],
    
    # ------------------------------------------------------------------------
    # 符号定义
    # ------------------------------------------------------------------------
    ".kaelis/symbols/symbols.json": [
        "scripts/kaelis",
        "scripts/intent_parser.py",
    ],
    
    # ------------------------------------------------------------------------
    # 数据库 Schema
    # ------------------------------------------------------------------------
    "database/schema.sql": [
        "database/migrations/*.py",
        "api/models/*.py",
        "docs/database/schema.md",
    ],
    
    # ------------------------------------------------------------------------
    # 共享类型定义
    # ------------------------------------------------------------------------
    "core/types.py": [
        "api/**/*.py",
        "agents/**/*.py",
        "web/frontend/src/types/*.ts",
    ],
}

# ============================================================================
# 生成规则配置
# 定义：如何根据源文件生成目标文件
# ============================================================================
GENERATION_RULES: dict[str, dict[str, Any]] = {
    "contracts/openapi.yaml": {
        "generator": "codegen",
        "commands": [
            "python scripts/codegen.py backend --output api/routes",
            "python scripts/codegen.py frontend --output web/frontend/src/api",
            "python scripts/codegen.py tests --output tests",
            "python scripts/codegen.py postman --output postman",
            "python scripts/codegen.py readme --output .",
        ],
        "validators": [
            "python scripts/dependency_graph.py validate --type openapi",
            "python scripts/dependency_graph.py verify",
        ],
    },
    "config/slo.yaml": {
        "generator": "slo",
        "commands": [
            "python scripts/slo_validator.py generate",
        ],
    },
}


@dataclass
class SyncTask:
    """联动修正任务"""
    source: str
    targets: list[str]
    commands: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, success, failed
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass  
class DependencyNode:
    """依赖图节点"""
    path: str
    dependents: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    last_modified: str | None = None
    checksum: str | None = None


class DependencyGraph:
    """
    依赖图谱引擎
    
    实现功能：
    - 构建项目依赖图
    - 检测变更影响范围
    - 生成联动修正任务
    - 执行同步操作
    """
    
    def __init__(self):
        self.nodes: dict[str, DependencyNode] = {}
        self._build_graph()
    
    def _build_graph(self):
        """构建依赖图"""
        for source, targets in DEPENDENCIES.items():
            # 源节点
            if source not in self.nodes:
                self.nodes[source] = DependencyNode(path=source)
            
            # 目标节点
            for target in targets:
                if target not in self.nodes:
                    self.nodes[target] = DependencyNode(path=target)
                
                # 建立双向关系
                self.nodes[source].dependents.append(target)
                self.nodes[target].dependencies.append(source)
    
    def _load_auto_dependencies(self) -> dict[str, list[str]]:
        """加载自动发现的依赖规则"""
        cache_file = PROJECT_ROOT / ".kaelis" / "auto_dependencies.json"
        if not cache_file.exists():
            return {}
        
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("linkage_rules", {})
        except Exception:
            return {}
    
    def get_affected(self, changed_file: str) -> list[str]:
        """
        获取受变更影响的所有模块
        
        优先使用自动发现的依赖规则，回退到手动配置
        
        Args:
            changed_file: 变更的文件路径
            
        Returns:
            需要同步的目标文件列表
        """
        affected = []
        
        # 1. 优先使用自动发现的规则
        auto_rules = self._load_auto_dependencies()
        if changed_file in auto_rules:
            affected.extend(auto_rules[changed_file])
        
        # 2. 从自动规则的反向索引查找
        cache_file = PROJECT_ROOT / ".kaelis" / "auto_dependencies.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                reverse_index = data.get("reverse_index", {})
                
                # Python 模块变更 → 导入它的文件
                if changed_file.endswith(".py"):
                    module_key = f"py:{changed_file.replace('/', '.').replace('.py', '')}"
                    if module_key in reverse_index:
                        affected.extend(reverse_index[module_key])
                
                # TypeScript 模块变更
                elif changed_file.endswith((".ts", ".tsx")):
                    module_key = f"ts:{changed_file}"
                    if module_key in reverse_index:
                        affected.extend(reverse_index[module_key])
                
                # 环境变量 Schema 变更 → 使用这些变量的文件
                if changed_file == "config/env.schema.json":
                    for key, files in reverse_index.items():
                        if key.startswith("env:"):
                            affected.extend(files)
            
            except Exception:
                pass
        
        # 3. 回退到手动配置（兜底）
        for source_pattern, targets in DEPENDENCIES.items():
            if self._matches(changed_file, source_pattern):
                affected.extend(targets)
        
        # 去重并过滤掉自身
        return list(set(f for f in affected if f != changed_file))
    
    def _matches(self, file: str, pattern: str) -> bool:
        """检查文件是否匹配模式"""
        # 支持通配符匹配
        return fnmatch.fnmatch(file, pattern) or file == pattern
    
    def get_sync_tasks(self, changed_files: list[str]) -> list[SyncTask]:
        """
        根据变更文件生成联动修正任务
        
        Args:
            changed_files: 变更文件列表
            
        Returns:
            同步任务列表
        """
        tasks = []
        
        for changed_file in changed_files:
            affected = self.get_affected(changed_file)
            
            if not affected:
                continue
            
            # 查找生成规则
            commands = []
            for source_pattern, rule in GENERATION_RULES.items():
                if self._matches(changed_file, source_pattern):
                    commands.extend(rule.get("commands", []))
            
            task = SyncTask(
                source=changed_file,
                targets=affected,
                commands=commands,
            )
            tasks.append(task)
        
        return tasks
    
    def check_consistency(self) -> dict[str, Any]:
        """
        检查系统一致性
        
        检测：
        - OpenAPI 与后端路由是否一致
        - OpenAPI 与前端类型是否一致
        - 配置项是否漂移
        
        Returns:
            一致性检查结果
        """
        issues = []
        
        # 检查 1: OpenAPI 规范是否存在
        openapi_file = PROJECT_ROOT / "contracts" / "openapi.yaml"
        if not openapi_file.exists():
            issues.append({
                "level": "error",
                "message": "OpenAPI specification missing",
                "file": "contracts/openapi.yaml",
            })
        
        # 检查 2: 后端路由是否从 OpenAPI 生成
        backend_routes = PROJECT_ROOT / "api" / "routes"
        if backend_routes.exists() and openapi_file.exists():
            openapi_mtime = openapi_file.stat().st_mtime
            
            for route_file in backend_routes.glob("*.py"):
                if route_file.stat().st_mtime < openapi_mtime:
                    issues.append({
                        "level": "warning",
                        "message": f"Backend route {route_file.name} is older than OpenAPI spec",
                        "file": str(route_file.relative_to(PROJECT_ROOT)),
                        "suggestion": "Run `make sync-backend`",
                    })
        
        # 检查 3: 前端类型是否从 OpenAPI 生成
        frontend_types = PROJECT_ROOT / "web" / "frontend" / "src" / "api" / "schema.d.ts"
        if frontend_types.exists() and openapi_file.exists():
            if frontend_types.stat().st_mtime < openapi_file.stat().st_mtime:
                issues.append({
                    "level": "warning",
                    "message": "Frontend types are older than OpenAPI spec",
                    "file": str(frontend_types.relative_to(PROJECT_ROOT)),
                    "suggestion": "Run `make sync-frontend`",
                })
        
        # 检查 4: 配置漂移
        env_example = PROJECT_ROOT / ".env.example"
        docker_compose = PROJECT_ROOT / "docker-compose.yml"
        
        if env_example.exists() and docker_compose.exists():
            env_content = env_example.read_text(encoding="utf-8")
            compose_content = docker_compose.read_text(encoding="utf-8")
            
            # 简单检查：提取端口号
            import re
            env_ports = set(re.findall(r'PORT[:=]\s*(\d+)', env_content))
            compose_ports = set(re.findall(r'"(\d+):\d+"', compose_content))
            
            if env_ports != compose_ports and env_ports and compose_ports:
                issues.append({
                    "level": "warning",
                    "message": f"Port configuration mismatch: .env.example={env_ports}, docker-compose.yml={compose_ports}",
                    "file": ".env.example, docker-compose.yml",
                    "suggestion": "Run `make sync-config`",
                })
        
        return {
            "status": "consistent" if not issues else "inconsistent",
            "issues": issues,
            "timestamp": datetime.now().isoformat(),
        }
    
    def audit(self, output_file: Path | None = None) -> dict[str, Any]:
        """
        执行完整架构审计
        
        检查维度：
        - 通 (Connectivity): 模块间连接是否完整
        - 达 (Reachability): 变更能否正确传播到所有依赖
        - 速 (Speed): 同步延迟是否在可接受范围
        - 省 (Efficiency): 同步是否高效，避免冗余
        
        Returns:
            审计报告
        """
        print("🔍 Running Architecture Audit: 通、达、速、省")
        print()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "dimensions": {},
            "recommendations": [],
        }
        
        # 维度 1: 通 (Connectivity)
        print("1️⃣ 通 (Connectivity) - 检查模块连接完整性...")
        connectivity_issues = []
        
        openapi_file = PROJECT_ROOT / "contracts" / "openapi.yaml"
        if openapi_file.exists():
            import yaml
            spec = yaml.safe_load(openapi_file.read_text(encoding="utf-8"))
            defined_paths = set(spec.get("paths", {}).keys())
            
            # 检查后端实现
            backend_routes = PROJECT_ROOT / "api" / "routes"
            if backend_routes.exists():
                implemented_paths = set()
                for route_file in backend_routes.glob("*.py"):
                    content = route_file.read_text(encoding="utf-8")
                    # 简单提取 @bp.route 装饰器
                    import re
                    routes = re.findall(r"@bp\.route\(['\"]([^'\"]+)['\"]", content)
                    implemented_paths.update(routes)
                
                missing = defined_paths - implemented_paths
                if missing:
                    connectivity_issues.append({
                        "type": "missing_implementation",
                        "paths": list(missing),
                        "message": f"{len(missing)} API paths defined but not implemented",
                    })
        
        report["dimensions"]["connectivity"] = {
            "score": 100 - len(connectivity_issues) * 10,
            "issues": connectivity_issues,
        }
        print(f"   Score: {report['dimensions']['connectivity']['score']}/100")
        
        # 维度 2: 达 (Reachability) - 改进版，考虑自动发现的依赖
        print("\n2️⃣ 达 (Reachability) - 检查变更传播可达性...")
        
        unreachable = []
        
        # 加载自动发现的依赖
        auto_deps = self._load_auto_dependencies()
        
        # 合并手动和自动的依赖关系
        all_sources = set(DEPENDENCIES.keys()) | set(auto_deps.keys())
        
        for source in all_sources:
            source_path = PROJECT_ROOT / source
            if "*" in source:
                continue
            
            # 获取该源的所有目标（手动 + 自动）
            manual_targets = DEPENDENCIES.get(source, [])
            auto_targets = auto_deps.get(source, [])
            all_targets = set(manual_targets) | set(auto_targets)
            
            for target in all_targets:
                if "*" in target:
                    continue
                target_path = PROJECT_ROOT / target
                if not target_path.exists():
                    unreachable.append({
                        "source": source,
                        "target": target,
                        "message": f"Target does not exist: {target}",
                    })
        
        # 计算可达性得分：基于文件覆盖率
        all_defined_targets = set()
        existing_targets = set()
        
        for source in all_sources:
            source_path = PROJECT_ROOT / source
            if "*" in source or not source_path.exists():
                continue
            
            targets = set(DEPENDENCIES.get(source, [])) | set(auto_deps.get(source, []))
            for target in targets:
                if "*" not in target:
                    all_defined_targets.add(target)
                    target_path = PROJECT_ROOT / target
                    if target_path.exists():
                        existing_targets.add(target)
        
        # 额外加分：自动发现的依赖覆盖率
        auto_coverage_bonus = 0
        if auto_deps:
            # 如果自动发现了额外依赖，给予加分
            auto_only_targets = set()
            for targets in auto_deps.values():
                auto_only_targets.update(targets)
            
            # 计算自动发现的覆盖率
            py_files = set(str(p.relative_to(PROJECT_ROOT)) for p in PROJECT_ROOT.rglob("api/**/*.py"))
            ts_files = set(str(p.relative_to(PROJECT_ROOT)) for p in PROJECT_ROOT.rglob("web/frontend/src/**/*.{ts,tsx}"))
            all_code_files = py_files | ts_files
            
            if all_code_files:
                coverage = len(auto_only_targets & all_code_files) / len(all_code_files)
                auto_coverage_bonus = int(coverage * 10)  # 最多加 10 分
        
        if all_defined_targets:
            base_score = int(len(existing_targets) / len(all_defined_targets) * 100)
            reachability_score = min(100, base_score + auto_coverage_bonus)
        else:
            reachability_score = 100
            
        report["dimensions"]["reachability"] = {
            "score": reachability_score,
            "issues": unreachable,
            "auto_discovered_rules": len(auto_deps),
        }
        print(f"   Score: {report['dimensions']['reachability']['score']}/100")
        print(f"   Existing: {len(existing_targets)}/{len(all_defined_targets)}")
        if auto_deps:
            print(f"   Auto-discovered rules: {len(auto_deps)} (+{auto_coverage_bonus} bonus)")
        
        # 维度 3: 速 (Speed)
        print("\n3️⃣ 速 (Speed) - 检查同步时效...")
        
        stale_targets = []
        total_checked = 0
        
        for source_pattern, targets in DEPENDENCIES.items():
            if "*" in source_pattern:
                continue
            source_path = PROJECT_ROOT / source_pattern
            if not source_path.exists():
                continue
            
            source_mtime = source_path.stat().st_mtime
            
            for target_pattern in targets:
                if "*" in target_pattern:
                    # 检查该模式下所有文件
                    target_dir = PROJECT_ROOT / target_pattern.split("*")[0]
                    if target_dir.exists():
                        for target_file in target_dir.glob("*" + target_pattern.split("*")[1]):
                            total_checked += 1
                            if target_file.stat().st_mtime < source_mtime:
                                stale_targets.append({
                                    "source": source_pattern,
                                    "target": str(target_file.relative_to(PROJECT_ROOT)),
                                    "lag_seconds": source_mtime - target_file.stat().st_mtime,
                                })
                else:
                    target_path = PROJECT_ROOT / target_pattern
                    if target_path.exists():
                        total_checked += 1
                        if target_path.stat().st_mtime < source_mtime:
                            stale_targets.append({
                                "source": source_pattern,
                                "target": target_pattern,
                                "lag_seconds": source_mtime - target_path.stat().st_mtime,
                            })
        
        # 计算同步得分：新鲜文件的比例
        if total_checked > 0:
            fresh_count = total_checked - len(stale_targets)
            speed_score = int(fresh_count / total_checked * 100)
        else:
            speed_score = 100
            
        report["dimensions"]["speed"] = {
            "score": speed_score,
            "stale_count": len(stale_targets),
            "issues": stale_targets[:10],  # 只显示前10个
        }
        print(f"   Score: {report['dimensions']['speed']['score']}/100")
        print(f"   Fresh: {total_checked - len(stale_targets)}/{total_checked}")
        
        # 维度 4: 省 (Efficiency)
        print("\n4️⃣ 省 (Efficiency) - 检查同步效率...")
        
        redundant_rules = []
        covered_patterns = set()
        
        for source in DEPENDENCIES.keys():
            for pattern in covered_patterns:
                if fnmatch.fnmatch(source, pattern) or fnmatch.fnmatch(pattern, source):
                    redundant_rules.append({
                        "patterns": [source, pattern],
                        "message": f"Potentially redundant patterns: {source} and {pattern}",
                    })
            covered_patterns.add(source)
        
        report["dimensions"]["efficiency"] = {
            "score": 100 - len(redundant_rules) * 5,
            "issues": redundant_rules,
        }
        print(f"   Score: {report['dimensions']['efficiency']['score']}/100")
        
        # 生成建议
        print("\n📝 Recommendations:")
        if connectivity_issues:
            report["recommendations"].append("Run `make sync-backend` to implement missing API routes")
        if stale_targets:
            report["recommendations"].append("Run `make sync-all` to update stale targets")
        if unreachable:
            report["recommendations"].append("Review DEPENDENCIES mapping for missing target files")
        
        if not report["recommendations"]:
            report["recommendations"].append("All systems are consistent. No action needed.")
            print("   ✅ All systems are consistent!")
        else:
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"   {i}. {rec}")
        
        # 总体评分
        overall_score = sum(
            d["score"] for d in report["dimensions"].values()
        ) / len(report["dimensions"])
        report["overall_score"] = round(overall_score, 1)
        
        print(f"\n📊 Overall Architecture Score: {report['overall_score']}/100")
        
        # 保存报告
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Report saved to: {output_file}")
        
        return report
    
    def verify(self) -> dict[str, Any]:
        """
        双向验证：检查现有实现是否与 OpenAPI 规范一致
        
        Returns:
            验证结果，包含不一致清单
        """
        print("🔍 Running Bidirectional Verification")
        print("=" * 60)
        print()
        
        import yaml
        import re
        
        openapi_file = PROJECT_ROOT / "contracts" / "openapi.yaml"
        if not openapi_file.exists():
            print("❌ OpenAPI file not found")
            return {"status": "error", "message": "OpenAPI file not found"}
        
        spec = yaml.safe_load(openapi_file.read_text(encoding="utf-8"))
        paths = spec.get("paths", {})
        
        issues = []
        verified = []
        
        # 检查 1: 后端路由实现
        print("1️⃣ Verifying backend route implementations...")
        routes_dir = PROJECT_ROOT / "api" / "routes"
        
        if routes_dir.exists():
            # 收集 OpenAPI 定义的所有操作
            openapi_operations = set()
            for path, methods in paths.items():
                for method, operation in methods.items():
                    if method == "parameters":
                        continue
                    operation_id = operation.get("operationId", "")
                    if operation_id:
                        openapi_operations.add(operation_id)
            
            # 收集已实现的函数
            implemented_operations = set()
            for route_file in routes_dir.glob("*.py"):
                content = route_file.read_text(encoding="utf-8")
                # 提取函数定义
                functions = re.findall(r'^def (\w+)\(', content, re.MULTILINE)
                implemented_operations.update(functions)
            
            # 检查缺失的实现
            missing = openapi_operations - implemented_operations
            extra = implemented_operations - openapi_operations - {"health_check"}
            
            if missing:
                issues.append({
                    "type": "missing_implementation",
                    "severity": "high",
                    "message": f"{len(missing)} API operations not implemented",
                    "operations": list(missing),
                    "fix": "Run `make sync-backend` to generate missing routes",
                })
                print(f"   ❌ {len(missing)} operations missing")
            else:
                print(f"   ✅ All {len(openapi_operations)} operations implemented")
            
            if extra:
                issues.append({
                    "type": "extra_implementation",
                    "severity": "low",
                    "message": f"{len(extra)} functions not in OpenAPI spec",
                    "operations": list(extra)[:5],
                })
        else:
            issues.append({
                "type": "missing_routes_dir",
                "severity": "high",
                "message": "Backend routes directory not found",
                "fix": "Run `make sync-backend`",
            })
        
        # 检查 2: 前端类型定义
        print("\n2️⃣ Verifying frontend type definitions...")
        types_file = PROJECT_ROOT / "web" / "frontend" / "src" / "api" / "schema.d.ts"
        
        if types_file.exists():
            content = types_file.read_text(encoding="utf-8")
            schemas = spec.get("components", {}).get("schemas", {})
            
            missing_types = []
            for schema_name in schemas.keys():
                if f"export interface {schema_name}" not in content:
                    missing_types.append(schema_name)
            
            if missing_types:
                issues.append({
                    "type": "missing_types",
                    "severity": "medium",
                    "message": f"{len(missing_types)} TypeScript types missing",
                    "types": missing_types[:5],
                    "fix": "Run `make sync-frontend` to generate types",
                })
                print(f"   ❌ {len(missing_types)} types missing")
            else:
                print(f"   ✅ All {len(schemas)} TypeScript types present")
        else:
            issues.append({
                "type": "missing_types_file",
                "severity": "medium",
                "message": "Frontend types file not found",
                "fix": "Run `make sync-frontend`",
            })
        
        # 检查 3: 测试覆盖
        print("\n3️⃣ Verifying test coverage...")
        tests_dir = PROJECT_ROOT / "tests"
        
        if tests_dir.exists():
            test_files = list(tests_dir.glob("test_api_*.py"))
            expected_tests = len(openapi_operations) / 3  # 粗略估计
            
            if len(test_files) < expected_tests:
                issues.append({
                    "type": "insufficient_tests",
                    "severity": "low",
                    "message": f"Test coverage may be insufficient ({len(test_files)} files)",
                    "fix": "Run `make sync-tests` to generate tests",
                })
                print(f"   ⚠️ Only {len(test_files)} test files found")
            else:
                print(f"   ✅ {len(test_files)} test files present")
        else:
            issues.append({
                "type": "missing_tests",
                "severity": "low",
                "message": "Tests directory not found",
                "fix": "Run `make sync-tests`",
            })
        
        # 检查 4: 文档同步
        print("\n4️⃣ Verifying documentation sync...")
        readme_api = PROJECT_ROOT / "README_API.md"
        
        if readme_api.exists():
            readme_mtime = readme_api.stat().st_mtime
            spec_mtime = openapi_file.stat().st_mtime
            
            if readme_mtime < spec_mtime:
                issues.append({
                    "type": "stale_documentation",
                    "severity": "low",
                    "message": "API documentation is older than OpenAPI spec",
                    "fix": "Run `make sync-readme` to update docs",
                })
                print(f"   ⚠️ Documentation is stale")
            else:
                print(f"   ✅ Documentation is up to date")
        else:
            issues.append({
                "type": "missing_documentation",
                "severity": "low",
                "message": "API documentation not found",
                "fix": "Run `make sync-readme`",
            })
        
        # 检查 5: 环境变量校验（新增）
        print("\n5️⃣ Verifying environment variables...")
        schema_path = PROJECT_ROOT / "config" / "env.schema.json"
        
        if schema_path.exists():
            # 尝试导入并运行校验
            try:
                import sys
                sys.path.insert(0, str(PROJECT_ROOT))
                from core.env_validator import validate_env, load_env_file
                
                env_vars = load_env_file()
                result = validate_env(env_vars, strict=False)
                
                if result.is_valid:
                    print(f"   ✅ Environment variables valid")
                else:
                    print(f"   ❌ {len(result.errors)} validation errors")
                    issues.append({
                        "type": "env_validation_failed",
                        "severity": "high" if result.errors else "low",
                        "message": f"{len(result.errors)} environment variable validation errors",
                        "fix": "Run `python core/env_validator.py` to see details",
                    })
                
                if result.warnings:
                    print(f"   ⚠️  {len(result.warnings)} warnings")
                    
            except Exception as e:
                print(f"   ⚠️  Could not validate environment: {e}")
        else:
            print(f"   ⚠️  Schema file not found: config/env.schema.json")
            issues.append({
                "type": "missing_env_schema",
                "severity": "medium",
                "message": "Environment schema not found",
                "fix": "Create config/env.schema.json",
            })
        
        # 检查 6: 数据库模型同步（新增）
        print("\n6️⃣ Verifying database models...")
        models_dir = PROJECT_ROOT / "api" / "models"
        
        if models_dir.exists():
            # 收集 OpenAPI 中应该生成模型的实体
            schemas = spec.get("components", {}).get("schemas", {})
            
            # 明确包含的核心实体（即使没有 id 字段）
            CORE_ENTITIES = ["Triple", "Report", "Metabolite", "Compound"]
            
            def is_entity_schema(name: str, schema: dict) -> bool:
                """判断是否为实体 Schema"""
                if name in CORE_ENTITIES:
                    return True
                if any(suffix in name for suffix in ["Request", "Response", "DTO", "Input", "Output"]):
                    return False
                properties = schema.get("properties", {})
                entity_indicators = ["id", "created_at", "updated_at", "uuid", "pk"]
                return any(indicator in properties for indicator in entity_indicators)
            
            expected_models = []
            for schema_name, schema in schemas.items():
                if is_entity_schema(schema_name, schema):
                    expected_models.append(schema_name.lower())
            
            # 检查已存在的模型
            existing_models = []
            for model_file in models_dir.glob("*.py"):
                if model_file.name != "__init__.py":
                    existing_models.append(model_file.stem)
            
            missing_models = set(expected_models) - set(existing_models)
            
            if missing_models:
                issues.append({
                    "type": "missing_models",
                    "severity": "medium",
                    "message": f"{len(missing_models)} database models missing",
                    "models": list(missing_models),
                    "fix": "Run `kaelis converge sync --with-models` to generate models",
                })
                print(f"   ❌ {len(missing_models)} models missing: {', '.join(missing_models)}")
            else:
                print(f"   ✅ All {len(expected_models)} database models present")
            
            # 检查 API 响应字段与模型列的一致性
            print(f"   🔍 Checking API-to-Model consistency...")
            # 简化的检查：验证主要字段存在
            consistent_count = 0
            for model_name in existing_models:
                model_file = models_dir / f"{model_name}.py"
                if model_file.exists():
                    content = model_file.read_text(encoding="utf-8")
                    # 查找对应的 Schema
                    schema_name = model_name.capitalize()
                    if schema_name in schemas:
                        schema_props = schemas[schema_name].get("properties", {})
                        # 检查主要字段是否存在
                        missing_cols = []
                        for prop in schema_props:
                            if prop not in ["id", "created_at", "updated_at"]:
                                if f"{prop} = Column" not in content:
                                    missing_cols.append(prop)
                        if not missing_cols:
                            consistent_count += 1
            
            if existing_models:
                print(f"   ✅ {consistent_count}/{len(existing_models)} models consistent with API")
        else:
            print(f"   ⚠️ Models directory not found")
        
        # 检查 7: 代码中环境变量使用扫描
        print("\n7️⃣ Scanning for undefined environment variable usage...")
        try:
            import subprocess
            result = subprocess.run(
                ["python", "scripts/verify_env_usage.py"],
                capture_output=True,
                text=True,
                timeout=30
            )
            # 检查是否有未定义变量
            if "UNDEFINED VARIABLES" in result.stdout:
                undefined_count = result.stdout.count("Variable:")
                print(f"   ⚠️  Found {undefined_count} undefined variable(s) in code")
                issues.append({
                    "type": "undefined_env_in_code",
                    "severity": "low",
                    "message": f"{undefined_count} environment variables used in code but not in schema",
                    "fix": "Run `python scripts/verify_env_usage.py --generate-template` to see details",
                })
            else:
                print(f"   ✅ All environment variables in code are defined in schema")
        except Exception as e:
            print(f"   ⚠️  Could not scan code: {e}")
        
        # 总结
        print("\n" + "=" * 60)
        
        if issues:
            print(f"⚠️ Found {len(issues)} consistency issues:")
            for i, issue in enumerate(issues, 1):
                icon = "🔴" if issue.get("severity") == "high" else "🟡" if issue.get("severity") == "medium" else "⚪"
                print(f"\n{i}. {icon} [{issue['severity'].upper()}] {issue['message']}")
                if "fix" in issue:
                    print(f"   💡 Fix: {issue['fix']}")
        else:
            print("✅ All verifications passed!")
        
        return {
            "status": "inconsistent" if issues else "consistent",
            "issues": issues,
            "timestamp": datetime.now().isoformat(),
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis Dependency Graph Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 检查文件变更的影响范围
    python scripts/dependency_graph.py affected contracts/openapi.yaml
    
    # 生成联动修正任务
    python scripts/dependency_graph.py tasks contracts/openapi.yaml
    
    # 执行架构审计 (通、达、速、省)
    python scripts/dependency_graph.py audit
    
    # 检查系统一致性
    python scripts/dependency_graph.py check
        """
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # affected 命令
    affected_parser = subparsers.add_parser(
        "affected",
        help="Get affected modules for changed files"
    )
    affected_parser.add_argument("files", nargs="+", help="Changed file paths")
    
    # tasks 命令
    tasks_parser = subparsers.add_parser(
        "tasks",
        help="Generate sync tasks for changed files"
    )
    tasks_parser.add_argument("files", nargs="+", help="Changed file paths")
    
    # audit 命令
    audit_parser = subparsers.add_parser(
        "audit",
        help="Run architecture audit (通、达、速、省)"
    )
    audit_parser.add_argument(
        "--output",
        type=Path,
        default=AUDIT_DIR / f"audit-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
        help="Output file for audit report"
    )
    
    # check 命令
    check_parser = subparsers.add_parser(
        "check",
        help="Check system consistency"
    )
    
    # validate 命令
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate specific aspect"
    )
    validate_parser.add_argument("--type", choices=["openapi", "config"], required=True)
    
    # verify 命令 - 双向验证
    verify_parser = subparsers.add_parser(
        "verify",
        help="Bidirectional verification: check if implementation matches OpenAPI spec"
    )
    verify_parser.add_argument(
        "--output",
        type=Path,
        help="Output file for verification report"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    graph = DependencyGraph()
    
    if args.command == "affected":
        print(f"🔍 Checking affected modules for: {', '.join(args.files)}")
        print()
        
        for file in args.files:
            affected = graph.get_affected(file)
            if affected:
                print(f"📄 {file}")
                print(f"   Affects {len(affected)} modules:")
                for target in affected:
                    print(f"      → {target}")
                print()
            else:
                print(f"📄 {file} - No dependencies defined")
    
    elif args.command == "tasks":
        print(f"📋 Generating sync tasks for: {', '.join(args.files)}")
        print()
        
        tasks = graph.get_sync_tasks(args.files)
        
        if not tasks:
            print("   No sync tasks needed")
            return
        
        for i, task in enumerate(tasks, 1):
            print(f"Task {i}:")
            print(f"  Source: {task.source}")
            print(f"  Targets ({len(task.targets)}):")
            for target in task.targets[:5]:
                print(f"    - {target}")
            if len(task.targets) > 5:
                print(f"    ... and {len(task.targets) - 5} more")
            if task.commands:
                print(f"  Commands:")
                for cmd in task.commands:
                    print(f"    $ {cmd}")
            print()
    
    elif args.command == "audit":
        graph.audit(args.output)
    
    elif args.command == "check":
        result = graph.check_consistency()
        
        print(f"📊 System Consistency Check")
        print(f"   Status: {result['status'].upper()}")
        print(f"   Timestamp: {result['timestamp']}")
        print()
        
        if result['issues']:
            print(f"⚠️ Found {len(result['issues'])} issues:")
            for issue in result['issues']:
                icon = "🔴" if issue['level'] == 'error' else "🟡"
                print(f"   {icon} [{issue['level'].upper()}] {issue['message']}")
                if 'suggestion' in issue:
                    print(f"      💡 {issue['suggestion']}")
        else:
            print("✅ All systems are consistent!")
        
        sys.exit(0 if result['status'] == 'consistent' else 1)
    
    elif args.command == "validate":
        if args.type == "openapi":
            openapi_file = PROJECT_ROOT / "contracts" / "openapi.yaml"
            if not openapi_file.exists():
                print("❌ OpenAPI file not found")
                sys.exit(1)
            
            import yaml
            try:
                spec = yaml.safe_load(openapi_file.read_text(encoding="utf-8"))
                print(f"✅ OpenAPI spec is valid")
                print(f"   Version: {spec.get('openapi', 'unknown')}")
                print(f"   API Title: {spec.get('info', {}).get('title', 'unknown')}")
                print(f"   Paths: {len(spec.get('paths', {}))}")
                print(f"   Schemas: {len(spec.get('components', {}).get('schemas', {}))}")
            except Exception as e:
                print(f"❌ Invalid OpenAPI spec: {e}")
                sys.exit(1)
        
        elif args.type == "config":
            result = graph.check_consistency()
            if result['status'] != 'consistent':
                print("❌ Configuration validation failed")
                for issue in result['issues']:
                    print(f"   - {issue['message']}")
                sys.exit(1)
            else:
                print("✅ Configuration is valid")
    
    elif args.command == "verify":
        result = graph.verify()
        
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Verification report saved to: {args.output}")
        
        sys.exit(0 if result['status'] == 'consistent' else 1)


if __name__ == "__main__":
    main()
