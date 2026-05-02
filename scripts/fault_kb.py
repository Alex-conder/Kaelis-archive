#!/usr/bin/env python3
"""
Kaelis Phase 5 - 故障知识库 (Fault Knowledge Base)
故障经验沉淀系统 - 让历史故障成为可预防的资产

核心能力：
1. 结构化记录故障（症状、诊断、修复）
2. 自动计算重要性评分
3. 自动去重与版本管理
4. 与代码符号双向链接
"""

import os
import sys
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
FAULT_KB_FILE = PROJECT_ROOT / ".kaelis" / "fault-kb.jsonl"
FAULT_INDEX_FILE = PROJECT_ROOT / ".kaelis" / "fault-index.json"


@dataclass
class FaultEntry:
    """故障知识条目"""
    id: str
    symptoms: str
    diagnosis: str
    fix: str
    fix_command: Optional[str]
    file_hashes: Dict[str, str]  # 文件路径 -> hash
    linked_symbols: List[Dict[str, str]]
    occurrence_count: int
    first_occurred_at: str
    last_occurred_at: str
    importance_score: float  # 0-1
    tags: List[str]
    created_at: str
    updated_at: str
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def generate_signature(self) -> str:
        """生成故障签名（用于去重）"""
        content = f"{self.symptoms}:{self.diagnosis}:{self.fix}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


class FaultKnowledgeBase:
    """故障知识库"""
    
    def __init__(self):
        FAULT_KB_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.entries: Dict[str, FaultEntry] = {}
        self._load_entries()
    
    def _load_entries(self):
        """加载所有故障条目"""
        if not FAULT_KB_FILE.exists():
            return
        
        for line in FAULT_KB_FILE.read_text(encoding='utf-8').strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                entry = FaultEntry(**data)
                self.entries[entry.id] = entry
            except Exception:
                pass
    
    def _save_entries(self):
        """保存所有故障条目"""
        lines = []
        for entry in self.entries.values():
            lines.append(json.dumps(entry.to_dict(), ensure_ascii=False))
        
        FAULT_KB_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self._rebuild_index()
    
    def _rebuild_index(self):
        """重建索引"""
        index = {
            'by_file': defaultdict(list),
            'by_symbol': defaultdict(list),
            'by_tag': defaultdict(list),
            'signatures': {}
        }
        
        for entry in self.entries.values():
            # 按文件索引
            for f in entry.file_hashes.keys():
                index['by_file'][f].append(entry.id)
            
            # 按符号索引
            for sym in entry.linked_symbols:
                key = f"{sym.get('file', '')}:{sym.get('name', '')}"
                index['by_symbol'][key].append(entry.id)
            
            # 按标签索引
            for tag in entry.tags:
                index['by_tag'][tag].append(entry.id)
            
            # 签名索引
            index['signatures'][entry.generate_signature()] = entry.id
        
        # 转换为普通 dict 以便 JSON 序列化
        index = {k: dict(v) if isinstance(v, defaultdict) else v for k, v in index.items()}
        
        FAULT_INDEX_FILE.write_text(json.dumps(index, indent=2), encoding='utf-8')
    
    def record(
        self,
        symptoms: str,
        diagnosis: str,
        fix: str,
        fix_command: str = None,
        linked_files: List[str] = None,
        tags: List[str] = None
    ) -> FaultEntry:
        """
        记录新的故障或更新现有故障
        
        Returns:
            FaultEntry: 新创建或更新的故障条目
        """
        now = datetime.now().isoformat()
        
        # 计算文件哈希
        file_hashes = {}
        if linked_files:
            for f in linked_files:
                file_path = PROJECT_ROOT / f
                if file_path.exists():
                    content = file_path.read_bytes()
                    file_hashes[f] = hashlib.sha256(content).hexdigest()[:16]
        
        # 提取代码符号
        linked_symbols = []
        if linked_files:
            for f in linked_files:
                if f.endswith('.py'):
                    symbols = self._extract_symbols_from_file(f)
                    linked_symbols.extend(symbols)
        
        # 生成临时条目用于计算签名
        temp_entry = FaultEntry(
            id="temp",
            symptoms=symptoms,
            diagnosis=diagnosis,
            fix=fix,
            fix_command=fix_command,
            file_hashes=file_hashes,
            linked_symbols=linked_symbols,
            occurrence_count=1,
            first_occurred_at=now,
            last_occurred_at=now,
            importance_score=0.0,
            tags=tags or [],
            created_at=now,
            updated_at=now
        )
        
        signature = temp_entry.generate_signature()
        
        # 检查是否已存在相同故障
        existing_entry = self._find_by_signature(signature)
        
        if existing_entry:
            # 更新现有条目
            existing_entry.occurrence_count += 1
            existing_entry.last_occurred_at = now
            existing_entry.importance_score = self._calculate_importance(existing_entry)
            existing_entry.updated_at = now
            
            # 合并文件哈希（保留最新的）
            existing_entry.file_hashes.update(file_hashes)
            
            self._save_entries()
            print(f"📝 故障记录已更新 (发生次数: {existing_entry.occurrence_count})")
            return existing_entry
        
        else:
            # 创建新条目
            entry_id = f"FAULT-{datetime.now().strftime('%Y%m%d')}-{len(self.entries) + 1:03d}"
            
            entry = FaultEntry(
                id=entry_id,
                symptoms=symptoms,
                diagnosis=diagnosis,
                fix=fix,
                fix_command=fix_command,
                file_hashes=file_hashes,
                linked_symbols=linked_symbols,
                occurrence_count=1,
                first_occurred_at=now,
                last_occurred_at=now,
                importance_score=self._calculate_importance(temp_entry),
                tags=tags or self._auto_extract_tags(symptoms, diagnosis),
                created_at=now,
                updated_at=now
            )
            
            self.entries[entry_id] = entry
            self._save_entries()
            print(f"✅ 新故障已记录: {entry_id}")
            return entry
    
    def _find_by_signature(self, signature: str) -> Optional[FaultEntry]:
        """通过签名查找故障条目"""
        if FAULT_INDEX_FILE.exists():
            index = json.loads(FAULT_INDEX_FILE.read_text())
            entry_id = index.get('signatures', {}).get(signature)
            if entry_id:
                return self.entries.get(entry_id)
        return None
    
    def _calculate_importance(self, entry: FaultEntry) -> float:
        """
        计算故障重要性评分 (0-1)
        
        考虑因素：
        - 发生次数 (40%)
        - 影响核心 API (30%)
        - 最近发生时间 (20%)
        - 修复复杂度 (10%)
        """
        score = 0.0
        
        # 1. 发生次数 (对数衰减)
        occurrence_score = min(1.0, (entry.occurrence_count / 5) ** 0.5)
        score += occurrence_score * 0.4
        
        # 2. 影响核心 API
        core_patterns = ['api/routes', 'api/models', 'core/']
        is_core = any(any(p in s.get('file', '') for p in core_patterns) 
                     for s in entry.linked_symbols)
        score += 0.3 if is_core else 0.0
        
        # 3. 最近发生时间 (越近越重要)
        try:
            last_time = datetime.fromisoformat(entry.last_occurred_at)
            days_ago = (datetime.now() - last_time).days
            recency_score = max(0, 1 - days_ago / 30)  # 30 天内线性衰减
            score += recency_score * 0.2
        except Exception:
            pass
        
        # 4. 修复复杂度（简单命令修复得分低）
        if entry.fix_command and len(entry.fix_command) < 50:
            score += 0.05
        else:
            score += 0.1
        
        return round(score, 2)
    
    def _extract_symbols_from_file(self, file_path: str) -> List[Dict[str, str]]:
        """从文件中提取代码符号"""
        symbols = []
        full_path = PROJECT_ROOT / file_path
        
        if not full_path.exists():
            return symbols
        
        try:
            content = full_path.read_text(encoding='utf-8')
            
            # 简单正则提取函数和类定义
            # 函数
            for match in re.finditer(r'def\s+(\w+)', content):
                symbols.append({
                    'type': 'function',
                    'name': match.group(1),
                    'file': file_path
                })
            
            # 类
            for match in re.finditer(r'class\s+(\w+)', content):
                symbols.append({
                    'type': 'class',
                    'name': match.group(1),
                    'file': file_path
                })
                
        except Exception:
            pass
        
        return symbols
    
    def _auto_extract_tags(self, symptoms: str, diagnosis: str) -> List[str]:
        """自动提取标签"""
        tags = []
        text = f"{symptoms} {diagnosis}".lower()
        
        # 关键词映射
        tag_map = {
            'timeout': ['timeout', '超时', 'timed out'],
            'memory': ['memory', '内存', 'oom', 'out of memory'],
            'database': ['database', 'db', 'neo4j', 'mysql', 'postgres'],
            'network': ['network', 'connection', '网络', '连接'],
            'performance': ['slow', 'performance', '慢', '性能'],
            'error': ['error', 'exception', '错误', '异常'],
        }
        
        for tag, keywords in tag_map.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags
    
    def lookup(self, query: str = None, file_path: str = None, min_importance: float = 0.0) -> List[FaultEntry]:
        """
        查询故障知识库
        
        Args:
            query: 文本查询（匹配症状或诊断）
            file_path: 文件路径过滤
            min_importance: 最小重要性评分
        """
        results = []
        
        # 按文件路径查找
        if file_path:
            if FAULT_INDEX_FILE.exists():
                index = json.loads(FAULT_INDEX_FILE.read_text())
                entry_ids = index.get('by_file', {}).get(file_path, [])
                for eid in entry_ids:
                    entry = self.entries.get(eid)
                    if entry and entry.importance_score >= min_importance:
                        results.append(entry)
        
        # 文本查询
        elif query:
            query_lower = query.lower()
            for entry in self.entries.values():
                if entry.importance_score < min_importance:
                    continue
                
                match = (
                    query_lower in entry.symptoms.lower() or
                    query_lower in entry.diagnosis.lower() or
                    query_lower in entry.fix.lower() or
                    any(query_lower in t for t in entry.tags)
                )
                
                if match:
                    results.append(entry)
        
        # 返回所有（按重要性排序）
        else:
            results = [e for e in self.entries.values() if e.importance_score >= min_importance]
        
        # 按重要性排序
        results.sort(key=lambda x: x.importance_score, reverse=True)
        
        return results
    
    def get_by_id(self, fault_id: str) -> Optional[FaultEntry]:
        """通过 ID 获取故障条目"""
        return self.entries.get(fault_id)
    
    def deduplicate(self) -> int:
        """
        去重处理
        
        Returns:
            int: 合并的重复条目数
        """
        signatures = {}
        to_merge = []
        
        for entry in self.entries.values():
            sig = entry.generate_signature()
            if sig in signatures:
                to_merge.append((entry.id, signatures[sig]))
            else:
                signatures[sig] = entry.id
        
        # 合并重复项
        for dup_id, keep_id in to_merge:
            dup_entry = self.entries.pop(dup_id)
            keep_entry = self.entries[keep_id]
            
            keep_entry.occurrence_count += dup_entry.occurrence_count
            keep_entry.file_hashes.update(dup_entry.file_hashes)
            keep_entry.importance_score = self._calculate_importance(keep_entry)
        
        if to_merge:
            self._save_entries()
        
        return len(to_merge)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.entries)
        
        if total == 0:
            return {'total': 0}
        
        occurrence_distribution = defaultdict(int)
        tag_distribution = defaultdict(int)
        high_importance = 0
        
        for entry in self.entries.values():
            occurrence_distribution[min(entry.occurrence_count, 5)] += 1
            for tag in entry.tags:
                tag_distribution[tag] += 1
            if entry.importance_score >= 0.7:
                high_importance += 1
        
        return {
            'total': total,
            'high_importance': high_importance,
            'occurrence_distribution': dict(occurrence_distribution),
            'top_tags': dict(sorted(tag_distribution.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    
    def verify_freshness(self) -> List[Dict[str, Any]]:
        """验证知识新鲜度，返回过时条目"""
        stale_entries = []
        
        for entry in self.entries.values():
            stale_symbols = []
            
            for f, old_hash in entry.file_hashes.items():
                file_path = PROJECT_ROOT / f
                if not file_path.exists():
                    stale_symbols.append({'type': 'file_deleted', 'path': f})
                else:
                    current_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]
                    if current_hash != old_hash:
                        stale_symbols.append({
                            'type': 'file_modified',
                            'path': f,
                            'old_hash': old_hash,
                            'new_hash': current_hash
                        })
            
            if stale_symbols:
                stale_entries.append({
                    'entry_id': entry.id,
                    'symptoms': entry.symptoms[:50],
                    'stale_symbols': stale_symbols,
                    'importance_score': entry.importance_score
                })
        
        # 按重要性排序
        stale_entries.sort(key=lambda x: x['importance_score'], reverse=True)
        
        return stale_entries


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Fault Knowledge Base',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 记录新故障
  python scripts/fault_kb.py record \\
    --symptoms "Neo4j 连接超时" \\
    --diagnosis "内存不足导致查询阻塞" \\
    --fix "重启 Neo4j 容器" \\
    --fix-command "docker-compose restart neo4j" \\
    --linked-files "api/routes/kg.py" \\
    --tags "database,timeout"

  # 查询故障
  python scripts/fault_kb.py lookup --file api/routes/kg.py
  python scripts/fault_kb.py lookup --query "timeout"

  # 显示统计
  python scripts/fault_kb.py stats

  # 验证知识新鲜度
  python scripts/fault_kb.py verify
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # record 命令
    record_parser = subparsers.add_parser('record', help='Record a new fault')
    record_parser.add_argument('--symptoms', '-s', required=True, help='Fault symptoms')
    record_parser.add_argument('--diagnosis', '-d', required=True, help='Root cause diagnosis')
    record_parser.add_argument('--fix', '-f', required=True, help='Fix description')
    record_parser.add_argument('--fix-command', '-c', help='Command to fix')
    record_parser.add_argument('--linked-files', '-l', nargs='+', help='Related files')
    record_parser.add_argument('--tags', '-t', nargs='+', help='Tags')
    
    # lookup 命令
    lookup_parser = subparsers.add_parser('lookup', help='Lookup faults')
    lookup_parser.add_argument('--query', '-q', help='Text query')
    lookup_parser.add_argument('--file', '-f', help='File path filter')
    lookup_parser.add_argument('--min-importance', '-i', type=float, default=0.0, help='Min importance score')
    
    # stats 命令
    subparsers.add_parser('stats', help='Show statistics')
    
    # verify 命令
    subparsers.add_parser('verify', help='Verify knowledge freshness')
    
    # list 命令
    subparsers.add_parser('list', help='List all faults')
    
    args = parser.parse_args()
    
    kb = FaultKnowledgeBase()
    
    if args.command == 'record':
        entry = kb.record(
            symptoms=args.symptoms,
            diagnosis=args.diagnosis,
            fix=args.fix,
            fix_command=args.fix_command,
            linked_files=args.linked_files,
            tags=args.tags
        )
        print(f"\n📊 重要性评分: {entry.importance_score}")
        print(f"🏷️  自动标签: {', '.join(entry.tags)}")
        return 0
    
    elif args.command == 'lookup':
        results = kb.lookup(
            query=args.query,
            file_path=args.file,
            min_importance=args.min_importance
        )
        
        print("\n" + "=" * 70)
        print(f"🔍 查询结果 ({len(results)} 条)")
        print("=" * 70)
        
        for entry in results:
            importance_icon = "🔴" if entry.importance_score >= 0.7 else "🟡" if entry.importance_score >= 0.4 else "🟢"
            print(f"\n{importance_icon} {entry.id} (重要性: {entry.importance_score})")
            print(f"   症状: {entry.symptoms[:60]}{'...' if len(entry.symptoms) > 60 else ''}")
            print(f"   诊断: {entry.diagnosis[:60]}{'...' if len(entry.diagnosis) > 60 else ''}")
            print(f"   修复: {entry.fix[:60]}{'...' if len(entry.fix) > 60 else ''}")
            print(f"   发生次数: {entry.occurrence_count}")
            print(f"   标签: {', '.join(entry.tags)}")
            if entry.fix_command:
                print(f"   命令: {entry.fix_command}")
        
        print("\n" + "=" * 70)
        return 0
    
    elif args.command == 'stats':
        stats = kb.get_stats()
        
        print("\n" + "=" * 50)
        print("📊 故障知识库统计")
        print("=" * 50)
        print(f"\n总条目数: {stats['total']}")
        print(f"高重要性: {stats.get('high_importance', 0)}")
        
        if 'occurrence_distribution' in stats:
            print("\n发生次数分布:")
            for count, num in sorted(stats['occurrence_distribution'].items()):
                label = f"{count} 次" if count < 5 else "5+ 次"
                print(f"  {label}: {num} 条")
        
        if 'top_tags' in stats:
            print("\n热门标签:")
            for tag, count in stats['top_tags'].items():
                print(f"  #{tag}: {count}")
        
        print("\n" + "=" * 50)
        return 0
    
    elif args.command == 'verify':
        stale = kb.verify_freshness()
        
        print("\n" + "=" * 70)
        print("🔍 知识新鲜度验证")
        print("=" * 70)
        
        if not stale:
            print("\n✅ 所有知识条目都是新鲜的！")
        else:
            print(f"\n⚠️  发现 {len(stale)} 个可能过时的条目:\n")
            
            for item in stale:
                print(f"🔴 {item['entry_id']} (重要性: {item['importance_score']})")
                print(f"   症状: {item['symptoms']}")
                for sym in item['stale_symbols']:
                    if sym['type'] == 'file_deleted':
                        print(f"   ❌ 文件已删除: {sym['path']}")
                    else:
                        print(f"   ⚠️  文件已修改: {sym['path']}")
                print()
        
        print("=" * 70)
        return 0
    
    elif args.command == 'list':
        entries = sorted(kb.entries.values(), key=lambda x: x.importance_score, reverse=True)
        
        print("\n" + "=" * 70)
        print(f"📋 故障知识库 ({len(entries)} 条)")
        print("=" * 70)
        
        for entry in entries:
            importance_icon = "🔴" if entry.importance_score >= 0.7 else "🟡" if entry.importance_score >= 0.4 else "🟢"
            print(f"\n{importance_icon} {entry.id} (重要性: {entry.importance_score})")
            print(f"   症状: {entry.symptoms[:50]}")
            print(f"   发生: {entry.occurrence_count} 次 | 标签: {', '.join(entry.tags)}")
        
        print("\n" + "=" * 70)
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
