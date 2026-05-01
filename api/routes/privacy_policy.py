"""Privacy Policy Management API — Auto-classification rules for memory privacy levels.

Allows users to define rules that automatically assign privacy_level to new memories
based on keywords, source patterns, or key prefixes.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from core.memory_manager_v2 import get_memory_manager

logger = logging.getLogger(__name__)

privacy_policy_bp = Blueprint("privacy_policy", __name__, url_prefix="/api/privacy-policy")

RULES_KEY = "privacy_policy_rules"
DEFAULT_RULES = [
    {"id": "rule_1", "pattern": "password", "match_type": "key_contains", "privacy_level": "private", "priority": 100},
    {"id": "rule_2", "pattern": "api_key", "match_type": "key_contains", "privacy_level": "private", "priority": 100},
    {"id": "rule_3", "pattern": "public", "match_type": "key_contains", "privacy_level": "public", "priority": 10},
    {"id": "rule_4", "pattern": "team", "match_type": "key_contains", "privacy_level": "team", "priority": 10},
]


def _get_user_id() -> str:
    return request.headers.get("X-User-ID", "anonymous")


def _load_rules(user_id: str) -> List[Dict[str, Any]]:
    try:
        mm = get_memory_manager()
        stored = mm.read("L0", RULES_KEY, user_id=user_id)
        if stored and isinstance(stored, dict) and "value" in stored:
            rules = stored["value"]
            if isinstance(rules, list):
                return rules
    except Exception as e:
        logger.debug("Failed to load privacy rules: %s", e)
    return [r.copy() for r in DEFAULT_RULES]


def _save_rules(user_id: str, rules: List[Dict[str, Any]]) -> bool:
    try:
        mm = get_memory_manager()
        mm.write(
            "L0",
            RULES_KEY,
            rules,
            metadata={"source": "privacy_policy", "updated_at": datetime.now(timezone.utc).isoformat()},
            user_id=user_id,
        )
        return True
    except Exception as e:
        logger.error("Failed to save privacy rules: %s", e)
        return False


def _apply_rules(key: str, source: str, rules: List[Dict[str, Any]]) -> str:
    """Determine privacy level for a memory key based on rules."""
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 0), reverse=True)
    for rule in sorted_rules:
        pattern = rule.get("pattern", "")
        match_type = rule.get("match_type", "key_contains")
        if match_type == "key_contains" and pattern.lower() in key.lower():
            return rule.get("privacy_level", "private")
        if match_type == "source_equals" and pattern.lower() == source.lower():
            return rule.get("privacy_level", "private")
        if match_type == "key_prefix" and key.lower().startswith(pattern.lower()):
            return rule.get("privacy_level", "private")
    return "private"


@privacy_policy_bp.route("/rules", methods=["GET"])
def get_rules():
    """Get current privacy classification rules."""
    user_id = _get_user_id()
    rules = _load_rules(user_id)
    return jsonify({"success": True, "data": {"rules": rules, "default": DEFAULT_RULES}})


@privacy_policy_bp.route("/rules", methods=["POST"])
def add_rule():
    """Add a new privacy classification rule."""
    user_id = _get_user_id()
    data = request.get_json() or {}

    pattern = data.get("pattern", "").strip()
    match_type = data.get("match_type", "key_contains")
    privacy_level = data.get("privacy_level", "private")
    priority = data.get("priority", 10)

    if not pattern:
        return jsonify({"success": False, "error": "pattern is required"}), 400

    if privacy_level not in ("public", "team", "private"):
        return jsonify({"success": False, "error": "privacy_level must be public/team/private"}), 400

    rules = _load_rules(user_id)
    new_rule = {
        "id": f"rule_{datetime.now(timezone.utc).timestamp()}",
        "pattern": pattern,
        "match_type": match_type,
        "privacy_level": privacy_level,
        "priority": priority,
    }
    rules.append(new_rule)

    if _save_rules(user_id, rules):
        return jsonify({"success": True, "data": {"rule": new_rule}})
    return jsonify({"success": False, "error": "Failed to save rule"}), 500


@privacy_policy_bp.route("/rules/<rule_id>", methods=["DELETE"])
def delete_rule(rule_id: str):
    """Delete a privacy classification rule."""
    user_id = _get_user_id()
    rules = _load_rules(user_id)
    filtered = [r for r in rules if r.get("id") != rule_id]

    if len(filtered) == len(rules):
        return jsonify({"success": False, "error": "Rule not found"}), 404

    if _save_rules(user_id, filtered):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Failed to save rules"}), 500


@privacy_policy_bp.route("/preview", methods=["POST"])
def preview_classification():
    """Preview what privacy level a key would get under current rules."""
    user_id = _get_user_id()
    data = request.get_json() or {}
    key = data.get("key", "")
    source = data.get("source", "")

    if not key:
        return jsonify({"success": False, "error": "key is required"}), 400

    rules = _load_rules(user_id)
    level = _apply_rules(key, source, rules)
    matched = []
    for rule in sorted(rules, key=lambda r: r.get("priority", 0), reverse=True):
        pattern = rule.get("pattern", "")
        match_type = rule.get("match_type", "key_contains")
        if match_type == "key_contains" and pattern.lower() in key.lower():
            matched.append(rule)
        elif match_type == "source_equals" and pattern.lower() == source.lower():
            matched.append(rule)
        elif match_type == "key_prefix" and key.lower().startswith(pattern.lower()):
            matched.append(rule)

    return jsonify({"success": True, "data": {"key": key, "privacy_level": level, "matched_rules": matched}})


@privacy_policy_bp.route("/stats", methods=["GET"])
def get_privacy_stats():
    """Get memory distribution by privacy level."""
    user_id = _get_user_id()
    stats = {"L0": {}, "L1": {}, "L2": {}, "L3": {}, "total": {}}

    try:
        mm = get_memory_manager()
        for layer in ["L1", "L2"]:
            try:
                results = mm.search_by_privacy_level(layer, "public", top_k=1000, user_id=user_id)
                stats[layer]["public"] = len(results)
                results = mm.search_by_privacy_level(layer, "team", top_k=1000, user_id=user_id)
                stats[layer]["team"] = len(results)
                results = mm.search_by_privacy_level(layer, "private", top_k=1000, user_id=user_id)
                stats[layer]["private"] = len(results)
            except Exception as e:
                logger.debug("Privacy stats for %s failed: %s", layer, e)
                stats[layer] = {"error": str(e)}

        # Totals
        for level in ["public", "team", "private"]:
            stats["total"][level] = sum(stats.get(l, {}).get(level, 0) for l in ["L0", "L1", "L2", "L3"] if isinstance(stats.get(l), dict))

    except Exception as e:
        logger.error("Privacy stats failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "data": stats})
