"""
Mesh API Routes (P23-A)

Endpoints:
    POST /api/mesh/handshake       -> Challenge-response identity verification
    POST /api/mesh/heartbeat       -> Peer liveness probe
    POST /api/mesh/memory/digests  -> Get public memory digests
    POST /api/mesh/memory/get      -> Get specific memory entry
    POST /api/mesh/invoke          -> Remote MCP tool invocation
    GET  /api/mesh/peers           -> List known peers
    POST /api/mesh/sync            -> Trigger gossip sync with a peer
"""

import logging
from flask import Blueprint, request, jsonify

from core.mesh.identity import get_node_identity
from core.mesh.transport import get_mesh_transport
from core.mesh.gossip import get_gossip_protocol
from core.mesh.discovery import get_discovery_service
from core.mesh.authorization import get_authorization_manager

logger = logging.getLogger(__name__)

mesh_bp = Blueprint("mesh", __name__, url_prefix="/api/mesh")


@mesh_bp.route("/handshake", methods=["POST"])
def mesh_handshake():
    """Handle incoming handshake request."""
    data = request.get_json() or {}
    transport = get_mesh_transport()
    result = transport.handle_handshake(data)
    return jsonify(result), 200 if result.get("success") else 403


@mesh_bp.route("/heartbeat", methods=["POST"])
def mesh_heartbeat():
    """Handle incoming heartbeat."""
    data = request.get_json() or {}
    transport = get_mesh_transport()
    result = transport.handle_heartbeat(data)
    return jsonify(result)


@mesh_bp.route("/memory/digests", methods=["POST"])
def mesh_memory_digests():
    """Return public memory digests for sync."""
    data = request.get_json() or {}
    gossip = get_gossip_protocol()
    result = gossip.handle_digests_request(data)
    return jsonify(result)


@mesh_bp.route("/memory/get", methods=["POST"])
def mesh_memory_get():
    """Return a specific memory entry."""
    data = request.get_json() or {}
    gossip = get_gossip_protocol()
    result = gossip.handle_memory_get(data)
    return jsonify(result)


@mesh_bp.route("/invoke", methods=["POST"])
def mesh_invoke():
    """Handle remote MCP tool invocation."""
    data = request.get_json() or {}
    auth_header = request.headers.get("Authorization", "")
    auth_token = None
    if auth_header.startswith("Bearer "):
        auth_token = auth_header[7:]

    transport = get_mesh_transport()
    result = transport.handle_invoke(data, auth_token=auth_token)
    status = 200 if result.get("success") else 403
    return jsonify(result), status


@mesh_bp.route("/peers", methods=["GET"])
def mesh_peers():
    """List all known peers."""
    transport = get_mesh_transport()
    discovery = get_discovery_service()
    return jsonify({
        "success": True,
        "data": {
            "self": {
                "kni": get_node_identity().kni,
                "display_name": get_node_identity().display_name,
            },
            "peers": transport.list_sessions(),
            "discovered": discovery.get_peers(),
        }
    })


@mesh_bp.route("/sync", methods=["POST"])
def mesh_sync():
    """Trigger gossip sync with a specific peer or random peer."""
    data = request.get_json() or {}
    target_kni = data.get("target_kni")
    gossip = get_gossip_protocol()

    if target_kni:
        result = gossip.sync_with_peer(target_kni)
    else:
        result = gossip.gossip_round()

    return jsonify({
        "success": result.get("success", False),
        "data": result,
    })


# --------------------------------------------------------------------------- #
# Authorization endpoints
# --------------------------------------------------------------------------- #

@mesh_bp.route("/auth/request", methods=["POST"])
def mesh_auth_request():
    """Receive an access request from a remote peer."""
    data = request.get_json() or {}
    request_id = data.get("request_id")
    requester_kni = data.get("requester_kni")
    resource_type = data.get("resource_type")
    actions = data.get("actions", [])

    if not all([request_id, requester_kni, resource_type]):
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    try:
        from core.memory_manager_v2 import get_memory_manager
        mm = get_memory_manager()
        pending = mm.read(layer="L0", key="mesh_pending_requests", user_id="system")
        requests = []
        if pending and isinstance(pending.get("value"), list):
            requests = pending["value"]

        # Deduplicate by request_id
        if any(r.get("id") == request_id for r in requests):
            return jsonify({"success": True, "message": "Request already recorded"})

        requests.append({
            "id": request_id,
            "requester_kni": requester_kni,
            "target_kni": get_node_identity().kni,
            "resource_type": resource_type,
            "actions": actions,
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
        return jsonify({"success": True, "request_id": request_id})
    except Exception as e:
        logger.exception("Failed to record auth request")
        return jsonify({"success": False, "error": str(e)}), 500


@mesh_bp.route("/auth/pending", methods=["GET"])
def mesh_auth_pending():
    """List pending access requests."""
    try:
        from core.memory_manager_v2 import get_memory_manager
        mm = get_memory_manager()
        pending = mm.read(layer="L0", key="mesh_pending_requests", user_id="system")
        requests = []
        if pending and isinstance(pending.get("value"), list):
            requests = [r for r in pending["value"] if r.get("status") == "pending"]
        return jsonify({"success": True, "data": {"requests": requests}})
    except Exception as e:
        logger.exception("Failed to list pending requests")
        return jsonify({"success": False, "error": str(e)}), 500


@mesh_bp.route("/auth/approve", methods=["POST"])
def mesh_auth_approve():
    """Approve a pending access request and issue a token."""
    data = request.get_json() or {}
    request_id = data.get("request_id")
    approved_actions = data.get("approved_actions", [])

    if not request_id:
        return jsonify({"success": False, "error": "Missing request_id"}), 400

    try:
        from core.memory_manager_v2 import get_memory_manager
        mm = get_memory_manager()
        pending = mm.read(layer="L0", key="mesh_pending_requests", user_id="system")
        if not pending or not isinstance(pending.get("value"), list):
            return jsonify({"success": False, "error": "No pending requests found"}), 404

        requests = pending["value"]
        req = None
        for r in requests:
            if r.get("id") == request_id:
                req = r
                break

        if not req:
            return jsonify({"success": False, "error": f"Request {request_id} not found"}), 404

        auth = get_authorization_manager()
        perm_id = auth.grant_permission(
            requester_kni=req["requester_kni"],
            resource_type=req["resource_type"],
            resource_id="*",
            actions=approved_actions,
        )

        token = auth.create_token(
            issuer_kni=get_node_identity().kni,
            subject_kni=req["requester_kni"],
            permissions=[{
                "resource_type": req["resource_type"],
                "resource_id": "*",
                "actions": approved_actions,
            }],
            ttl_hours=24,
        )

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

        return jsonify({
            "success": True,
            "permission_id": perm_id,
            "token": token,
            "message": f"Access granted to {req['requester_kni']}",
        })
    except Exception as e:
        logger.exception("Failed to approve auth request")
        return jsonify({"success": False, "error": str(e)}), 500


@mesh_bp.route("/discover", methods=["POST"])
def mesh_discover():
    """Start discovery and optionally perform handshakes."""
    data = request.get_json() or {}
    duration = data.get("duration", 5)
    auto_handshake = data.get("auto_handshake", True)

    discovery = get_discovery_service()
    transport = get_mesh_transport()

    # Ensure discovery is running
    if not discovery._registered:
        discovery.start()

    peers = discovery.discover(duration=duration)

    handshakes = {}
    if auto_handshake:
        for p in peers:
            kni = p["kni"]
            transport.register_peer(kni, p["host"], p["port"], p["capabilities"])
            handshakes[kni] = transport.perform_handshake(kni)

    return jsonify({
        "success": True,
        "data": {
            "peers_discovered": len(peers),
            "peers": peers,
            "handshakes": handshakes,
        }
    })
