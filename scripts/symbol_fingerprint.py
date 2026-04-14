#!/usr/bin/env python3
"""
Kaelis Symbol Fingerprint System
技术债务治理 v2.0 - 增强1: 符号指纹替代文件路径

基于AST结构哈希计算符号指纹，代码重构时保持链接稳定。
"""

import ast
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class SymbolFingerprint:
    """符号指纹数据结构"""
    symbol_name: str
    symbol_type: str  # 'function', 'class', 'method'
    fingerprint: str  # 16位结构哈希
    file_path: str    # 当前文件路径（可更新）
    line_number: int
    column: int
    ast_structure: str  # 归一化的AST结构
    last_updated: str


class SymbolFingerprintEngine:
    """符号指纹引擎"""
    
    def __init__(self, index_file: str = ".kaelis/symbol_fingerprints.json"):
        self.index_file = Path(index_file)
        self.fingerprints: Dict[str, SymbolFingerprint] = {}
        self._load_index()
    
    def _load_index(self):
        """加载指纹索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for fp_data in data.get('fingerprints', []):
                        fp = SymbolFingerprint(**fp_data)
                        self.fingerprints[fp.fingerprint] = fp
            except Exception as e:
                print(f"[WARN] 加载指纹索引失败: {e}")
    
    def _save_index(self):
        """保存指纹索引"""
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'version': '1.0',
            'total_symbols': len(self.fingerprints),
            'fingerprints': [asdict(fp) for fp in self.fingerprints.values()]
        }
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _normalize_ast_node(self, node: ast.AST) -> str:
        """
        归一化AST节点：
        - 移除docstring
        - 移除注释
        - 保留结构（函数名、参数、调用关系）
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 提取函数签名结构
            name = node.name
            args = []
            for arg in node.args.args:
                arg_type = ""
                if arg.annotation:
                    arg_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else ""
                args.append(f"{arg.arg}:{arg_type}")
            
            # 提取返回类型
            returns = ""
            if node.returns:
                returns = ast.unparse(node.returns) if hasattr(ast, 'unparse') else ""
            
            # 提取函数体内的关键调用（仅函数名，不包含具体参数）
            calls = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name):
                        calls.append(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        calls.append(child.func.attr)
            
            # 构建归一化结构
            structure = f"def {name}({','.join(args)})->{returns}:[{','.join(sorted(set(calls)))}]"
            return structure
        
        elif isinstance(node, ast.ClassDef):
            # 提取类结构
            name = node.name
            bases = [ast.unparse(base) if hasattr(ast, 'unparse') else base.id 
                    for base in node.bases if isinstance(base, ast.Name)]
            
            # 提取方法名（不含实现）
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            
            structure = f"class {name}({','.join(bases)}):[{','.join(methods)}]"
            return structure
        
        return ""
    
    def compute_fingerprint(self, symbol_name: str, file_path: str) -> Optional[str]:
        """
        计算符号指纹
        
        Args:
            symbol_name: 符号名称（函数名/类名）
            file_path: 文件路径
            
        Returns:
            16位指纹哈希，失败返回None
        """
        path = Path(file_path)
        if not path.exists():
            print(f"[ERROR] 文件不存在: {file_path}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == symbol_name:
                        structure = self._normalize_ast_node(node)
                        if structure:
                            # 计算哈希
                            fingerprint = hashlib.sha256(
                                structure.encode('utf-8')
                            ).hexdigest()[:16]
                            
                            # 保存指纹记录
                            fp = SymbolFingerprint(
                                symbol_name=symbol_name,
                                symbol_type='function',
                                fingerprint=fingerprint,
                                file_path=str(file_path),
                                line_number=node.lineno,
                                column=node.col_offset,
                                ast_structure=structure,
                                last_updated=datetime.now().isoformat()
                            )
                            self.fingerprints[fingerprint] = fp
                            self._save_index()
                            
                            return fingerprint
                
                elif isinstance(node, ast.ClassDef):
                    if node.name == symbol_name:
                        structure = self._normalize_ast_node(node)
                        if structure:
                            fingerprint = hashlib.sha256(
                                structure.encode('utf-8')
                            ).hexdigest()[:16]
                            
                            fp = SymbolFingerprint(
                                symbol_name=symbol_name,
                                symbol_type='class',
                                fingerprint=fingerprint,
                                file_path=str(file_path),
                                line_number=node.lineno,
                                column=node.col_offset,
                                ast_structure=structure,
                                last_updated=datetime.now().isoformat()
                            )
                            self.fingerprints[fingerprint] = fp
                            self._save_index()
                            
                            return fingerprint
            
            print(f"[WARN] 未在文件中找到符号: {symbol_name}")
            return None
            
        except SyntaxError as e:
            print(f"[ERROR] 解析文件失败 {file_path}: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] 计算指纹失败: {e}")
            return None
    
    def find_symbol_by_fingerprint(self, fingerprint: str) -> Optional[SymbolFingerprint]:
        """通过指纹查找符号"""
        return self.fingerprints.get(fingerprint)
    
    def update_symbol_location(self, fingerprint: str, new_file_path: str, 
                               new_line_number: int = None) -> bool:
        """
        更新符号位置（代码重构后调用）
        
        Args:
            fingerprint: 符号指纹
            new_file_path: 新文件路径
            new_line_number: 新行号（可选）
            
        Returns:
            是否更新成功
        """
        fp = self.fingerprints.get(fingerprint)
        if not fp:
            print(f"[WARN] 未找到指纹: {fingerprint}")
            return False
        
        old_path = fp.file_path
        fp.file_path = new_file_path
        if new_line_number:
            fp.line_number = new_line_number
        fp.last_updated = datetime.now().isoformat()
        
        self._save_index()
        print(f"[INFO] 更新符号位置: {old_path} -> {new_file_path}")
        return True
    
    def scan_file_for_changes(self, file_path: str) -> List[Tuple[str, str]]:
        """
        扫描文件变化，返回(指纹, 状态)列表
        状态: 'unchanged', 'moved', 'modified', 'new', 'deleted'
        """
        path = Path(file_path)
        if not path.exists():
            return []
        
        changes = []
        current_fingerprints = {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            # 提取当前文件所有符号
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    structure = self._normalize_ast_node(node)
                    if structure:
                        fingerprint = hashlib.sha256(
                            structure.encode('utf-8')
                        ).hexdigest()[:16]
                        current_fingerprints[fingerprint] = {
                            'name': node.name,
                            'type': 'class' if isinstance(node, ast.ClassDef) else 'function',
                            'line': node.lineno
                        }
            
            # 比对已有指纹
            for fp_hash, fp_data in self.fingerprints.items():
                if fp_data.file_path == str(file_path):
                    if fp_hash in current_fingerprints:
                        # 检查是否移动
                        current = current_fingerprints[fp_hash]
                        if current['line'] != fp_data.line_number:
                            changes.append((fp_hash, 'moved'))
                        else:
                            changes.append((fp_hash, 'unchanged'))
                    else:
                        changes.append((fp_hash, 'deleted'))
            
            # 检查新符号
            for fp_hash, current in current_fingerprints.items():
                if fp_hash not in self.fingerprints:
                    changes.append((fp_hash, 'new'))
            
            return changes
            
        except Exception as e:
            print(f"[ERROR] 扫描文件失败: {e}")
            return []
    
    def get_all_fingerprints(self) -> Dict[str, SymbolFingerprint]:
        """获取所有指纹"""
        return self.fingerprints.copy()
    
    def remove_fingerprint(self, fingerprint: str) -> bool:
        """删除指纹"""
        if fingerprint in self.fingerprints:
            del self.fingerprints[fingerprint]
            self._save_index()
            return True
        return False


def main():
    """CLI入口"""
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(
        description='Kaelis Symbol Fingerprint System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/symbol_fingerprint.py compute MyClass api/models/user.py
  python scripts/symbol_fingerprint.py find abc123def4567890
  python scripts/symbol_fingerprint.py scan api/models/user.py
  python scripts/symbol_fingerprint.py relink abc123def4567890 api/models/new_user.py
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # compute
    compute_parser = subparsers.add_parser('compute', help='计算符号指纹')
    compute_parser.add_argument('symbol_name', help='符号名称')
    compute_parser.add_argument('file_path', help='文件路径')
    
    # find
    find_parser = subparsers.add_parser('find', help='通过指纹查找符号')
    find_parser.add_argument('fingerprint', help='指纹哈希')
    
    # scan
    scan_parser = subparsers.add_parser('scan', help='扫描文件变化')
    scan_parser.add_argument('file_path', help='文件路径')
    
    # relink
    relink_parser = subparsers.add_parser('relink', help='更新符号位置')
    relink_parser.add_argument('fingerprint', help='指纹哈希')
    relink_parser.add_argument('new_file_path', help='新文件路径')
    relink_parser.add_argument('--line', type=int, help='新行号')
    
    # list
    list_parser = subparsers.add_parser('list', help='列出所有指纹')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    engine = SymbolFingerprintEngine()
    
    if args.command == 'compute':
        fp = engine.compute_fingerprint(args.symbol_name, args.file_path)
        if fp:
            print(f"✅ 指纹计算成功")
            print(f"   符号: {args.symbol_name}")
            print(f"   文件: {args.file_path}")
            print(f"   指纹: {fp}")
        else:
            print("❌ 指纹计算失败")
            return 1
    
    elif args.command == 'find':
        result = engine.find_symbol_by_fingerprint(args.fingerprint)
        if result:
            print(f"✅ 找到符号")
            print(f"   名称: {result.symbol_name}")
            print(f"   类型: {result.symbol_type}")
            print(f"   位置: {result.file_path}:{result.line_number}")
            print(f"   结构: {result.ast_structure[:80]}...")
        else:
            print(f"❌ 未找到指纹: {args.fingerprint}")
            return 1
    
    elif args.command == 'scan':
        changes = engine.scan_file_for_changes(args.file_path)
        if changes:
            print(f"📊 扫描结果: {len(changes)} 个符号")
            for fp, status in changes:
                emoji = {
                    'unchanged': '✅',
                    'moved': '📦',
                    'modified': '📝',
                    'new': '✨',
                    'deleted': '🗑️'
                }.get(status, '❓')
                print(f"   {emoji} {fp[:16]}...: {status}")
        else:
            print("ℹ️  无符号变化")
    
    elif args.command == 'relink':
        success = engine.update_symbol_location(
            args.fingerprint, 
            args.new_file_path,
            args.line
        )
        if success:
            print(f"✅ 已更新符号位置")
        else:
            print(f"❌ 更新失败")
            return 1
    
    elif args.command == 'list':
        fps = engine.get_all_fingerprints()
        if fps:
            print(f"📋 共 {len(fps)} 个符号指纹")
            for fp_hash, fp_data in fps.items():
                print(f"   {fp_hash[:16]}... | {fp_data.symbol_name} ({fp_data.symbol_type})")
                print(f"               @ {fp_data.file_path}:{fp_data.line_number}")
        else:
            print("ℹ️  暂无指纹记录")


if __name__ == '__main__':
    main()
