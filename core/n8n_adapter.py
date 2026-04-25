"""
n8n Node Adapter (FEAT-005)

Converts n8n node definitions to Kaelis WorkflowNodeDefinition format.

Usage:
    from core.n8n_adapter import N8nNodeAdapter
    adapter = N8nNodeAdapter()
    kaelis_nodes = adapter.convert_batch(n8n_nodes)
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Map n8n property types to Kaelis config types
PROPERTY_TYPE_MAP = {
    "string": "string",
    "number": "number",
    "boolean": "boolean",
    "options": "select",
    "multiOptions": "multi_select",
    "json": "json",
    "collection": "object",
    "fixedCollection": "object",
    "dateTime": "string",
    "color": "string",
    "resourceLocator": "string",
}

# Map n8n group names to Kaelis categories
CATEGORY_MAP = {
    "input": "input",
    "output": "output",
    "transform": "general",
    "schedule": "control",
    "trigger": "control",
}

# Fallback icon mapping based on node name patterns
ICON_PATTERNS = [
    (r"http", "public"),
    (r"webhook", "webhook"),
    (r"email|mail", "mail"),
    (r"slack", "message"),
    (r"telegram", "send"),
    (r"discord", "message"),
    (r"google", "search"),
    (r"github", "code"),
    (r"git", "code"),
    (r"sql|database|postgres|mysql", "database"),
    (r"csv|excel|spreadsheet", "table"),
    (r"file", "folder"),
    (r"image|photo", "image"),
    (r"pdf", "file"),
    (r"json", "data"),
    (r"xml", "data"),
    (r"function|code|javascript|python", "code"),
    (r"if|switch|compare", "splitscreen"),
    (r"loop|repeat", "repeat"),
    (r"wait|delay|sleep", "timer"),
    (r"schedule|cron", "schedule"),
    (r"error|catch", "alert"),
    (r"merge|join|combine", "merge"),
    (r"split", "splitscreen"),
    (r"set|variable", "settings"),
]


def _guess_icon(node_name: str) -> str:
    """Guess a Kaelis icon from n8n node name."""
    name_lower = node_name.lower()
    for pattern, icon in ICON_PATTERNS:
        if re.search(pattern, name_lower):
            return icon
    return "build"


def _sanitize_id(raw_id: str) -> str:
    """Convert n8n node name to a valid Kaelis node ID."""
    # e.g. "n8n-nodes-base.httpRequest" -> "n8n_httpRequest"
    parts = raw_id.replace("-", "_").split(".")
    if len(parts) >= 2:
        return f"n8n_{parts[-1]}"
    return f"n8n_{raw_id}"


def _map_category(groups: List[str]) -> str:
    """Map n8n group to Kaelis category."""
    if not groups:
        return "general"
    primary = groups[0].lower()
    return CATEGORY_MAP.get(primary, primary if primary in CATEGORY_MAP.values() else "general")


def _map_property_type(prop_type: str) -> str:
    """Map n8n property type to Kaelis config type."""
    return PROPERTY_TYPE_MAP.get(prop_type, "string")


def _convert_property(prop: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a single n8n property to Kaelis config field."""
    prop_name = prop.get("name")
    if not prop_name:
        return None
    result = {
        "type": _map_property_type(prop.get("type", "string")),
        "default": prop.get("default"),
    }

    # Handle options type
    if prop.get("type") == "options" and "options" in prop:
        result["options"] = [opt.get("value", opt.get("name")) for opt in prop["options"]]

    # Handle number min/max if present
    if prop.get("type") == "number":
        if "minValue" in prop:
            result["min"] = prop["minValue"]
        if "maxValue" in prop:
            result["max"] = prop["maxValue"]

    return result


def _build_inputs(n8n_inputs: List[str]) -> List[Dict[str, Any]]:
    """Build Kaelis inputs from n8n inputs."""
    if not n8n_inputs:
        return []
    return [
        {
            "name": "input",
            "type": "any",
            "required": True,
            "description": "Main input from previous node",
        }
    ]


def _build_outputs(n8n_outputs: List[str]) -> List[Dict[str, Any]]:
    """Build Kaelis outputs from n8n outputs."""
    if not n8n_outputs:
        return []
    return [
        {
            "name": "output",
            "type": "any",
            "description": "Main output to next node",
        }
    ]


class N8nNodeAdapter:
    """Adapter to convert n8n node definitions to Kaelis format."""

    def convert(self, n8n_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert a single n8n node to Kaelis WorkflowNodeDefinition.

        Args:
            n8n_node: n8n node definition dict

        Returns:
            Kaelis-compatible node dict, or None if conversion fails
        """
        try:
            raw_name = n8n_node.get("name", "")
            if not raw_name:
                return None
            display_name = n8n_node.get("displayName") or n8n_node.get("defaults", {}).get("name", raw_name)
            description = n8n_node.get("description", "")
            groups = n8n_node.get("group", [])
            if isinstance(groups, str):
                groups = [groups]

            # Build config from properties
            config: Dict[str, Any] = {}
            for prop in n8n_node.get("properties", []):
                prop_name = prop.get("name")
                if not prop_name:
                    continue
                converted = _convert_property(prop)
                if converted is not None:
                    config[prop_name] = converted

            kaelis_node = {
                "id": _sanitize_id(raw_name),
                "type": "action",
                "name": display_name,
                "description": description,
                "icon": _guess_icon(raw_name),
                "category": _map_category(groups),
                "inputs": _build_inputs(n8n_node.get("inputs", [])),
                "outputs": _build_outputs(n8n_node.get("outputs", [])),
                "config": config,
                "metadata": {
                    "source": "n8n",
                    "original_name": raw_name,
                    "version": n8n_node.get("version"),
                },
            }

            logger.debug(f"Converted n8n node '{raw_name}' -> '{kaelis_node['id']}'")
            return kaelis_node

        except Exception as e:
            logger.warning(f"Failed to convert n8n node: {e}")
            return None

    def convert_batch(self, n8n_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert a batch of n8n nodes.

        Args:
            n8n_nodes: List of n8n node definitions

        Returns:
            List of successfully converted Kaelis nodes
        """
        results = []
        for node in n8n_nodes:
            converted = self.convert(node)
            if converted:
                results.append(converted)
        logger.info(f"Converted {len(results)}/{len(n8n_nodes)} n8n nodes")
        return results

    def parse_jsonl(self, jsonl_text: str) -> List[Dict[str, Any]]:
        """Parse n8n nodes from JSONL format (one JSON object per line)."""
        nodes = []
        for line in jsonl_text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json
                nodes.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return nodes

    def parse_json(self, json_text: str) -> List[Dict[str, Any]]:
        """Parse n8n nodes from JSON format (array or single object)."""
        import json
        data = json.loads(json_text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Could be a single node or a wrapped response
            if "nodes" in data:
                return data["nodes"]
            return [data]
        return []
