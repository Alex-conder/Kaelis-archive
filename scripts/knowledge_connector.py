#!/usr/bin/env python3
"""
Kaelis Phase 5 - 知识连接层 (Knowledge Connection Layer)
知识条目与代码符号的双向链接系统

核心能力：
1. 为 ADR 和故障条目建立与代码符号的链接
2. 支持从文件查询关联知识
3. 支持从知识查询关联代码
4. 存储于 .kaelis/knowledge_links.json
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
LINKS_FILE = PROJECT_ROOT / ".kaelis" / "knowledge_links.json"


class KnowledgeConnector:
    """知识连接器"""
    
    def __init__(self):
        LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.links: Dict[str, Dict[str, Any]] = {
            'symbol_to_knowledge': defaultdict(list),  # symbol_key -> [knowledge_ids]
            'knowledge_to_symbols': defaultdict(list),  # knowledge_id -> [symbol_keys]
            'file_to_knowledge': defaultdict(list),     # file_path -> [knowledge_ids]
        }
        self._load_links()
    
    def _load_links(self):
        """加载链接数据"""
        if LINKS_FILE.exists():
            data = json.loads(LINKS_FILE.read_text(encoding='utf-8'))
            self.links = {
                'symbol_to_knowledge': defaultdict(list, data.get('symbol_to_knowledge', {})),
                'knowledge_to_symbols': defaultdict(list, data.get('knowledge_to_symbols', {})),
                'file_to_knowledge': defaultdict(list, data.get('file_to_knowledge', {})),
            }
    
    def _save_links(self):
        """保存链接数据"""
        # 转换为普通 dict
        data = {
            k: dict(v) for k, v in self.links.items()
        }
        LINKS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    
    def link_knowledge_to_symbol(
        self,
        knowledge_id: str,
        symbol_type: str,
        symbol_name: str,
        file_path: str
    ):
        """
        建立知识与符号的链接
        
        Args:
            knowledge_id: ADR 或故障条目 ID
            symbol_type: 'function', 'class', 'file'
            symbol_name: 符号名称
            file_path: 文件路径
        """
        symbol_key = f"{file_path}:{symbol_type}:{symbol_name}"
        
        # 双向链接
        if knowledge_id not in self.links['symbol_to_knowledge'][symbol_key]:
            self.links['symbol_to_knowledge'][symbol_key].append(knowledge_id)
        
        if symbol_key not in self.links['knowledge_to_symbols'][knowledge_id]:
            self.links['knowledge_to_symbols'][knowledge_id].append(symbol_key)
        
        # 文件级链接
        if knowledge_id not in self.links['file_to_knowledge'][file_path]:
            self.links['file_to_knowledge'][file_path].append(knowledge_id)
        
        self._save_links()
    
    def get_knowledge_for_file(self, file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取与文件关联的所有知识
        
        Returns:
            {'adrs': [...], 'faults': [...]}
        """
        knowledge_ids = self.links['file_to_knowledge'].get(file_path, [])
        
        result = {'adrs': [], 'faults': []}
        
        for kid in knowledge_ids:
            if kid.startswith('ADR-'):
                adr = self._load_adr(kid)
                if adr:
                    result['adrs'].append(adr)
            elif kid.startswith('FAULT-'):
                fault = self._load_fault(kid)
                if fault:
                    result['faults'].append(fault)
        
        return result
    
    def get_knowledge_for_symbol(self, file_path: str, symbol_type: str, symbol_name: str) -> List[str]:
        """获取与符号关联的知识 ID 列表"""
        symbol_key = f"{file_path}:{symbol_type}:{symbol_name}"
        return self.links['symbol_to_knowledge'].get(symbol_key, [])
    
    def get_symbols_for_knowledge(self, knowledge_id: str) -> List[str]:
        """获取知识条目关联的所有符号"""
        return self.links['knowledge_to_symbols'].get(knowledge_id, [])
    
    def _load_adr(self, adr_id: str) -> Optional[Dict[str, Any]]:
        """加载 ADR"""
        adr_path = PROJECT_ROOT / ".kaelis" / "adr" / f"{adr_id}.json"
        if adr_path.exists():
            return json.loads(adr_path.read_text(encoding='utf-8'))
        return None
    
    def _load_fault(self, fault_id: str) -> Optional[Dict[str, Any]]:
        """加载故障条目"""
        kb_path = PROJECT_ROOT / ".kaelis" / "fault-kb.jsonl"
        if not kb_path.exists():
            return None
        
        for line in kb_path.read_text(encoding='utf-8').strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get('id') == fault_id:
                    return data
            except Exception:
                pass
        
        return None
    
    def auto_link_from_adr(self, adr_id: str):
        """从 ADR 自动建立链接"""
        adr = self._load_adr(adr_id)
        if not adr:
            return
        
        linked_symbols = adr.get('linked_symbols', [])
        for sym in linked_symbols:
            self.link_knowledge_to_symbol(
                knowledge_id=adr_id,
                symbol_type=sym.get('type', 'file'),
                symbol_name=sym.get('name', sym.get('path', 'unknown')),
                file_path=sym.get('file') or sym.get('path', 'unknown')
            )
    
    def auto_link_from_fault(self, fault_id: str):
        """从故障条目自动建立链接"""
        fault = self._load_fault(fault_id)
        if not fault:
            return
        
        linked_symbols = fault.get('linked_symbols', [])
        for sym in linked_symbols:
            self.link_knowledge_to_symbol(
                knowledge_id=fault_id,
                symbol_type=sym.get('type', 'function'),
                symbol_name=sym.get('name', 'unknown'),
                file_path=sym.get('file', 'unknown')
            )
    
    def build_all_links(self):
        """重建所有链接"""
        # 清空现有链接
        self.links = {
            'symbol_to_knowledge': defaultdict(list),
            'knowledge_to_symbols': defaultdict(list),
            'file_to_knowledge': defaultdict(list),
        }
        
        # 链接所有 ADR
        adr_dir = PROJECT_ROOT / ".kaelis" / "adr"
        for adr_file in adr_dir.glob("ADR-*.json"):
            adr_id = adr_file.stem
            self.auto_link_from_adr(adr_id)
        
        # 链接所有故障
        kb_path = PROJECT_ROOT / ".kaelis" / "fault-kb.jsonl"
        if kb_path.exists():
            for line in kb_path.read_text(encoding='utf-8').strip().split('\n'):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    fault_id = data.get('id')
                    if fault_id:
                        self.auto_link_from_fault(fault_id)
                except Exception:
                    pass
        
        self._save_links()
        print(f"✅ 知识链接已重建: {len(self.links['knowledge_to_symbols'])} 个条目")
    
    def print_links_for_file(self, file_path: str):
        """打印文件的关联知识"""
        knowledge = self.get_knowledge_for_file(file_path)
        
        print(f"\n📎 与 `{file_path}` 关联的知识:\n")
        
        if knowledge['faults']:
            print("🔴 相关故障:")
            for fault in sorted(knowledge['faults'], key=lambda x: x.get('importance_score', 0), reverse=True):
                importance = fault.get('importance_score', 0)
                icon = "🔴" if importance >= 0.7 else "🟡" if importance >= 0.4 else "🟢"
                print(f"   {icon} {fault['id']} (重要性: {importance})")
                print(f"      症状: {fault['symptoms'][:50]}{'...' if len(fault['symptoms']) > 50 else ''}")
                print(f"      修复: {fault['fix'][:50]}{'...' if len(fault['fix']) > 50 else ''}")
                if fault.get('fix_command'):
                    print(f"      命令: `{fault['fix_command']}`")
                print()
        
        if knowledge['adrs']:
            print("📝 相关 ADR:")
            for adr in knowledge['adrs']:
                print(f"   📝 {adr['id']}: {adr['title']}")
                print(f"      状态: {adr['status']}")
                print()
        
        if not knowledge['faults'] and not knowledge['adrs']:
            print("   暂无关联知识")


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Knowledge Connector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 查询文件的关联知识
  python scripts/knowledge_connector.py linked-to api/routes/kg.py

  # 重建所有链接
  python scripts/knowledge_connector.py rebuild

  # 链接知识到符号
  python scripts/knowledge_connector.py link FAULT-20260413-001 function extract_triples api/routes/kg.py
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # linked-to 命令
    linked_parser = subparsers.add_parser('linked-to', help='Get knowledge linked to a file')
    linked_parser.add_argument('file_path', help='File path')
    
    # rebuild 命令
    subparsers.add_parser('rebuild', help='Rebuild all knowledge links')
    
    # link 命令
    link_parser = subparsers.add_parser('link', help='Manually link knowledge to symbol')
    link_parser.add_argument('knowledge_id', help='Knowledge ID (ADR-xxx or FAULT-xxx)')
    link_parser.add_argument('symbol_type', choices=['function', 'class', 'file'])
    link_parser.add_argument('symbol_name', help='Symbol name')
    link_parser.add_argument('file_path', help='File path')
    
    args = parser.parse_args()
    
    connector = KnowledgeConnector()
    
    if args.command == 'linked-to':
        connector.print_links_for_file(args.file_path)
        return 0
    
    elif args.command == 'rebuild':
        connector.build_all_links()
        return 0
    
    elif args.command == 'link':
        connector.link_knowledge_to_symbol(
            knowledge_id=args.knowledge_id,
            symbol_type=args.symbol_type,
            symbol_name=args.symbol_name,
            file_path=args.file_path
        )
        print(f"✅ {args.knowledge_id} 已链接到 {args.file_path}:{args.symbol_type}:{args.symbol_name}")
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
