"""
Kaelis MCP Mesh Tools
=====================
跨节点互联 MCP Tools：节点发现、授权请求、远程调用。

用法:
    from core.mcp.mesh_tools import register_mesh_tools
    register_mesh_tools(mcp)
"""

import json
import logging
from typing import Any

from core.mesh.identity import get_node_identity
from core.mesh.discovery import get_discovery_service
from core.mesh.authorization import get_authorization_manager

logger = logging.getLogger(__name__)


def register_mesh_tools(mcp: Any):
    """向 FastMCP 实例注册 Mesh 相关 Tools。"""

    # ==================================================================
    # mesh_list_nodes
    # ==================================================================

    @mcp.tool()
    def mesh_list_nodes() -> str:
        """
        列出本地网络中发现的和已授权的 Kaelis 节点。

        Returns:
            JSON 字符串，包含 discovered_nodes 和 authorized_peers
        """
        try:
            disc = get_discovery_service()
            peers = disc.get_peers()

            auth = get_authorization_manager()
            perms = auth.list_permissions()

            # 构建节点信息
            nodes = []
            for p in peers:
                nodes.append({
                    "kni": p["kni"],
                    "display_name": p["display_name"],
                    "host": p["host"],
                    "port": p["port"],
                    "capabilities": p["capabilities"],
                    "status": "discovered",
                })

            # 去重：已授权但尚未发现的也加入
            discovered_knis = {p["kni"] for p in peers}
            for perm in perms:
                kni = perm.get("requester_kni")
                if kni and kni not in discovered_knis:
                    nodes.append({
                        "kni": kni,
                        "status": "authorized_only",
                        "permissions": [{
                            "resource_type": perm.get("resource_type"),
                            "resource_id": perm.get("resource_id"),
                            "actions": perm.get("actions"),
                        }],
                    })

            return json.dumps({
                "success": True,
                "count": len(nodes),
                "nodes": nodes,
                "self": {
                    "kni": get_node_identity().kni,
                    "display_name": get_node_identity().display_name,
                },
            }, ensure_ascii=False)

        except Exception as e:
            logger.exception("mesh_list_nodes failed")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ==================================================================
    # mesh_request_access
    # ==================================================================

    @mcp.tool()
    def mesh_request_access(target_kni: str, resource_type: str, actions: str) -> str:
        """
        向目标节点发送授权请求。

        Args:
            target_kni: 目标节点 KNI
            resource_type: 资源类型（memory, skill, space 等）
            actions: 逗号分隔的操作列表（read, write, delete）

        Returns:
            JSON 字符串，包含 request_id
        """
        try:
            action_list = [a.strip() for a in actions.split(",") if a.strip()]
            request_id = f"req_{get_node_identity().kni}_{target_kni}_{resource_type}_{int(__import__('time').time())}"

            # Try to send request over network if target is a known active peer
            sent_over_network = False
            try:
                from core.mesh.transport import get_mesh_transport
                transport = get_mesh_transport()
                sess = transport.get_session(target_kni)
                if sess and sess.status == "active":
                    import requests
                    url = f"http://{sess.host}:{sess.port}/api/mesh/auth/request"
                    resp = requests.post(
                        url,
                        json={
                            "request_id": request_id,
                            "requester_kni": get_node_identity().kni,
                            "resource_type": resource_type,
                            "actions": action_list,
                        },
                        headers={"Authorization": f"Bearer {sess.token}"} if sess.token else {},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        sent_over_network = True
            except Exception as e:
                logger.debug("Network send failed, falling back to local queue: %s", e)

            # If network send failed or target not active, record locally
            if not sent_over_network:
                mm = __import__("core.memory_manager_v2", fromlist=["get_memory_manager"]).get_memory_manager()
                pending = mm.read(layer="L0", key="mesh_pending_requests", user_id="system")
                requests = []
                if pending and isinstance(pending.get("value"), list):
                    requests = pending["value"]

                requests.append({
                    "id": request_id,
                    "requester_kni": get_node_identity().kni,
                    "target_kni": target_kni,
                    "resource_type": resource_type,
                    "actions": action_list,
                    "status": "pending",
                    "requested_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                })

                mm.write(
                    layer="L0",
                    key="mesh_pending_requests",
                    value=requests,
                    metadata={"type": "mesh_request"},
                    user_id="system",
                    agent_id="kaelis_self",
                )

            return json.dumps({
                "success": True,
                "request_id": request_id,
                "sent_over_network": sent_over_network,
                "message": f"Access request {'sent to' if sent_over_network else 'queued for'} {target_kni}. Waiting for approval.",
            }, ensure_ascii=False)

        except Exception as e:
            logger.exception("mesh_request_access failed")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ==================================================================
    # mesh_grant_access
    # ==================================================================

    @mcp.tool()
    def mesh_grant_access(request_id: str, approved_actions: str) -> str:
        """
        批准授权请求。

        Args:
            request_id: 请求 ID
            approved_actions: 逗号分隔的批准操作列表

        Returns:
            JSON 字符串，包含 granted token
        """
        try:
            mm = __import__("core.memory_manager_v2", fromlist=["get_memory_manager"]).get_memory_manager()
            pending = mm.read(layer="L0", key="mesh_pending_requests", user_id="system")
            if not pending or not isinstance(pending.get("value"), list):
                return json.dumps({"success": False, "error": "No pending requests found"}, ensure_ascii=False)

            requests = pending["value"]
            req = None
            for r in requests:
                if r.get("id") == request_id:
                    req = r
                    break

            if not req:
                return json.dumps({"success": False, "error": f"Request {request_id} not found"}, ensure_ascii=False)

            action_list = [a.strip() for a in approved_actions.split(",") if a.strip()]

            # 记录授权
            auth = get_authorization_manager()
            perm_id = auth.grant_permission(
                requester_kni=req["requester_kni"],
                resource_type=req["resource_type"],
                resource_id="*",  # 未来可细化到具体资源
                actions=action_list,
            )

            # 签发 JWT
            token = auth.create_token(
                issuer_kni=get_node_identity().kni,
                subject_kni=req["requester_kni"],
                permissions=[{
                    "resource_type": req["resource_type"],
                    "resource_id": "*",
                    "actions": action_list,
                }],
                ttl_hours=24,
            )

            # 更新请求状态
            req["status"] = "granted"
            req["granted_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            req["permission_id"] = perm_id
            mm.write(
                layer="L0",
                key="mesh_pending_requests",
                value=requests,
                metadata={"type": "mesh_request"},
                user_id="system",
                agent_id="kaelis_self",
            )

            return json.dumps({
                "success": True,
                "permission_id": perm_id,
                "token": token,
                "message": f"Access granted to {req['requester_kni']}",
            }, ensure_ascii=False)

        except Exception as e:
            logger.exception("mesh_grant_access failed")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    # ==================================================================
    # mesh_call_remote
    # ==================================================================

    @mcp.tool()
    def mesh_call_remote(target_kni: str, tool_name: str, params_json: str) -> str:
        """
        携带 JWT 调用远程节点的 MCP Tool。

        Args:
            target_kni: 目标节点 KNI
            tool_name: 远程 Tool 名称
            params_json: Tool 参数 JSON 字符串

        Returns:
            JSON 字符串，包含远程调用结果
        """
        try:
            auth = get_authorization_manager()

            # 检查是否有权限
            if not auth.check_permission(
                requester_kni=get_node_identity().kni,
                resource_type="mcp_tool",
                resource_id=tool_name,
                action="execute",
            ):
                return json.dumps({
                    "success": False,
                    "error": f"No permission to execute {tool_name} on {target_kni}",
                }, ensure_ascii=False)

            # 查找目标节点地址
            disc = get_discovery_service()
            peers = disc.get_peers()
            target = next((p for p in peers if p["kni"] == target_kni), None)
            if not target:
                return json.dumps({
                    "success": False,
                    "error": f"Node {target_kni} not found in local network",
                }, ensure_ascii=False)

            # 生成 JWT（证明自己身份和权限）
            token = auth.create_token(
                issuer_kni=get_node_identity().kni,
                subject_kni=target_kni,
                permissions=[{"resource_type": "mcp_tool", "resource_id": tool_name, "actions": ["execute"]}],
                ttl_hours=1,
            )

            # Perform actual HTTP call via mesh transport
            from core.mesh.transport import get_mesh_transport
            transport = get_mesh_transport()
            result = transport.invoke_remote(
                target_kni,
                tool_name,
                json.loads(params_json),
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        except Exception as e:
            logger.exception("mesh_call_remote failed")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    logger.info("Mesh tools registered: mesh_list_nodes, mesh_request_access, mesh_grant_access, mesh_call_remote")
