"""
KgFlywheel API 路由
REST API + WebSocket 端点
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify

# 导入核心组件
from .kg_flywheel_agent import create_kg_flywheel_agent, AgentState
from .kg_flywheel_tools import TOOL_REGISTRY
from .kg_flywheel_memory import create_kg_memory

# 创建 Blueprint
kg_flywheel_bp = Blueprint('kg_flywheel', __name__, url_prefix='/api/kg-flywheel')

# WebSocket 处理器（由 unified_server 注册）
ws_handlers = {}


# =============================================================================
# REST API 端点
# =============================================================================

@kg_flywheel_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    # 检查 Neo4j 连接
    from .kg_flywheel_tools import neo4j_driver
    
    try:
        neo4j_driver.verify_connectivity()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return jsonify({
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "kg-flywheel",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    })


@kg_flywheel_bp.route('/chat', methods=['POST'])
def chat():
    """
    主聊天端点
    
    Request Body:
        {
            "message": "用户输入",
            "user_id": "用户ID",
            "session_id": "会话ID（可选）",
            "context": {}  // 附加上下文
        }
    
    Response:
        {
            "reply": "Agent 回复",
            "session_id": "会话ID",
            "state": "COMPLETED",
            "data": {},  // 结构化数据
            "tool_calls": ["使用的工具列表"]
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "缺少 message 字段"}), 400
        
        user_id = data.get('user_id', 'anonymous')
        session_id = data.get('session_id')
        message = data['message']
        context = data.get('context', {})
        
        # 创建 Agent
        agent = create_kg_flywheel_agent(user_id, session_id, TOOL_REGISTRY)
        
        # 处理消息
        response = asyncio.run(agent.process(message, context))
        
        # 记录实体用于图谱可视化
        try:
            from .kg_flywheel_memory import KgFlywheelMemory
            memory = KgFlywheelMemory(user_id, response.session_id)
            memory.record_entities(message)
            # 也记录回复中的实体
            memory.record_entities(response.reply)
        except Exception as e:
            # 记录失败不影响主流程
            pass
        
        return jsonify({
            "reply": response.reply,
            "session_id": response.session_id,
            "state": response.state.value,
            "data": response.data,
            "tool_calls": response.tool_calls,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@kg_flywheel_bp.route('/extract', methods=['POST'])
def extract():
    """
    直接提取端点
    
    Request Body:
        {
            "text": "要提取的文本",
            "source": "来源标识（可选）",
            "user_id": "用户ID（可选）"
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({"error": "缺少 text 字段"}), 400
        
        result = asyncio.run(TOOL_REGISTRY.call("extract_triples", {
            "text": data['text'],
            "source": data.get('source', 'api'),
            "user_id": data.get('user_id', 'anonymous')
        }))
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kg_flywheel_bp.route('/query', methods=['POST'])
def query():
    """
    直接查询端点
    
    Request Body:
        {
            "query": "Cypher 查询语句",
            "parameters": {},  // 查询参数
            "user_id": "用户ID（可选）"
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({"error": "缺少 query 字段"}), 400
        
        result = asyncio.run(TOOL_REGISTRY.call("query_graph", {
            "query": data['query'],
            "parameters": data.get('parameters', {}),
            "user_id": data.get('user_id', 'anonymous')
        }))
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kg_flywheel_bp.route('/inspect', methods=['POST'])
def inspect():
    """
    直接质检端点
    
    Request Body:
        {
            "check_type": "full|completeness|consistency|accuracy",
            "user_id": "用户ID（可选）"
        }
    """
    try:
        data = request.get_json() or {}
        
        result = asyncio.run(TOOL_REGISTRY.call("run_quality_check", {
            "check_type": data.get('check_type', 'full'),
            "user_id": data.get('user_id', 'anonymous')
        }))
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kg_flywheel_bp.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """获取会话信息"""
    try:
        # 从请求参数获取 user_id
        user_id = request.args.get('user_id', 'anonymous')
        
        memory = create_kg_memory(user_id, session_id)
        summary = memory.get_session_summary()
        
        return jsonify(summary)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kg_flywheel_bp.route('/sessions/<session_id>/reports', methods=['GET'])
def list_reports(session_id: str):
    """列出会话的检查报告"""
    try:
        user_id = request.args.get('user_id', 'anonymous')
        
        memory = create_kg_memory(user_id, session_id)
        reports = memory.list_reports()
        
        return jsonify({
            "session_id": session_id,
            "reports": reports
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kg_flywheel_bp.route('/reports/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """获取详细报告"""
    try:
        user_id = request.args.get('user_id', 'anonymous')
        session_id = request.args.get('session_id')
        
        if not session_id:
            return jsonify({"error": "缺少 session_id 参数"}), 400
        
        memory = create_kg_memory(user_id, session_id)
        report = memory.get_report(report_id)
        
        if not report:
            return jsonify({"error": "报告不存在"}), 404
        
        return jsonify(report)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kg_flywheel_bp.route('/metrics', methods=['GET'])
def metrics():
    """
    Prometheus 指标端点
    暴露飞轮运行指标供监控采集
    """
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from .kg_flywheel_monitoring import REGISTRY
        
        return generate_latest(REGISTRY), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    except ImportError:
        # 如果没有安装 prometheus_client，返回基础指标
        from .kg_flywheel_tools import neo4j_connection_status
        
        basic_metrics = f"""# HELP kg_neo4j_connected Neo4j connection status
# TYPE kg_neo4j_connected gauge
kg_neo4j_connected{{uri="{neo4j_connection_status.get('uri', 'unknown')}"}} {1 if neo4j_connection_status.get('connected') else 0}

# HELP kg_driver_type Current driver type (1=neo4j, 0=mock)
# TYPE kg_driver_type gauge
kg_driver_type {1 if neo4j_connection_status.get('driver_type') == 'neo4j' else 0}
"""
        return basic_metrics, 200, {'Content-Type': 'text/plain; charset=utf-8'}


@kg_flywheel_bp.route('/graph/<session_id>', methods=['GET'])
def get_session_graph(session_id: str):
    """
    获取指定会话相关的知识图谱子图
    返回格式：{ nodes: [{id, name, type}], edges: [{source, target, relation}] }
    """
    try:
        from .kg_flywheel_tools import neo4j_driver
        
        user_id = request.args.get('user_id', 'anonymous')
        memory = create_kg_memory(user_id, session_id)
        
        # 从记忆中获取本次会话涉及的实体
        meta = memory._load_meta()
        recent_entities = meta.get("mentioned_entities", [])
        
        # 构建 Cypher 查询：获取这些实体及其1跳邻居
        if recent_entities:
            # 安全地转义实体名称
            escaped_entities = [e.replace('"', '\\"') for e in recent_entities]
            entity_list = '["' + '","'.join(escaped_entities) + '"]'
            cypher = f"""
            MATCH (n:Entity)-[r:RELATES]-(m:Entity)
            WHERE n.name IN {entity_list}
            RETURN n.name AS source, r.type AS relation, m.name AS target
            LIMIT 100
            """
        else:
            # 如果没有记录实体，返回最近创建的20个节点关系
            cypher = """
            MATCH (n:Entity)-[r:RELATES]-(m:Entity)
            RETURN n.name AS source, r.type AS relation, m.name AS target
            LIMIT 50
            """
        
        # 执行查询
        with neo4j_driver.session() as session:
            result = session.run(cypher)
            rows = result.data()
        
        # 构建节点集合和边集合
        nodes_set = {}
        edges = []
        
        for row in rows:
            source = row.get('source')
            target = row.get('target')
            relation = row.get('relation', 'RELATES')
            
            if source and target:
                # 添加节点（去重，保留类型信息）
                if source not in nodes_set:
                    nodes_set[source] = {"id": source, "label": source, "type": "Entity"}
                if target not in nodes_set:
                    nodes_set[target] = {"id": target, "label": target, "type": "Entity"}
                
                edges.append({
                    "source": source,
                    "target": target,
                    "relation": relation
                })
        
        nodes = list(nodes_set.values())
        
        return jsonify({
            "session_id": session_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# WebSocket 处理器
# =============================================================================

async def handle_ws_message(websocket, message: str, user_id: str = "anonymous"):
    """
    处理 WebSocket 消息
    
    消息格式：
    {
        "type": "chat|extract|query|inspect",
        "message": "...",
        "session_id": "..."
    }
    """
    try:
        data = json.loads(message)
        msg_type = data.get('type', 'chat')
        session_id = data.get('session_id')
        
        if msg_type == 'chat':
            # 创建 Agent 并处理
            agent = create_kg_flywheel_agent(user_id, session_id, TOOL_REGISTRY)
            
            # 发送阶段更新
            await websocket.send(json.dumps({
                "type": "stage_update",
                "stage": "extract",
                "status": "active"
            }))
            
            response = await agent.process(data.get('message', ''))
            
            # 发送回复
            await websocket.send(json.dumps({
                "type": "response",
                "payload": {
                    "reply": response.reply,
                    "session_id": response.session_id,
                    "state": response.state.value,
                    "data": response.data,
                    "tool_calls": response.tool_calls
                }
            }))
            
            # 发送统计更新
            await websocket.send(json.dumps({
                "type": "stats_update",
                "stats": {
                    "entities": response.data.get('summary', {}).get('entity_count', 0),
                    "relations": response.data.get('summary', {}).get('relation_count', 0),
                    "score": response.data.get('summary', {}).get('overall_score')
                }
            }))
            
        elif msg_type == 'extract':
            result = await TOOL_REGISTRY.call("extract_triples", {
                "text": data.get('text', ''),
                "source": data.get('source', 'ws'),
                "user_id": user_id
            })
            await websocket.send(json.dumps({
                "type": "extraction_result",
                "payload": result
            }))
            
        elif msg_type == 'query':
            result = await TOOL_REGISTRY.call("query_graph", {
                "query": data.get('query', ''),
                "user_id": user_id
            })
            await websocket.send(json.dumps({
                "type": "query_result",
                "payload": result
            }))
            
        elif msg_type == 'inspect':
            result = await TOOL_REGISTRY.call("run_quality_check", {
                "check_type": data.get('check_type', 'full'),
                "user_id": user_id
            })
            await websocket.send(json.dumps({
                "type": "inspection_result",
                "payload": result
            }))
            
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"未知消息类型: {msg_type}"
            }))
            
    except json.JSONDecodeError:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "无效的 JSON 格式"
        }))
    except Exception as e:
        await websocket.send(json.dumps({
            "type": "error",
            "message": str(e)
        }))


def register_websocket_handlers(sock):
    """注册 WebSocket 路由"""
    
    @sock.route('/ws/kg-flywheel')
    def kg_flywheel_ws(ws):
        """WebSocket 连接处理"""
        user_id = ws.receive().get('user_id', 'anonymous') if ws.receive() else 'anonymous'
        
        while True:
            try:
                message = ws.receive()
                if message is None:
                    break
                
                # 异步处理消息
                asyncio.run(handle_ws_message(ws, message, user_id))
                
            except Exception as e:
                ws.send(json.dumps({
                    "type": "error",
                    "message": str(e)
                }))
                break


# 导出
__all__ = [
    'kg_flywheel_bp',
    'register_websocket_handlers',
    'handle_ws_message'
]
