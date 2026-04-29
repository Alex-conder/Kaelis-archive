"""
工具管理 API

为前端 ToolsPage 提供工具列表和管理接口。
"""

from flask import Blueprint, jsonify, request

from core.tools.universal_tool_registry import ToolGateway, ToolRegistry
from core.security.file_gateway import FileGateway

tools_bp = Blueprint("tools", __name__, url_prefix="/api/mcp/tools")

_tool_gateway = ToolGateway()
_file_gateway = FileGateway()


@tools_bp.route("", methods=["GET"])
def list_tools():
    """获取已注册工具列表"""
    try:
        tools = _tool_gateway.list_tools()
        return jsonify({"success": True, "tools": tools})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_bp.route("/call", methods=["POST"])
def call_tool():
    """通过 ToolGateway 安全调用工具"""
    data = request.get_json() or {}
    source = data.get("source", "web_ui")
    tool_name = data.get("tool_name", "")
    params = data.get("params", {})

    try:
        import asyncio
        result = asyncio.run(_tool_gateway.execute(source, tool_name, params))
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 403


@tools_bp.route("/register", methods=["POST"])
def register_external_tool():
    """注册外部 MCP Tool"""
    data = request.get_json() or {}
    name = data.get("name", "")
    metadata = data.get("metadata", {})

    # 外部工具使用占位 handler（实际调用由外部服务处理）
    def external_handler(**kwargs):
        return {"status": "delegated", "tool": name, "params": kwargs}

    _tool_gateway.registry.register(name, external_handler, metadata)
    return jsonify({"success": True, "registered": name})


@tools_bp.route("/allowed_dirs", methods=["GET"])
def list_allowed_dirs():
    """获取文件网关授权目录白名单"""
    return jsonify({"success": True, "directories": _file_gateway.allowed_directories})


@tools_bp.route("/allowed_dirs", methods=["POST"])
def add_allowed_dir():
    """添加授权目录"""
    data = request.get_json() or {}
    path = data.get("path", "")
    ok = _file_gateway.add_allowed_directory(path)
    return jsonify({"success": ok, "directories": _file_gateway.allowed_directories})


@tools_bp.route("/allowed_dirs", methods=["DELETE"])
def remove_allowed_dir():
    """移除授权目录"""
    data = request.get_json() or {}
    path = data.get("path", "")
    ok = _file_gateway.remove_allowed_directory(path)
    return jsonify({"success": ok, "directories": _file_gateway.allowed_directories})
