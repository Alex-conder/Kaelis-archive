"""
Observability API routes for Kaelis.

- GET /api/observability/metrics  - Current aggregated metrics
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from core.observability.otel_setup import get_metrics, reset_metrics

logger = logging.getLogger(__name__)

observability_bp = Blueprint("observability", __name__, url_prefix="/api/observability")


@observability_bp.route("/metrics", methods=["GET"])
def observability_metrics():
    """
    Return current aggregated observability metrics.

    Response:
        {
            "call_count": int,
            "error_count": int,
            "avg_latency_ms": float,
            "error_rate": float,
            "window_size": int,
            "timestamp": str
        }
    """
    metrics = get_metrics()
    metrics["timestamp"] = datetime.now(timezone.utc).isoformat()
    return jsonify(metrics), 200


@observability_bp.route("/metrics/reset", methods=["POST"])
def observability_metrics_reset():
    """Reset aggregated metrics (admin/debug use)."""
    reset_metrics()
    return jsonify({"success": True, "message": "Metrics reset", "timestamp": datetime.now(timezone.utc).isoformat()}), 200
