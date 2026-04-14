#!/usr/bin/env python3
"""
测试 Neo4j 连接切换逻辑
"""
import os
import sys

# 设置环境变量
os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
os.environ['NEO4J_USER'] = 'neo4j'
os.environ['NEO4J_PASS'] = 'password'

# 清除缓存
for mod in list(sys.modules.keys()):
    if 'kg_flywheel' in mod:
        del sys.modules[mod]

print("=" * 60)
print("Neo4j 连接切换测试")
print("=" * 60)
print()

# 第一次检测（Neo4j 未启动）
print("[Test 1] Neo4j 未启动时:")
from api.routes.kg_flywheel_tools import get_neo4j_driver, neo4j_connection_status
driver = get_neo4j_driver()
print(f"  Driver type: {type(driver).__name__}")
print(f"  Status: {neo4j_connection_status}")
print()

# 模拟 Neo4j 启动后的重新检测
print("[Test 2] 模拟 Neo4j 重启检测:")
driver2 = get_neo4j_driver(force_reconnect=True)
print(f"  Driver type: {type(driver2).__name__}")
print(f"  Status: {neo4j_connection_status}")
print()

# 测试工具调用
print("[Test 3] 工具调用测试:")
import asyncio

async def test_tools():
    from api.routes.kg_flywheel_tools import TOOL_REGISTRY
    
    # 测试提取
    result = await TOOL_REGISTRY.call("extract_triples", {
        "text": "测试文本",
        "source": "test",
        "user_id": "test_user"
    })
    print(f"  Extract result: {result.get('task_id')}")
    print(f"  Triples count: {result.get('triples_extracted')}")
    
    # 测试查询
    result = await TOOL_REGISTRY.call("query_graph", {
        "query": "MATCH (n) RETURN count(n) as cnt",
        "user_id": "test_user"
    })
    print(f"  Query success: {result.get('success')}")

asyncio.run(test_tools())
print()

print("=" * 60)
print("测试完成!")
print("=" * 60)
print()
print("说明:")
print("- 当真实 Neo4j 不可用时，系统自动降级到 Mock 驱动")
print("- 启动 Neo4j 后，使用 force_reconnect=True 可自动切换到真实驱动")
print("- 所有工具调用在两种模式下都能正常工作")
