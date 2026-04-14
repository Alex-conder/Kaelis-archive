#!/usr/bin/env python3
"""
Kaelis AI Native CLI
Phase 1: Infrastructure Layer - CLI Integration

Commands:
    kaelis ai status          # 查看 AI 服务状态
    kaelis ai sync            # 同步所有 AI 上下文文件
    kaelis ai query "..."     # 自然语言查询
    kaelis ai search <symbol> # 符号搜索
    kaelis ai impact <file>   # 影响分析
"""

import argparse
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:5000"
KIMI_DIR = Path(".kimi")


def run_api_request(method, endpoint, data=None, params=None):
    """Make API request using curl"""
    import urllib.request
    import urllib.error
    
    url = f"{API_BASE_URL}{endpoint}"
    if params:
        query_string = '&'.join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query_string}"
    
    try:
        if method == "GET":
            req = urllib.request.Request(url)
        else:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode('utf-8') if data else None,
                headers={'Content-Type': 'application/json'},
                method=method
            )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as e:
        print(f"❌ 无法连接到服务: {e}")
        print(f"   请确保服务已启动: python launch.py")
        return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def cmd_status():
    """Check AI service status"""
    print("🔍 检查 Kaelis AI Native 服务状态...\n")
    
    result = run_api_request("GET", "/ai/health")
    
    if not result:
        sys.exit(1)
    
    if result.get("status") == "healthy":
        print("✅ AI Native 服务运行正常")
        print(f"   版本: {result.get('version')}")
        print(f"   时间: {result.get('timestamp')}")
        print(f"\n📡 可用端点:")
        for endpoint in result.get("endpoints", []):
            print(f"   • {endpoint}")
    else:
        print(f"⚠️  服务状态异常: {result.get('status')}")


def cmd_sync():
    """Sync AI context files"""
    print("🔄 同步 AI 上下文文件...\n")
    
    # Ensure .kimi directory exists
    KIMI_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate commands.md
    commands_file = KIMI_DIR / "commands.md"
    
    # Update timestamp in commands.md
    content = generate_commands_md()
    
    with open(commands_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已生成: {commands_file}")
    
    # Generate corrections.md (placeholder for Phase 2)
    corrections_file = KIMI_DIR / "corrections.md"
    if not corrections_file.exists():
        with open(corrections_file, 'w', encoding='utf-8') as f:
            f.write(generate_corrections_md())
        print(f"✅ 已生成: {corrections_file}")
    else:
        print(f"⏭️  已存在: {corrections_file} (使用 'kaelis ai analyze' 更新)")
    
    print("\n📝 AI 上下文文件已同步")
    print("   Kimi Code 现在可以读取这些文件来了解项目架构")


def generate_commands_md():
    """Generate commands.md content"""
    from datetime import datetime
    
    return f"""# Kaelis 对话式治理命令映射

> 本文件定义自然语言查询到 Kaelis API 的映射关系
> AI 编码助手可参考此文件理解如何与 Kaelis 架构治理系统交互
> 生成时间: {datetime.now().isoformat()}

## 核心 API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| /ai/contract/m0 | GET | 获取所有 M0 规则 |
| /ai/contract/m0/{{id}} | GET | 获取单个 M0 规则 |
| /ai/contract/openapi/summary | GET | 获取 API 摘要 |
| /ai/symbols/search | GET | 符号搜索 |
| /ai/impact/analyze | POST | 影响分析 |
| /ai/risk/pre-check | GET | 风险评分 |
| /ai/block-events | POST | 记录阻断事件 |
| /ai/health | GET | 健康检查 |

## 常用查询映射

### M0 规则查询
**用户**: "M0 规则有哪些？"
**→**: GET /ai/contract/m0

### 符号搜索
**用户**: "搜索 UserService"
**→**: GET /ai/symbols/search?q=UserService&limit=10

### 影响分析
**用户**: "修改 OrderService 会影响什么？"
**→**: POST /ai/impact/analyze
**Body**: {{"symbol": "OrderService", "file_path": "api/services/order.py", "change_type": "modify"}}

### 风险检查
**用户**: "这段代码有风险吗？"
**→**: GET /ai/risk/pre-check?file_path=api/services/order.py

## 更多信息

查看完整文档: .kimi/commands.md
"""


def generate_corrections_md():
    """Generate initial corrections.md"""
    return """# AI 纠偏指南

> 常见错误模式 → 正确写法
> 本文件基于历史阻断事件自动生成

## 使用说明

AI 编码助手在生成代码前应检查此文件，避免已知的常见错误。

## 规则索引

<!-- 将由 kaelis ai analyze 自动填充 -->

*暂无纠偏记录。运行 `kaelis ai analyze` 生成。*

---

## 如何添加纠偏记录

1. 当代码被 Kaelis 阻断时，事件会被自动记录
2. 运行 `kaelis ai analyze` 分析阻断模式
3. 本文件将自动更新

---

*文件版本: 1.0.0*
"""


def cmd_query(query_text):
    """Natural language query"""
    print(f"🔍 查询: {query_text}\n")
    
    # Simple keyword-based routing
    query_lower = query_text.lower()
    
    if "m0" in query_lower or "规则" in query_lower or "规范" in query_lower:
        # Query M0 rules
        result = run_api_request("GET", "/ai/contract/m0")
        if result:
            print("📋 M0 代码规范:\n")
            for rule in result:
                severity_emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    rule.get("severity"), "⚪"
                )
                print(f"{severity_emoji} {rule.get('id')}: {rule.get('name')}")
                print(f"   {rule.get('description')}")
                if rule.get("suggestion"):
                    print(f"   💡 建议: {rule.get('suggestion')}")
                print()
    
    elif "api" in query_lower or "接口" in query_lower or "端点" in query_lower:
        # Query API summary
        result = run_api_request("GET", "/ai/contract/openapi/summary")
        if result:
            print(f"📡 {result.get('title')} v{result.get('version')}\n")
            print(f"共 {result.get('total_endpoints')} 个端点")
            print(f"数据模型: {', '.join(result.get('schemas', [])[:5])}...")
    
    elif "健康" in query_lower or "状态" in query_lower or "status" in query_lower:
        cmd_status()
    
    else:
        print("💡 支持的查询类型:")
        print("   • 'M0 规则有哪些？' - 查看代码规范")
        print("   • 'API 结构' - 查看 API 摘要")
        print("   • '服务状态' - 查看健康状态")


def cmd_search(symbol_name):
    """Search for symbols"""
    print(f"🔍 搜索符号: {symbol_name}\n")
    
    result = run_api_request("GET", "/ai/symbols/search", params={
        "q": symbol_name,
        "limit": 10
    })
    
    if not result:
        return
    
    if not result:
        print(f"❌ 未找到匹配 '{symbol_name}' 的符号")
        return
    
    print(f"找到 {len(result)} 个结果:\n")
    
    for sym in result:
        type_emoji = {"class": "📦", "function": "⚙️", "module": "📁"}.get(
            sym.get("type"), "📄"
        )
        print(f"{type_emoji} {sym.get('name')} ({sym.get('type')})")
        print(f"   位置: {sym.get('file_path')}:{sym.get('line_number')}")
        if sym.get("signature"):
            print(f"   签名: {sym.get('signature')}")
        if sym.get("docstring"):
            print(f"   文档: {sym.get('docstring')[:100]}...")
        print()


def cmd_impact(file_path, symbol=None):
    """Analyze impact of changes"""
    if not symbol:
        # Try to extract symbol name from file path
        symbol = Path(file_path).stem
    
    print(f"📊 分析 {symbol} 的影响范围...\n")
    
    result = run_api_request("POST", "/ai/impact/analyze", data={
        "symbol": symbol,
        "file_path": file_path,
        "change_type": "modify"
    })
    
    if not result:
        return
    
    risk_emoji = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴"
    }.get(result.get("risk_level"), "⚪")
    
    print(f"{risk_emoji} 风险等级: {result.get('risk_level')}")
    print(f"⏱️  估计工作量: {result.get('estimated_effort')}")
    print()
    
    direct_deps = result.get("direct_dependencies", [])
    indirect_deps = result.get("indirect_dependencies", [])
    affected_files = result.get("affected_files", [])
    
    print(f"📎 直接依赖: {len(direct_deps)} 个")
    for dep in direct_deps[:5]:
        print(f"   • {dep.get('name')} @ {dep.get('file_path')}")
    if len(direct_deps) > 5:
        print(f"   ... 还有 {len(direct_deps) - 5} 个")
    print()
    
    print(f"📎 间接依赖: {len(indirect_deps)} 个")
    print(f"📁 受影响文件: {len(affected_files)} 个")
    print()
    
    print("💡 建议措施:")
    for suggestion in result.get("suggestions", []):
        print(f"   • {suggestion}")


def cmd_risk(file_path):
    """Check risk score"""
    print(f"⚠️  评估 {file_path} 的风险...\n")
    
    result = run_api_request("GET", "/ai/risk/pre-check", params={
        "file_path": file_path
    })
    
    if not result:
        return
    
    level = result.get("level")
    score = result.get("total_score")
    
    level_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(level, "⚪")
    
    print(f"{level_emoji} 风险等级: {level} ({score}/100)")
    print(f"   阻断阈值: {result.get('block_threshold')}")
    
    if result.get("should_block"):
        print("   ⚠️  建议阻断提交，请人工审核")
    else:
        print("   ✅ 风险可控")
    print()
    
    print("📊 各维度评分:")
    for dim in result.get("dimensions", []):
        bar = "█" * (dim.get("score", 0) // 5) + "░" * (20 - dim.get("score", 0) // 5)
        print(f"   {dim.get('name'):10} [{bar}] {dim.get('score')}/100")
        print(f"              {dim.get('details')}")
    print()
    
    print("💡 建议:")
    for suggestion in result.get("suggestions", []):
        print(f"   • {suggestion}")


def cmd_analyze():
    """Analyze block patterns (Phase 2 placeholder)"""
    print("📈 阻断模式分析 (Phase 2 功能)\n")
    
    telemetry_file = Path(".kaelis-telemetry.jsonl")
    
    if not telemetry_file.exists():
        print("ℹ️  暂无阻断事件记录")
        print("   当 AI 生成的代码被阻断时，事件将自动记录")
        return
    
    try:
        with open(telemetry_file, 'r', encoding='utf-8') as f:
            events = [json.loads(line) for line in f if line.strip()]
        
        block_events = [e for e in events if e.get("type") == "block"]
        
        print(f"共记录 {len(block_events)} 次阻断事件\n")
        
        # Group by rule
        from collections import Counter
        rule_counts = Counter(e.get("rule_id") for e in block_events)
        
        print("按规则统计:")
        for rule_id, count in rule_counts.most_common():
            print(f"   • {rule_id}: {count} 次")
        
        # Check for patterns (3+ occurrences)
        patterns = [(rule, count) for rule, count in rule_counts.items() if count >= 3]
        
        if patterns:
            print("\n🔍 发现重复模式 (3+ 次):")
            for rule, count in patterns:
                print(f"   ⚠️  {rule}: {count} 次")
            print("\n💡 建议: 考虑调整规则或更新纠偏指南")
        else:
            print("\n✅ 未发现明显重复模式")
            
    except Exception as e:
        print(f"❌ 分析失败: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Kaelis AI Native CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/kaelis_ai.py status
  python scripts/kaelis_ai.py sync
  python scripts/kaelis_ai.py query "M0 规则有哪些？"
  python scripts/kaelis_ai.py search UserService
  python scripts/kaelis_ai.py impact api/services/order.py
  python scripts/kaelis_ai.py risk api/routes/users.py
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # status
    subparsers.add_parser("status", help="查看 AI 服务状态")
    
    # sync
    subparsers.add_parser("sync", help="同步 AI 上下文文件")
    
    # query
    query_parser = subparsers.add_parser("query", help="自然语言查询")
    query_parser.add_argument("text", help="查询内容")
    
    # search
    search_parser = subparsers.add_parser("search", help="符号搜索")
    search_parser.add_argument("symbol", help="符号名称")
    
    # impact
    impact_parser = subparsers.add_parser("impact", help="影响分析")
    impact_parser.add_argument("file", help="文件路径")
    impact_parser.add_argument("--symbol", "-s", help="符号名称（默认从文件名推断）")
    
    # risk
    risk_parser = subparsers.add_parser("risk", help="风险评分")
    risk_parser.add_argument("file", help="文件路径")
    
    # analyze
    subparsers.add_parser("analyze", help="分析阻断模式")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to appropriate command
    if args.command == "status":
        cmd_status()
    elif args.command == "sync":
        cmd_sync()
    elif args.command == "query":
        cmd_query(args.text)
    elif args.command == "search":
        cmd_search(args.symbol)
    elif args.command == "impact":
        cmd_impact(args.file, args.symbol)
    elif args.command == "risk":
        cmd_risk(args.file)
    elif args.command == "analyze":
        cmd_analyze()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
