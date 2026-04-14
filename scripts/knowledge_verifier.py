#!/usr/bin/env python3
"""
Kaelis Phase 5 - 知识验证器 (Knowledge Verifier)
知识新鲜度校验系统

核心能力：
1. 检查知识条目关联的代码符号是否存在
2. 标记过时条目
3. 在 make knowledge-verify 中调用
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent


class KnowledgeVerifier:
    """知识验证器"""
    
    def __init__(self):
        self.stale_entries = []
        self.verified_count = 0
    
    def verify_all(self) -> Dict[str, Any]:
        """验证所有知识条目的新鲜度"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'adrs': self._verify_adrs(),
            'faults': self._verify_faults(),
            'summary': {}
        }
        
        # 汇总
        total_stale = len(results['adrs']['stale']) + len(results['faults']['stale'])
        total_verified = results['adrs']['total'] + results['faults']['total']
        
        results['summary'] = {
            'total_verified': total_verified,
            'total_stale': total_stale,
            'freshness_rate': round((total_verified - total_stale) / total_verified * 100, 1) if total_verified > 0 else 100
        }
        
        return results
    
    def _verify_adrs(self) -> Dict[str, Any]:
        """验证 ADR 的新鲜度"""
        adr_dir = PROJECT_ROOT / ".kaelis" / "adr"
        
        if not adr_dir.exists():
            return {'total': 0, 'stale': [], 'valid': []}
        
        stale = []
        valid = []
        
        for adr_file in adr_dir.glob("ADR-*.json"):
            try:
                data = json.loads(adr_file.read_text(encoding='utf-8'))
                adr_id = data.get('id', adr_file.stem)
                
                # 检查关联的文件是否存在
                linked_symbols = data.get('linked_symbols', [])
                stale_symbols = []
                
                for sym in linked_symbols:
                    file_path = PROJECT_ROOT / sym.get('path', sym.get('file', ''))
                    if not file_path.exists():
                        stale_symbols.append({
                            'type': 'file_deleted',
                            'path': str(file_path.relative_to(PROJECT_ROOT)),
                            'symbol': sym.get('name', 'unknown')
                        })
                
                if stale_symbols:
                    stale.append({
                        'id': adr_id,
                        'title': data.get('title', 'Unknown'),
                        'stale_symbols': stale_symbols,
                        'status': data.get('status', 'unknown')
                    })
                else:
                    valid.append({
                        'id': adr_id,
                        'title': data.get('title', 'Unknown')
                    })
                    
            except Exception as e:
                stale.append({
                    'id': adr_file.stem,
                    'error': str(e)
                })
        
        return {
            'total': len(stale) + len(valid),
            'stale': stale,
            'valid': valid
        }
    
    def _verify_faults(self) -> Dict[str, Any]:
        """验证故障知识的新鲜度"""
        kb_path = PROJECT_ROOT / ".kaelis" / "fault-kb.jsonl"
        
        if not kb_path.exists():
            return {'total': 0, 'stale': [], 'valid': []}
        
        stale = []
        valid = []
        
        for line in kb_path.read_text(encoding='utf-8').strip().split('\n'):
            if not line:
                continue
            
            try:
                data = json.loads(line)
                fault_id = data.get('id', 'unknown')
                
                # 检查关联的文件
                file_hashes = data.get('file_hashes', {})
                stale_files = []
                
                for file_path in file_hashes.keys():
                    full_path = PROJECT_ROOT / file_path
                    if not full_path.exists():
                        stale_files.append({
                            'type': 'file_deleted',
                            'path': file_path
                        })
                
                # 检查关联的符号
                linked_symbols = data.get('linked_symbols', [])
                stale_symbols = []
                
                for sym in linked_symbols:
                    file_path = PROJECT_ROOT / sym.get('file', '')
                    if not file_path.exists():
                        stale_symbols.append({
                            'type': 'symbol_file_deleted',
                            'symbol': sym.get('name', 'unknown'),
                            'file': sym.get('file', 'unknown')
                        })
                
                if stale_files or stale_symbols:
                    stale.append({
                        'id': fault_id,
                        'symptoms': data.get('symptoms', 'Unknown')[:50],
                        'stale_files': stale_files,
                        'stale_symbols': stale_symbols,
                        'importance_score': data.get('importance_score', 0)
                    })
                else:
                    valid.append({
                        'id': fault_id,
                        'symptoms': data.get('symptoms', 'Unknown')[:50],
                        'importance_score': data.get('importance_score', 0)
                    })
                    
            except Exception as e:
                pass
        
        return {
            'total': len(stale) + len(valid),
            'stale': stale,
            'valid': valid
        }
    
    def print_report(self, results: Dict[str, Any]):
        """打印验证报告"""
        print("\n" + "=" * 70)
        print("🔍 知识新鲜度验证报告")
        print("=" * 70)
        
        summary = results['summary']
        print(f"\n📊 汇总")
        print(f"   总条目数: {summary['total_verified']}")
        print(f"   过时条目: {summary['total_stale']}")
        print(f"   新鲜度: {summary['freshness_rate']}%")
        
        # ADR 详情
        adr_results = results['adrs']
        if adr_results['stale']:
            print(f"\n⚠️  过时 ADR ({len(adr_results['stale'])} 个):")
            for item in adr_results['stale']:
                print(f"\n   📋 {item['id']}: {item['title']}")
                for sym in item.get('stale_symbols', []):
                    print(f"      ❌ 文件已删除: {sym['path']}")
        
        # 故障详情
        fault_results = results['faults']
        if fault_results['stale']:
            print(f"\n⚠️  过时故障记录 ({len(fault_results['stale'])} 个):")
            for item in fault_results['stale']:
                icon = "🔴" if item.get('importance_score', 0) >= 0.7 else "🟡"
                print(f"\n   {icon} {item['id']}")
                print(f"      症状: {item['symptoms']}")
                for f in item.get('stale_files', []):
                    print(f"      ❌ 文件已删除: {f['path']}")
        
        if summary['total_stale'] == 0:
            print("\n✅ 所有知识条目都是新鲜的！")
        
        print("\n" + "=" * 70)
    
    def export_stale_report(self, results: Dict[str, Any], output_path: Path = None):
        """导出过时报告"""
        if output_path is None:
            output_path = PROJECT_ROOT / ".kaelis" / "stale_knowledge_report.json"
        
        stale_items = []
        
        for item in results['adrs']['stale']:
            stale_items.append({
                'type': 'adr',
                'id': item['id'],
                'title': item['title'],
                'reason': 'linked_file_deleted',
                'stale_symbols': item.get('stale_symbols', [])
            })
        
        for item in results['faults']['stale']:
            stale_items.append({
                'type': 'fault',
                'id': item['id'],
                'symptoms': item['symptoms'],
                'reason': 'linked_file_or_symbol_deleted',
                'stale_files': item.get('stale_files', []),
                'stale_symbols': item.get('stale_symbols', [])
            })
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_stale': len(stale_items),
            'items': stale_items
        }
        
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        return output_path


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Knowledge Verifier',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 验证所有知识新鲜度
  python scripts/knowledge_verifier.py verify

  # 验证并导出过时报告
  python scripts/knowledge_verifier.py verify --export
        """
    )
    
    parser.add_argument('--export', '-e', action='store_true', help='Export stale report')
    parser.add_argument('--output', '-o', type=Path, help='Output path for report')
    
    args = parser.parse_args()
    
    verifier = KnowledgeVerifier()
    results = verifier.verify_all()
    verifier.print_report(results)
    
    if args.export:
        path = verifier.export_stale_report(results, args.output)
        print(f"\n📄 报告已导出: {path}")
    
    # 返回退出码
    return 0 if results['summary']['total_stale'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
