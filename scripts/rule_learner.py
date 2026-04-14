#!/usr/bin/env python3
"""
Kaelis v2.0 - 自适应规则学习器 (Rule Learner)
功能: 从成功会话中提炼新模板

设计原则:
- 从审计日志学习，而非从 LLM 臆测
- 高频成功模式自动发现
- 人工审核后再采纳，确保质量

作者: Kaelis v2.0
版本: 2.0.0
"""

import json
import yaml
import hashlib
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass


# 路径配置
AUDIT_DIR = Path(".kaelis/audit")
TEMPLATE_FILE = Path("config/action_templates.yaml")
PENDING_DIR = Path("config/templates/pending")
APPROVED_DIR = Path("config/templates/approved")


@dataclass
class OperationPattern:
    """操作模式"""
    op_types: Tuple[str, ...]
    target_types: Tuple[str, ...]
    target_paths: Tuple[str, ...]
    frequency: int = 0
    success_count: int = 0
    
    def to_key(self) -> str:
        """生成唯一键"""
        content = f"{'|'.join(self.op_types)}:{':'.join(self.target_types)}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


class RuleLearner:
    """
    规则学习器
    
    从成功会话中发现高频操作模式，生成待审核的规则模板。
    """
    
    def __init__(self, min_frequency: int = 3, min_success_rate: float = 0.9):
        self.min_frequency = min_frequency
        self.min_success_rate = min_success_rate
        
        # 确保目录存在
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    
    def load_audit_entries(self) -> List[Dict]:
        """加载所有审计条目"""
        entries = []
        
        if not AUDIT_DIR.exists():
            return entries
        
        for audit_file in sorted(AUDIT_DIR.glob("op-*.jsonl")):
            with open(audit_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            entries.append(entry)
                        except json.JSONDecodeError:
                            continue
        
        return entries
    
    def group_by_session(self, entries: List[Dict]) -> Dict[str, List[Dict]]:
        """按会话分组"""
        sessions = defaultdict(list)
        for entry in entries:
            session_id = entry.get('session_id', 'unknown')
            sessions[session_id].append(entry)
        return dict(sessions)
    
    def extract_patterns(self, sessions: Dict[str, List[Dict]]) -> List[OperationPattern]:
        """提取操作模式"""
        pattern_counter = Counter()
        pattern_success = defaultdict(int)
        
        for session_id, ops in sessions.items():
            if len(ops) < 1:
                continue
            
            # 提取操作序列
            op_types = tuple(op.get('operation', 'unknown') for op in ops)
            target_types = tuple(op.get('target', {}).get('type', 'unknown') for op in ops)
            target_paths = tuple(op.get('target', {}).get('path', 'unknown') for op in ops)
            
            pattern = OperationPattern(
                op_types=op_types,
                target_types=target_types,
                target_paths=target_paths
            )
            
            key = pattern.to_key()
            pattern_counter[key] += 1
            
            # 统计成功次数
            all_success = all(op.get('result') == 'success' for op in ops)
            if all_success:
                pattern_success[key] += 1
        
        # 筛选高频模式
        patterns = []
        for key, freq in pattern_counter.items():
            if freq >= self.min_frequency:
                success_rate = pattern_success[key] / freq
                if success_rate >= self.min_success_rate:
                    # 重新构造 pattern
                    for session_id, ops in sessions.items():
                        if len(ops) >= 1:
                            op_types = tuple(op.get('operation', 'unknown') for op in ops)
                            target_types = tuple(op.get('target', {}).get('type', 'unknown') for op in ops)
                            target_paths = tuple(op.get('target', {}).get('path', 'unknown') for op in ops)
                            
                            test_pattern = OperationPattern(
                                op_types=op_types,
                                target_types=target_types,
                                target_paths=target_paths
                            )
                            if test_pattern.to_key() == key:
                                pattern = test_pattern
                                pattern.frequency = freq
                                pattern.success_count = pattern_success[key]
                                patterns.append(pattern)
                                break
        
        return patterns
    
    def generate_template(self, pattern: OperationPattern) -> Dict:
        """从模式生成模板"""
        # 推断意图短语
        intent_phrases = self._infer_intent_phrases(pattern)
        
        # 生成操作步骤
        operations = []
        for i, (op_type, target_type, target_path) in enumerate(
            zip(pattern.op_types, pattern.target_types, pattern.target_paths), 1
        ):
            operations.append({
                'step': i,
                'type': self._map_op_type(op_type),
                'params': {
                    'target_type': target_type,
                    'target_path': target_path
                }
            })
        
        # 构建模板
        template = {
            'id': f"learned_{pattern.to_key()}",
            'name': f"Learned Pattern ({pattern.frequency} occurrences)",
            'description': f"Auto-discovered from {pattern.frequency} successful sessions",
            'intent_patterns': intent_phrases,
            'required_intent': {
                'action': self._infer_action(pattern.op_types),
                'target': {
                    'type': pattern.target_types[0] if pattern.target_types else 'unknown'
                }
            },
            'operations': operations,
            'validation': {
                'pre_checks': [{'type': 'file_exists'}],
                'post_checks': [{'type': 'syntax_check'}]
            },
            'metadata': {
                'discovered_at': datetime.now().isoformat(),
                'frequency': pattern.frequency,
                'success_count': pattern.success_count,
                'success_rate': pattern.success_count / pattern.frequency,
                'status': 'pending_review',
                'source': 'rule_learner'
            }
        }
        
        return template
    
    def _infer_intent_phrases(self, pattern: OperationPattern) -> List[str]:
        """推断意图短语"""
        phrases = []
        
        # 基于目标路径推断
        paths_str = ' '.join(pattern.target_paths)
        
        if 'api/routes' in paths_str:
            phrases.append("增加.*API")
            phrases.append("添加.*路由")
        
        if '.env' in paths_str:
            phrases.append("配置.*环境变量")
            phrases.append("设置.*env")
        
        if 'config' in paths_str:
            phrases.append("修改.*配置")
            phrases.append("更新.*设置")
        
        if 'test' in paths_str:
            phrases.append("添加.*测试")
            phrases.append("创建.*test")
        
        if 'model' in paths_str or 'db' in paths_str:
            phrases.append("添加.*模型")
            phrases.append("创建.*数据库")
        
        return phrases or ["通用操作"]
    
    def _infer_action(self, op_types: Tuple[str, ...]) -> str:
        """推断动作类型"""
        action_map = {
            'file_add': 'add',
            'file_modify': 'modify',
            'file_delete': 'delete',
            'config_update': 'configure',
            'test_run': 'test',
            'db_migrate': 'migrate'
        }
        
        for op in op_types:
            if op in action_map:
                return action_map[op]
        
        return 'modify'
    
    def _map_op_type(self, op_type: str) -> str:
        """映射操作类型"""
        mapping = {
            'file_add': 'create_file',
            'file_modify': 'modify_file',
            'file_delete': 'delete_file',
            'config_update': 'yaml_modify',
            'test_run': 'run_tests',
            'db_migrate': 'run_migration'
        }
        return mapping.get(op_type, op_type)
    
    def _template_exists(self, template: Dict) -> bool:
        """检查模板是否已存在"""
        # 检查正式模板
        if TEMPLATE_FILE.exists():
            with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f) or {}
            
            for t in existing.get('templates', []):
                if t.get('operations') == template['operations']:
                    return True
        
        # 检查待审模板
        for pending_file in PENDING_DIR.glob("*.yaml"):
            with open(pending_file, 'r', encoding='utf-8') as f:
                pending = yaml.safe_load(f) or {}
            
            if pending.get('operations') == template['operations']:
                return True
        
        return False
    
    def save_template(self, template: Dict):
        """保存待审模板"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        template_id = template['id']
        filename = f"{template_id}_{timestamp}.yaml"
        
        filepath = PENDING_DIR / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(template, f, allow_unicode=True, default_flow_style=False)
        
        return filepath
    
    def run(self):
        """运行规则学习"""
        print("=" * 60)
        print("Kaelis Rule Learner v2.0")
        print("=" * 60)
        
        # 加载审计数据
        entries = self.load_audit_entries()
        if len(entries) < 5:
            print(f"\n[SKIP] Insufficient audit data: {len(entries)} entries")
            print("       Need at least 5 entries to learn patterns")
            return
        
        print(f"\n[OK] Loaded {len(entries)} audit entries")
        
        # 按会话分组
        sessions = self.group_by_session(entries)
        print(f"[OK] Grouped into {len(sessions)} sessions")
        
        # 提取模式
        patterns = self.extract_patterns(sessions)
        print(f"[OK] Found {len(patterns)} high-frequency patterns")
        
        # 生成模板
        new_templates = 0
        for pattern in patterns:
            template = self.generate_template(pattern)
            
            if self._template_exists(template):
                print(f"  [SKIP] Template already exists for pattern {pattern.to_key()}")
                continue
            
            filepath = self.save_template(template)
            new_templates += 1
            
            print(f"\n  [NEW] Pattern discovered:")
            print(f"        Frequency: {pattern.frequency} times")
            print(f"        Success rate: {pattern.success_count / pattern.frequency:.1%}")
            print(f"        Intent patterns: {', '.join(template['intent_patterns'][:2])}")
            print(f"        Saved to: {filepath}")
        
        print(f"\n" + "=" * 60)
        print(f"Learning complete: {new_templates} new templates pending review")
        print("=" * 60)
        
        if new_templates > 0:
            print(f"\nTo review templates:")
            print(f"  kaelis template list --pending")
            print(f"  kaelis template approve <id>")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kaelis Rule Learner - Discover patterns from successful sessions"
    )
    parser.add_argument('--min-frequency', '-f', type=int, default=3,
                       help='Minimum frequency to consider a pattern (default: 3)')
    parser.add_argument('--min-success-rate', '-s', type=float, default=0.9,
                       help='Minimum success rate (default: 0.9)')
    
    args = parser.parse_args()
    
    learner = RuleLearner(
        min_frequency=args.min_frequency,
        min_success_rate=args.min_success_rate
    )
    learner.run()


if __name__ == "__main__":
    main()
