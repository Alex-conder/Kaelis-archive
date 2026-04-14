#!/usr/bin/env python3
"""
Kaelis ACK v2.1 - 需求工厂 v2 (Idea Factory v2)
功能: 前馈确定性认知内核的主入口

执行流程:
1. 语义解析 (LLM) → 结构化意图 (JSON Schema 校验)
2. 规则匹配 → 确定性执行计划
3. 幻觉检测 → 拦截不存在的实体引用
4. 沙箱预演 → 隔离验证
5. 原子执行 → 全态快照 + 审计链

作者: Kaelis ACK v2.1
版本: 2.1.0
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# 导入 v2.1 组件
try:
    from rule_engine import RuleEngine, MatchResult
    from hallucination_detector import HallucinationDetector
    from sandbox_runner import SandboxRunner
    from atomic_executor import AtomicExecutor
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Failed to import components: {e}")
    COMPONENTS_AVAILABLE = False


class IntentParser:
    """
    结构化意图解析器
    
    将自然语言转换为结构化 JSON，必须通过 Schema 校验。
    实际生产环境中，这里会调用 LLM 进行解析。
    """
    
    SCHEMA_FILE = Path("config/intent_schema.json")
    
    def __init__(self):
        self.schema = self._load_schema()
    
    def _load_schema(self) -> Dict:
        """加载 JSON Schema"""
        if not self.SCHEMA_FILE.exists():
            raise FileNotFoundError(f"Schema file not found: {self.SCHEMA_FILE}")
        
        with open(self.SCHEMA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def parse(self, natural_language: str) -> Optional[Dict]:
        """
        解析自然语言为结构化意图
        
        简化实现: 基于关键词匹配
        实际实现: 调用 LLM API 生成 JSON
        """
        print(f"[IntentParser] Parsing: {natural_language}")
        
        # 简单关键词匹配 (模拟 LLM 解析)
        intent = self._keyword_based_parse(natural_language)
        
        # 验证
        if self._validate_intent(intent):
            print(f"[IntentParser] Valid intent generated")
            return intent
        else:
            print(f"[IntentParser] Failed to generate valid intent")
            return None
    
    def _keyword_based_parse(self, text: str) -> Dict:
        """基于关键词的意图解析 (简化版)"""
        text_lower = text.lower()
        
        # 默认意图
        intent = {
            "version": "2.1",
            "action": "query",
            "target": {
                "type": "config",
                "path": "config/default.yaml"
            },
            "parameters": {},
            "constraints": [],
            "metadata": {
                "original_query": text,
                "timestamp": "2026-04-12T12:00:00Z",
                "session_id": "test-session",
                "confidence": 0.8
            },
            "validation": {
                "syntax_check": True,
                "test_execution": True,
                "sandbox_prerun": True
            }
        }
        
        # 解析动作类型
        if any(kw in text_lower for kw in ['add', '增加', '添加', 'create', '新建']):
            intent['action'] = 'add'
        elif any(kw in text_lower for kw in ['modify', '修改', '更新', 'change', 'update']):
            intent['action'] = 'modify'
        elif any(kw in text_lower for kw in ['delete', '删除', '移除', 'remove']):
            intent['action'] = 'delete'
        elif any(kw in text_lower for kw in ['test', '测试']):
            intent['action'] = 'test'
        
        # 解析目标类型
        if any(kw in text_lower for kw in ['api', 'route', 'endpoint', '接口', '路由']):
            intent['target']['type'] = 'api_route'
            intent['target']['path'] = 'api/routes/new_module.py'
        elif any(kw in text_lower for kw in ['config', '配置']):
            intent['target']['type'] = 'config'
            intent['target']['path'] = 'config/settings.yaml'
        elif any(kw in text_lower for kw in ['agent', 'tool', '工具']):
            intent['target']['type'] = 'agent_tool'
            intent['target']['path'] = 'agent/tools/new_tool.py'
        elif any(kw in text_lower for kw in ['database', 'db', 'model', '数据库', '模型']):
            intent['target']['type'] = 'database'
            intent['target']['path'] = 'api/models/new_model.py'
        
        # 解析实体名称
        import re
        # 尝试提取引号内的名称
        name_match = re.search(r'["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']', text)
        if name_match:
            intent['target']['entity_name'] = name_match.group(1)
        
        # 特殊处理: 超时配置
        if 'timeout' in text_lower or '超时' in text:
            intent['parameters']['timeout'] = 30
        
        return intent
    
    def _validate_intent(self, intent: Dict) -> bool:
        """
        验证意图是否符合 Schema
        
        简化版验证，检查必需字段
        """
        required = self.schema.get('required', [])
        for field in required:
            if field not in intent:
                print(f"[SchemaValidation] Missing required field: {field}")
                return False
        
        # 验证 action 枚举
        valid_actions = self.schema.get('properties', {}).get('action', {}).get('enum', [])
        if intent.get('action') not in valid_actions:
            print(f"[SchemaValidation] Invalid action: {intent.get('action')}")
            return False
        
        # 验证 target
        target = intent.get('target', {})
        target_schema = self.schema.get('properties', {}).get('target', {})
        target_required = target_schema.get('required', [])
        for field in target_required:
            if field not in target:
                print(f"[SchemaValidation] Missing target field: {field}")
                return False
        
        return True


class IdeaFactoryV2:
    """
    需求工厂 v2.1
    
    前馈确定性流水线的主控制器。
    """
    
    def __init__(self):
        self.intent_parser = IntentParser()
        self.rule_engine = RuleEngine() if COMPONENTS_AVAILABLE else None
        self.hallucination_detector = HallucinationDetector() if COMPONENTS_AVAILABLE else None
        self.sandbox_runner = None  # 按需创建
        self.atomic_executor = None  # 按需创建
    
    def process(self, natural_language: str, dry_run: bool = False, skip_sandbox: bool = False) -> bool:
        """
        处理自然语言需求
        
        完整流水线:
        1. 语义解析
        2. 规则匹配
        3. 幻觉检测
        4. 沙箱预演
        5. 原子执行
        
        Args:
            natural_language: 自然语言描述
            dry_run: 是否仅模拟执行
            skip_sandbox: 是否跳过沙箱预演
        
        Returns:
            bool: 是否成功
        """
        print("\n" + "=" * 70)
        print("  Kaelis ACK v2.1 - Forward-Deterministic Cognitive Kernel")
        print("=" * 70)
        
        # Step 1: 语义解析
        print("\n[Step 1] Semantic Parsing")
        print("-" * 40)
        intent = self.intent_parser.parse(natural_language)
        if not intent:
            print("[FAIL] Failed to parse intent. Please refine your description.")
            return False
        
        print(f"  Action: {intent['action']}")
        print(f"  Target: {intent['target']['type']} - {intent['target']['path']}")
        if 'entity_name' in intent['target']:
            print(f"  Entity: {intent['target']['entity_name']}")
        
        # Step 2: 规则匹配
        print("\n[Step 2] Rule Engine Matching")
        print("-" * 40)
        
        if not self.rule_engine:
            print("[FAIL] Rule engine not available")
            return False
        
        template, matches = self.rule_engine.match_intent(intent)
        
        if not template:
            guidance = self.rule_engine.get_no_match_guidance()
            print(f"[FAIL] No matching template found")
            print(f"  Guidance: {guidance}")
            return False
        
        if matches[0].result == MatchResult.AMBIGUOUS:
            print(f"[WARN] Multiple matching templates detected:")
            for m in matches[:3]:
                print(f"  - {m.template_name}: {m.match_score:.1%}")
            print("[FAIL] Please refine your request to be more specific")
            return False
        
        print(f"  [OK] Matched template: {template['name']} ({matches[0].match_score:.1%})")
        
        # 生成执行计划
        execution_plan = self.rule_engine.generate_execution_plan(template, intent)
        
        # Step 3: 幻觉检测
        print("\n[Step 3] Hallucination Detection")
        print("-" * 40)
        
        if not self.hallucination_detector:
            print("[WARN] Hallucination detector not available")
        else:
            report = self.hallucination_detector.validate_execution_plan(execution_plan)
            
            if report.hallucinations:
                print(f"  [FAIL] Hallucinations detected:")
                for h in report.hallucinations:
                    print(f"    - [{h['type']}] {h['message']}")
                print("\n[BLOCKED] Execution blocked. Please correct the hallucinated references.")
                return False
            
            if report.warnings:
                print(f"  [WARN] Warnings:")
                for w in report.warnings:
                    print(f"    - {w}")
            
            print(f"  [OK] No hallucinations detected ({report.checked_items} items checked)")
        
        # 显示执行计划
        print(f"\n  Execution Plan:")
        print(f"    Risk Level: {execution_plan['risk_level']}")
        print(f"    Requires Confirmation: {execution_plan['requires_confirmation']}")
        print(f"    Steps ({len(execution_plan['steps'])}):")
        for step in execution_plan['steps']:
            print(f"      {step['step']}. {step['type']}")
        
        # 需要确认的操作
        if execution_plan['requires_confirmation'] and not dry_run:
            print(f"\n[CONFIRMATION REQUIRED]")
            response = input("This operation requires confirmation. Proceed? (yes/no): ")
            if response.lower() != 'yes':
                print("[CANCELLED] Operation cancelled by user")
                return False
        
        if dry_run:
            print(f"\n[DRY-RUN] Execution plan validated. No changes made.")
            return True
        
        # Step 4: 沙箱预演
        if not skip_sandbox:
            print("\n[Step 4] Sandbox Pre-execution")
            print("-" * 40)
            
            self.sandbox_runner = SandboxRunner()
            
            if not self.sandbox_runner.prepare_sandbox(execution_plan):
                print("[FAIL] Failed to prepare sandbox")
                return False
            
            sandbox_result = self.sandbox_runner.run_sandbox()
            
            if sandbox_result.status.value != 'success':
                print(f"  [FAIL] Sandbox execution failed")
                print(f"    Status: {sandbox_result.status.value}")
                print(f"    Error: {sandbox_result.error_details}")
                self.sandbox_runner.cleanup()
                return False
            
            print(f"  [OK] Sandbox execution successful")
            print(f"    Checks passed: {sandbox_result.checks_passed}")
            print(f"    Duration: {sandbox_result.duration_ms}ms")
            
            self.sandbox_runner.cleanup()
        else:
            print("\n[Step 4] Sandbox Pre-execution (SKIPPED)")
        
        # Step 5: 原子执行
        print("\n[Step 5] Atomic Execution")
        print("-" * 40)
        
        self.atomic_executor = AtomicExecutor()
        
        try:
            record = self.atomic_executor.execute(execution_plan)
            
            print(f"  [OK] Execution successful")
            print(f"    Execution ID: {record.execution_id}")
            print(f"    Snapshot: {record.snapshot_path}")
            print(f"    Modified files: {len(record.modified_files)}")
            
            return True
            
        except Exception as e:
            print(f"  [FAIL] Execution failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Kaelis ACK v2.1 - Idea Factory (Forward-Deterministic)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 解析需求并执行
  %(prog)s "增加 API 超时配置"
  
  # 仅验证执行计划（不执行）
  %(prog)s "添加用户认证接口" --dry-run
  
  # 跳过沙箱预演
  %(prog)s "修改数据库配置" --skip-sandbox
  
  # 查看可用模板
  %(prog)s --list-templates
        """
    )
    
    parser.add_argument('description', nargs='?', help='Natural language description of the task')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Validate only, do not execute')
    parser.add_argument('--skip-sandbox', action='store_true', help='Skip sandbox pre-execution')
    parser.add_argument('--list-templates', '-l', action='store_true', help='List available templates')
    
    args = parser.parse_args()
    
    factory = IdeaFactoryV2()
    
    if args.list_templates:
        if factory.rule_engine:
            print("Available Templates:")
            print("=" * 60)
            for t in factory.rule_engine.list_templates():
                print(f"\n{t['id']}: {t['name']}")
                print(f"  Description: {t['description']}")
        else:
            print("[FAIL] Rule engine not available")
            return 1
    
    elif args.description:
        success = factory.process(
            args.description,
            dry_run=args.dry_run,
            skip_sandbox=args.skip_sandbox
        )
        return 0 if success else 1
    
    else:
        parser.print_help()


if __name__ == "__main__":
    sys.exit(main())
