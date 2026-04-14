#!/usr/bin/env python3
"""
Kaelis Phase 5 (重构) - 决策契约引擎 (Decision Contract Engine)
将架构决策从自由文本提升为机器可读的约束契约

核心能力：
1. 决策契约的创建、激活、验证、归档
2. 约束条件的自动校验（AST 模式、正则、文件存在性等）
3. 决策生命周期管理（过期提醒、废止追踪）
4. 与现有系统集成（converge verify、make daily）
"""

import os
import sys
import json
import yaml
import re
import ast
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DECISION_DIR = PROJECT_ROOT / ".kaelis" / "decisions"
SCHEMA_FILE = PROJECT_ROOT / "config" / "schemas" / "decision.schema.yaml"


@dataclass
class ConstraintViolation:
    """约束违反记录"""
    decision_id: str
    constraint_id: str
    rule: str
    severity: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None


class DecisionContract:
    """决策契约数据类"""
    
    def __init__(self, data: dict):
        self.data = data
        self.id = data.get('id')
        self.type = data.get('type')
        self.status = data.get('status')
        self.title = data.get('title')
        self.scope = data.get('scope', {})
        self.constraints = data.get('constraints', [])
        self.review_after = data.get('review_after')
        self.superseded_by = data.get('superseded_by')
    
    def is_active(self) -> bool:
        """检查决策是否处于激活状态"""
        return self.status == 'active'
    
    def is_expired(self) -> bool:
        """检查决策是否已过期（需要重新评估）"""
        if not self.review_after:
            return False
        try:
            review_date = datetime.fromisoformat(self.review_after.replace('Z', '+00:00'))
            return datetime.now().astimezone() > review_date
        except:
            return False
    
    def to_dict(self) -> dict:
        return self.data
    
    def save(self):
        """保存决策契约到文件"""
        DECISION_DIR.mkdir(parents=True, exist_ok=True)
        file_path = DECISION_DIR / f"{self.id}.yaml"
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.data, f, allow_unicode=True, sort_keys=False)


class DecisionEngine:
    """决策契约引擎"""
    
    def __init__(self):
        self.decisions: Dict[str, DecisionContract] = {}
        self.schema = self._load_schema()
        self._load_all_decisions()
    
    def _load_schema(self) -> dict:
        """加载决策契约 Schema"""
        if SCHEMA_FILE.exists():
            return yaml.safe_load(SCHEMA_FILE.read_text(encoding='utf-8'))
        return {}
    
    def _load_all_decisions(self):
        """加载所有决策契约"""
        if not DECISION_DIR.exists():
            return
        
        for f in DECISION_DIR.glob("DEC-*.yaml"):
            try:
                data = yaml.safe_load(f.read_text(encoding='utf-8'))
                decision = DecisionContract(data)
                self.decisions[decision.id] = decision
            except Exception as e:
                print(f"⚠️  加载决策失败 {f}: {e}")
    
    def create_decision(self, interactive: bool = True) -> Optional[DecisionContract]:
        """创建新的决策契约"""
        print("\n" + "=" * 70)
        print("🎯 Kaelis 决策契约引擎")
        print("   将架构决策从自由文本提升为机器可读的约束契约")
        print("=" * 70)
        
        # 生成 ID
        decision_id = self._generate_id()
        print(f"\n📋 决策 ID: {decision_id}")
        
        if interactive:
            decision_data = self._interactive_create(decision_id)
        else:
            decision_data = self._auto_create(decision_id)
        
        if not decision_data:
            return None
        
        # 验证 Schema
        # TODO: 实现 JSON Schema 验证
        
        # 保存
        decision = DecisionContract(decision_data)
        decision.save()
        self.decisions[decision.id] = decision
        
        print(f"\n✅ 决策契约已保存: {DECISION_DIR / decision_id}.yaml")
        print(f"\n下一步:")
        print(f"   1. 编辑约束条件")
        print(f"   2. 运行 'kaelis decision activate {decision_id}' 激活约束")
        print(f"   3. 运行 'kaelis converge verify' 校验约束")
        
        return decision
    
    def _generate_id(self) -> str:
        """生成决策 ID"""
        date_str = datetime.now().strftime('%Y%m%d')
        existing = [d for d in self.decisions.keys() if d.startswith(f"DEC-{date_str}")]
        seq = len(existing) + 1
        return f"DEC-{date_str}-{seq:03d}"
    
    def _interactive_create(self, decision_id: str) -> Optional[dict]:
        """交互式创建决策"""
        # 标题
        title = input("\n📌 决策标题: ").strip()
        if not title:
            print("❌ 标题不能为空")
            return None
        
        # 类型
        print("\n📂 决策类型:")
        types = [
            ("architecture_pattern", "架构模式"),
            ("technology_choice", "技术选型"),
            ("api_design", "API 设计"),
            ("dependency_management", "依赖管理"),
            ("security_policy", "安全策略"),
            ("performance_optimization", "性能优化"),
            ("data_model", "数据模型"),
        ]
        for i, (t, desc) in enumerate(types, 1):
            print(f"   {i}. {desc} ({t})")
        
        type_choice = input("\n选择类型 (1-7): ").strip()
        try:
            decision_type = types[int(type_choice) - 1][0]
        except:
            decision_type = "architecture_pattern"
        
        # 描述
        description = input("\n📝 决策描述: ").strip()
        
        # 影响范围（自动分析）
        print("\n🔍 自动分析影响范围...")
        scope = self._analyze_scope()
        
        if scope['files']:
            print(f"   检测到 {len(scope['files'])} 个变更文件")
            add_more = input("   是否手动添加更多文件? (y/n): ").strip().lower()
            if add_more == 'y':
                while True:
                    file_path = input("   添加文件路径 (空行结束): ").strip()
                    if not file_path:
                        break
                    scope['files'].append(file_path)
        
        # 约束条件
        constraints = []
        if decision_type == 'architecture_pattern':
            print("\n⚖️  添加约束条件 (该决策施加的硬性规则):")
            print("   例如: '所有写操作必须通过 Command 服务'")
            
            while True:
                rule = input("\n   约束规则描述 (空行跳过): ").strip()
                if not rule:
                    break
                
                check_type = input("   校验类型 (ast_pattern/forbidden_pattern/regex_match): ").strip()
                pattern = input("   校验模式: ").strip()
                
                constraints.append({
                    'id': f"C{len(constraints) + 1}",
                    'rule': rule,
                    'check': {
                        'type': check_type or 'forbidden_pattern',
                        'pattern': pattern
                    },
                    'severity': 'error'
                })
        
        # 有效期
        print("\n⏰ 决策有效期:")
        print("   1. 3 个月")
        print("   2. 6 个月")
        print("   3. 1 年")
        validity = input("   选择 (1-3): ").strip()
        
        months = { '1': 3, '2': 6, '3': 12 }.get(validity, 3)
        review_after = (datetime.now() + timedelta(days=30*months)).isoformat()
        
        # 理由
        rationale = input("\n💭 决策理由: ").strip()
        
        return {
            'id': decision_id,
            'type': decision_type,
            'status': 'proposed',
            'title': title,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'review_after': review_after,
            'scope': scope,
            'constraints': constraints,
            'rationale': rationale or "未提供"
        }
    
    def _auto_create(self, decision_id: str) -> dict:
        """自动创建（基于 git diff）"""
        scope = self._analyze_scope()
        
        return {
            'id': decision_id,
            'type': 'architecture_pattern',
            'status': 'proposed',
            'title': '架构变更决策',
            'description': '自动生成的决策契约',
            'created_at': datetime.now().isoformat(),
            'review_after': (datetime.now() + timedelta(days=90)).isoformat(),
            'scope': scope,
            'constraints': [],
            'rationale': '待补充'
        }
    
    def _analyze_scope(self) -> dict:
        """分析影响范围（基于 git diff）"""
        scope = {'files': [], 'directories': [], 'services': []}
        
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD~3'],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )
            changed_files = [f for f in result.stdout.strip().split('\n') if f]
            scope['files'] = changed_files[:10]  # 最多 10 个
            
            # 推断服务
            services = set()
            for f in changed_files:
                if 'kg' in f.lower() or 'knowledge' in f.lower():
                    services.add('knowledge-graph')
                if 'api/routes' in f:
                    services.add('kaelis-api')
            scope['services'] = list(services)
            
        except:
            pass
        
        return scope
    
    def activate(self, decision_id: str) -> bool:
        """激活决策（约束开始生效）"""
        decision = self.decisions.get(decision_id)
        if not decision:
            print(f"❌ 决策 {decision_id} 不存在")
            return False
        
        decision.status = 'active'
        decision.data['status'] = 'active'
        decision.data['activated_at'] = datetime.now().isoformat()
        decision.save()
        
        print(f"✅ 决策 {decision_id} 已激活")
        print(f"   约束条件数量: {len(decision.constraints)}")
        print(f"   运行 'kaelis converge verify' 开始校验")
        
        return True
    
    def verify_constraints(self) -> List[ConstraintViolation]:
        """校验所有激活决策的约束条件"""
        violations = []
        
        for decision in self.decisions.values():
            if not decision.is_active():
                continue
            
            for constraint in decision.constraints:
                check = constraint.get('check', {})
                check_type = check.get('type')
                
                if check_type == 'ast_pattern':
                    v = self._check_ast_pattern(decision, constraint)
                    violations.extend(v)
                
                elif check_type == 'forbidden_pattern':
                    v = self._check_forbidden_pattern(decision, constraint)
                    violations.extend(v)
                
                elif check_type == 'file_exists':
                    v = self._check_file_exists(decision, constraint)
                    violations.extend(v)
                
                elif check_type == 'regex_match':
                    v = self._check_regex_match(decision, constraint)
                    violations.extend(v)
        
        return violations
    
    def _check_ast_pattern(self, decision: DecisionContract, constraint: dict) -> List[ConstraintViolation]:
        """AST 模式校验"""
        violations = []
        check = constraint.get('check', {})
        pattern = check.get('pattern', '')
        target_files = check.get('target_files', decision.scope.get('files', []))
        
        for file_path in target_files:
            full_path = PROJECT_ROOT / file_path
            if not full_path.exists():
                continue
            
            try:
                content = full_path.read_text(encoding='utf-8')
                tree = ast.parse(content)
                
                found = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if re.search(pattern, node.name):
                            found = True
                            break
                
                if not found:
                    violations.append(ConstraintViolation(
                        decision_id=decision.id,
                        constraint_id=constraint.get('id', 'unknown'),
                        rule=constraint.get('rule', ''),
                        severity=constraint.get('severity', 'error'),
                        message=f"未找到 AST 模式: {pattern}",
                        file=file_path,
                        suggestion="确保实现符合决策约束的模式"
                    ))
                    
            except:
                pass
        
        return violations
    
    def _check_forbidden_pattern(self, decision: DecisionContract, constraint: dict) -> List[ConstraintViolation]:
        """禁止模式校验"""
        violations = []
        check = constraint.get('check', {})
        pattern = check.get('pattern', '')
        message = check.get('message', '使用了禁止的模式')
        target_files = decision.scope.get('files', [])
        
        for file_path in target_files:
            full_path = PROJECT_ROOT / file_path
            if not full_path.exists():
                continue
            
            try:
                content = full_path.read_text(encoding='utf-8')
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        violations.append(ConstraintViolation(
                            decision_id=decision.id,
                            constraint_id=constraint.get('id', 'unknown'),
                            rule=constraint.get('rule', ''),
                            severity=constraint.get('severity', 'error'),
                            message=message,
                            file=file_path,
                            line=i,
                            suggestion=constraint.get('auto_fix') or "移除禁止的模式"
                        ))
                        
            except:
                pass
        
        return violations
    
    def _check_file_exists(self, decision: DecisionContract, constraint: dict) -> List[ConstraintViolation]:
        """文件存在性校验"""
        violations = []
        check = constraint.get('check', {})
        path = check.get('path', '')
        
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            violations.append(ConstraintViolation(
                decision_id=decision.id,
                constraint_id=constraint.get('id', 'unknown'),
                rule=constraint.get('rule', ''),
                severity='error',
                message=f"必需文件不存在: {path}",
                suggestion=f"创建文件: {path}"
            ))
        
        return violations
    
    def _check_regex_match(self, decision: DecisionContract, constraint: dict) -> List[ConstraintViolation]:
        """正则匹配校验"""
        violations = []
        check = constraint.get('check', {})
        pattern = check.get('pattern', '')
        target_files = check.get('target_files', [])
        
        for file_path in target_files:
            full_path = PROJECT_ROOT / file_path
            if not full_path.exists():
                continue
            
            try:
                content = full_path.read_text(encoding='utf-8')
                if not re.search(pattern, content):
                    violations.append(ConstraintViolation(
                        decision_id=decision.id,
                        constraint_id=constraint.get('id', 'unknown'),
                        rule=constraint.get('rule', ''),
                        severity='error',
                        message=f"未匹配到模式: {pattern}",
                        file=file_path
                    ))
            except:
                pass
        
        return violations
    
    def get_expired_decisions(self) -> List[DecisionContract]:
        """获取已过期的决策"""
        return [d for d in self.decisions.values() if d.is_expired() and d.is_active()]
    
    def get_active_decisions_for_file(self, file_path: str) -> List[DecisionContract]:
        """获取影响指定文件的激活决策"""
        result = []
        for decision in self.decisions.values():
            if not decision.is_active():
                continue
            if file_path in decision.scope.get('files', []):
                result.append(decision)
        return result
    
    def list_decisions(self, status: str = None) -> List[Dict]:
        """列出所有决策"""
        decisions = []
        for d in self.decisions.values():
            if status and d.status != status:
                continue
            decisions.append({
                'id': d.id,
                'title': d.title,
                'type': d.type,
                'status': d.status,
                'constraints_count': len(d.constraints),
                'is_expired': d.is_expired(),
                'created_at': d.data.get('created_at', '')[:10]
            })
        return sorted(decisions, key=lambda x: x['id'])
    
    def deprecate(self, decision_id: str, reason: str = None) -> bool:
        """废弃决策"""
        decision = self.decisions.get(decision_id)
        if not decision:
            return False
        
        decision.status = 'deprecated'
        decision.data['status'] = 'deprecated'
        decision.data['deprecated_at'] = datetime.now().isoformat()
        decision.data['deprecated_reason'] = reason
        decision.save()
        
        print(f"✅ 决策 {decision_id} 已废弃")
        return True
    
    def migrate_from_adr(self, adr_id: str) -> Optional[DecisionContract]:
        """从传统 ADR 迁移为决策契约"""
        adr_path = PROJECT_ROOT / ".kaelis" / "adr" / f"{adr_id}.json"
        
        if not adr_path.exists():
            print(f"❌ ADR {adr_id} 不存在")
            return None
        
        try:
            adr_data = json.loads(adr_path.read_text(encoding='utf-8'))
            
            # 生成新 ID
            new_id = self._generate_id()
            
            # 转换数据
            decision_data = {
                'id': new_id,
                'type': 'architecture_pattern',
                'status': adr_data.get('status', 'proposed'),
                'title': adr_data.get('title', 'Migrated ADR'),
                'description': adr_data.get('context', ''),
                'created_at': adr_data.get('created_at', datetime.now().isoformat()),
                'review_after': (datetime.now() + timedelta(days=90)).isoformat(),
                'scope': {
                    'files': [s.get('path') for s in adr_data.get('linked_symbols', []) if s.get('type') == 'file']
                },
                'constraints': [],
                'rationale': adr_data.get('decision', ''),
                'linked_knowledge': {
                    'adrs': [adr_id]
                }
            }
            
            decision = DecisionContract(decision_data)
            decision.save()
            self.decisions[new_id] = decision
            
            print(f"✅ ADR {adr_id} 已迁移为决策契约 {new_id}")
            print(f"   请编辑 {DECISION_DIR / new_id}.yaml 添加约束条件")
            
            return decision
            
        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            return None


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Decision Contract Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 创建决策契约
  kaelis decision create

  # 激活决策（约束生效）
  kaelis decision activate DEC-20260413-001

  # 校验约束
  kaelis decision verify

  # 列出决策
  kaelis decision list [--status active]

  # 查看过期决策
  kaelis decision expired

  # 从 ADR 迁移
  kaelis decision migrate ADR-20260413-001

  # 废弃决策
  kaelis decision deprecate DEC-20260413-001
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # create 命令
    create_parser = subparsers.add_parser('create', help='Create new decision')
    create_parser.add_argument('--auto', '-a', action='store_true', help='Auto-create without interaction')
    
    # activate 命令
    activate_parser = subparsers.add_parser('activate', help='Activate a decision')
    activate_parser.add_argument('decision_id', help='Decision ID')
    
    # verify 命令
    subparsers.add_parser('verify', help='Verify all active decision constraints')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='List decisions')
    list_parser.add_argument('--status', '-s', choices=['proposed', 'active', 'deprecated'])
    
    # expired 命令
    subparsers.add_parser('expired', help='Show expired decisions')
    
    # migrate 命令
    migrate_parser = subparsers.add_parser('migrate', help='Migrate from ADR')
    migrate_parser.add_argument('adr_id', help='ADR ID to migrate')
    
    # deprecate 命令
    deprecate_parser = subparsers.add_parser('deprecate', help='Deprecate a decision')
    deprecate_parser.add_argument('decision_id', help='Decision ID')
    deprecate_parser.add_argument('--reason', '-r', help='Reason for deprecation')
    
    args = parser.parse_args()
    
    engine = DecisionEngine()
    
    if args.command == 'create':
        decision = engine.create_decision(interactive=not args.auto)
        return 0 if decision else 1
    
    elif args.command == 'activate':
        return 0 if engine.activate(args.decision_id) else 1
    
    elif args.command == 'verify':
        violations = engine.verify_constraints()
        
        print("\n" + "=" * 70)
        print("⚖️  决策约束校验结果")
        print("=" * 70)
        
        if not violations:
            print("\n✅ 所有决策约束均已满足！")
        else:
            print(f"\n❌ 发现 {len(violations)} 处违反:\n")
            
            for v in violations:
                icon = "🚫" if v.severity == 'error' else "⚠️"
                print(f"{icon} [{v.decision_id}/{v.constraint_id}]")
                print(f"   规则: {v.rule}")
                print(f"   消息: {v.message}")
                if v.file:
                    print(f"   文件: {v.file}{f':{v.line}' if v.line else ''}")
                if v.suggestion:
                    print(f"   建议: {v.suggestion}")
                print()
        
        print("=" * 70)
        return 1 if violations else 0
    
    elif args.command == 'list':
        decisions = engine.list_decisions(status=args.status)
        
        print("\n" + "=" * 70)
        print(f"📋 决策列表 ({len(decisions)} 个)")
        print("=" * 70)
        
        status_icons = {
            'proposed': '📝',
            'active': '✅',
            'deprecated': '⚠️'
        }
        
        for d in decisions:
            icon = status_icons.get(d['status'], '❓')
            expired = " [EXPIRED]" if d.get('is_expired') else ""
            print(f"\n{icon} {d['id']}: {d['title']}{expired}")
            print(f"   类型: {d['type']} | 状态: {d['status']} | 约束: {d['constraints_count']}")
            print(f"   创建: {d['created_at']}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'expired':
        expired = engine.get_expired_decisions()
        
        print("\n" + "=" * 70)
        print(f"⏰ 过期决策 ({len(expired)} 个)")
        print("=" * 70)
        
        for d in expired:
            print(f"\n⚠️  {d.id}: {d.title}")
            print(f"   应在 {d.review_after[:10]} 前重新评估")
            print(f"   运行: kaelis decision deprecate {d.id}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'migrate':
        return 0 if engine.migrate_from_adr(args.adr_id) else 1
    
    elif args.command == 'deprecate':
        return 0 if engine.deprecate(args.decision_id, args.reason) else 1
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
