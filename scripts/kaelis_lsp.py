#!/usr/bin/env python3
"""
Kaelis Phase 7 - Language Server Protocol (LSP) 实现
Agent 护栏服务 - 为 AI 编码提供实时契约校验

核心能力：
1. LSP 标准接口实现
2. 实时代码校验（文档变更时触发）
3. 诊断信息推送（Diagnostics）
4. 代码动作建议（Code Actions）
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any

# 尝试导入 pygls（LSP 库）
try:
    from pygls.server import LanguageServer
    from pygls.protocol import JsonRPCProtocol
    from lsprotocol.types import (
        TEXT_DOCUMENT_DID_CHANGE,
        TEXT_DOCUMENT_DID_OPEN,
        DidChangeTextDocumentParams,
        DidOpenTextDocumentParams,
        Diagnostic,
        DiagnosticSeverity,
        Range,
        Position,
        CodeAction,
        CodeActionParams,
        Command,
        TEXT_DOCUMENT_CODE_ACTION,
        WorkspaceEdit,
        TextEdit,
    )
    LSP_AVAILABLE = True
except ImportError:
    LSP_AVAILABLE = False
    print("[WARN] pygls not installed. LSP mode not available.")
    print("Install: pip install pygls lsprotocol")

PROJECT_ROOT = Path(__file__).parent.parent

# 导入护栏规则引擎
try:
    from guard_rules import GuardRuleEngine, GuardViolation, GuardEventLogger
    GUARD_AVAILABLE = True
except ImportError:
    GUARD_AVAILABLE = False
    print("[WARN] Guard rules not available")


class KaelisLanguageServer:
    """Kaelis LSP 服务器"""
    
    def __init__(self):
        self.server = None
        self.guard_engine = None
        self.event_logger = None
        
        if GUARD_AVAILABLE:
            self.guard_engine = GuardRuleEngine()
            self.event_logger = GuardEventLogger()
    
    def create_server(self) -> 'LanguageServer':
        """创建 LSP 服务器实例"""
        if not LSP_AVAILABLE:
            raise RuntimeError("pygls not installed")
        
        server = LanguageServer("kaelis-lsp", "v1.0")
        
        @server.feature(TEXT_DOCUMENT_DID_OPEN)
        async def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams):
            """文档打开时触发校验"""
            await self._validate_document(ls, params.text_document.uri, params.text_document.text)
        
        @server.feature(TEXT_DOCUMENT_DID_CHANGE)
        async def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams):
            """文档变更时触发校验"""
            # 获取文档最新内容
            document = ls.workspace.get_document(params.text_document.uri)
            await self._validate_document(ls, params.text_document.uri, document.source)
        
        @server.feature(TEXT_DOCUMENT_CODE_ACTION)
        async def code_action(ls: LanguageServer, params: CodeActionParams):
            """提供代码动作建议"""
            return await self._get_code_actions(ls, params)
        
        self.server = server
        return server
    
    async def _validate_document(self, ls: LanguageServer, uri: str, content: str):
        """校验文档内容"""
        if not self.guard_engine:
            return
        
        # 确定语言
        language = self._detect_language(uri)
        
        # 执行护栏检查
        violations = self.guard_engine.check(content, {'uri': uri, 'language': language})
        
        # 转换为 LSP 诊断格式
        diagnostics = []
        
        for v in violations:
            severity = self._map_severity(v.level)
            
            # 创建诊断范围（简化：整行）
            if v.line:
                range_obj = Range(
                    start=Position(line=v.line - 1, character=0),
                    end=Position(line=v.line - 1, character=1000)
                )
            else:
                range_obj = Range(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=0)
                )
            
            diagnostic = Diagnostic(
                range=range_obj,
                message=f"[{v.rule}] {v.message}\n💡 {v.suggestion}",
                severity=severity,
                source="Kaelis Guard",
                code=v.rule
            )
            diagnostics.append(diagnostic)
        
        # 推送诊断信息
        ls.publish_diagnostics(uri, diagnostics)
        
        # 记录事件
        if self.event_logger:
            self.event_logger.log(
                'check' if not any(v.level == 'block' for v in violations) else 'block',
                violations,
                {'uri': uri, 'language': language}
            )
    
    async def _get_code_actions(self, ls: LanguageServer, params: CodeActionParams) -> List[CodeAction]:
        """获取代码动作建议"""
        actions = []
        
        # 获取当前诊断信息
        diagnostics = params.context.diagnostics
        
        for diag in diagnostics:
            if diag.source == "Kaelis Guard":
                # 提供快速修复建议
                if "环境变量" in diag.message:
                    action = CodeAction(
                        title="🛡️ 使用环境变量替代硬编码",
                        kind="quickfix",
                        diagnostics=[diag],
                        edit=WorkspaceEdit(
                            document_changes=[]
                        ),
                        command=Command(
                            title="Apply fix",
                            command="kaelis.applyGuardFix",
                            arguments=[diag.code, params.text_document.uri]
                        )
                    )
                    actions.append(action)
        
        return actions
    
    def _detect_language(self, uri: str) -> str:
        """从 URI 检测编程语言"""
        if uri.endswith('.py'):
            return 'python'
        elif uri.endswith(('.ts', '.tsx')):
            return 'typescript'
        elif uri.endswith(('.js', '.jsx')):
            return 'javascript'
        elif uri.endswith('.yaml') or uri.endswith('.yml'):
            return 'yaml'
        elif uri.endswith('.json'):
            return 'json'
        else:
            return 'plaintext'
    
    def _map_severity(self, level: str) -> DiagnosticSeverity:
        """映射违规级别到 LSP 严重程度"""
        mapping = {
            'info': DiagnosticSeverity.Information,
            'warning': DiagnosticSeverity.Warning,
            'error': DiagnosticSeverity.Error,
            'block': DiagnosticSeverity.Error
        }
        return mapping.get(level, DiagnosticSeverity.Warning)
    
    def start_stdio(self):
        """启动 STDIO 模式（标准 LSP 通信）"""
        if not LSP_AVAILABLE:
            print("❌ pygls not installed. Cannot start LSP server.")
            print("Install: pip install pygls lsprotocol")
            return 1
        
        print("🚀 Kaelis Language Server starting...")
        print("   Mode: STDIO")
        print("   Version: v1.0")
        
        server = self.create_server()
        server.start_io()
        return 0
    
    def start_tcp(self, host: str = "127.0.0.1", port: int = 9999):
        """启动 TCP 模式"""
        if not LSP_AVAILABLE:
            print("❌ pygls not installed. Cannot start LSP server.")
            return 1
        
        print(f"🚀 Kaelis Language Server starting...")
        print(f"   Mode: TCP")
        print(f"   Address: {host}:{port}")
        print(f"   Version: v1.0")
        
        server = self.create_server()
        server.start_tcp(host, port)
        return 0


class KaelisLSPClient:
    """Kaelis LSP 客户端（用于测试）"""
    
    def __init__(self):
        self.server_process = None
    
    def start_server(self) -> subprocess.Popen:
        """启动 LSP 服务器子进程"""
        import subprocess
        
        cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "kaelis_lsp.py"), "stdio"]
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.server_process = process
        return process
    
    def send_request(self, method: str, params: Dict[str, Any]):
        """发送 LSP 请求"""
        # 简化实现，实际使用 JSON-RPC
        pass
    
    def stop(self):
        """停止服务器"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Language Server / Guard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 启动 LSP 服务器 (STDIO 模式，用于编辑器集成)
  python scripts/kaelis_lsp.py stdio

  # 启动 LSP 服务器 (TCP 模式)
  python scripts/kaelis_lsp.py tcp --host 127.0.0.1 --port 9999

  # 单次代码检查
  python scripts/kaelis_lsp.py check --file api/routes/kg.py
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # stdio 命令
    subparsers.add_parser('stdio', help='Start LSP server in STDIO mode')
    
    # tcp 命令
    tcp_parser = subparsers.add_parser('tcp', help='Start LSP server in TCP mode')
    tcp_parser.add_argument('--host', default='127.0.0.1', help='Host address')
    tcp_parser.add_argument('--port', type=int, default=9999, help='Port number')
    
    # check 命令
    check_parser = subparsers.add_parser('check', help='Check code file')
    check_parser.add_argument('--file', '-f', type=Path, required=True, help='File to check')
    
    args = parser.parse_args()
    
    lsp = KaelisLanguageServer()
    
    if args.command == 'stdio':
        return lsp.start_stdio()
    
    elif args.command == 'tcp':
        return lsp.start_tcp(args.host, args.port)
    
    elif args.command == 'check':
        # 单次检查模式
        if not GUARD_AVAILABLE:
            print("❌ Guard rules not available")
            return 1
        
        engine = GuardRuleEngine()
        violations = engine.check_file(args.file)
        
        print("\n" + "=" * 60)
        print("🛡️  Kaelis Guard - 代码检查")
        print("=" * 60)
        print(f"\n文件: {args.file}")
        
        if not violations:
            print("\n✅ 未检测到违规")
        else:
            print(f"\n⚠️  发现 {len(violations)} 个问题:\n")
            
            for v in violations:
                icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "block": "🚫"}.get(v.level, "❓")
                print(f"{icon} [{v.level.upper()}] {v.rule}")
                print(f"   {v.message}")
                print(f"   💡 {v.suggestion}")
                if v.line:
                    print(f"   📍 第 {v.line} 行")
                print()
        
        print("=" * 60)
        
        has_block = any(v.level == 'block' for v in violations)
        return 1 if has_block else 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
