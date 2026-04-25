"""Tests for FEAT-005: n8n Node Import Adapter."""

import pytest
from core.n8n_adapter import (
    N8nNodeAdapter,
    _sanitize_id,
    _guess_icon,
    _map_category,
    _map_property_type,
    _convert_property,
    _build_inputs,
    _build_outputs,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    return N8nNodeAdapter()


@pytest.fixture
def sample_http_node():
    return {
        "name": "n8n-nodes-base.httpRequest",
        "displayName": "HTTP Request",
        "description": "Makes an HTTP request and returns the response data",
        "group": ["transform"],
        "version": 1,
        "inputs": ["main"],
        "outputs": ["main"],
        "properties": [
            {
                "name": "method",
                "type": "options",
                "default": "GET",
                "options": [
                    {"name": "GET", "value": "GET"},
                    {"name": "POST", "value": "POST"},
                ],
            },
            {
                "name": "url",
                "type": "string",
                "default": "",
            },
            {
                "name": "timeout",
                "type": "number",
                "default": 5000,
                "minValue": 1,
                "maxValue": 300000,
            },
            {
                "name": "allowUnauthorizedCerts",
                "type": "boolean",
                "default": False,
            },
        ],
    }


@pytest.fixture
def sample_slack_node():
    return {
        "name": "n8n-nodes-base.slack",
        "displayName": "Slack",
        "description": "Send messages to Slack",
        "group": ["output"],
        "version": 2,
        "inputs": ["main"],
        "outputs": ["main"],
        "properties": [
            {"name": "channel", "type": "string", "default": ""},
            {"name": "text", "type": "string", "default": ""},
        ],
    }


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

def test_sanitize_id_with_package_prefix():
    assert _sanitize_id("n8n-nodes-base.httpRequest") == "n8n_httpRequest"
    assert _sanitize_id("n8n-nodes-base.slack") == "n8n_slack"


def test_sanitize_id_without_package():
    assert _sanitize_id("httpRequest") == "n8n_httpRequest"
    assert _sanitize_id("some-node") == "n8n_some-node"


def test_guess_icon_http():
    assert _guess_icon("n8n-nodes-base.httpRequest") == "public"
    assert _guess_icon("HTTP Request") == "public"


def test_guess_icon_slack():
    assert _guess_icon("slack") == "message"
    assert _guess_icon("Send Slack Message") == "message"


def test_guess_icon_database():
    assert _guess_icon("postgres") == "database"
    assert _guess_icon("MySQL") == "database"


def test_guess_icon_fallback():
    assert _guess_icon("unknownNode") == "build"


def test_map_category_known_groups():
    assert _map_category(["input"]) == "input"
    assert _map_category(["output"]) == "output"
    assert _map_category(["transform"]) == "general"
    assert _map_category(["schedule"]) == "control"


def test_map_category_unknown_group():
    assert _map_category(["custom"]) == "general"


def test_map_category_empty():
    assert _map_category([]) == "general"


def test_map_category_string_group():
    # Groups may sometimes be a single string
    assert _map_category(["trigger"]) == "control"


def test_map_property_type_known():
    assert _map_property_type("string") == "string"
    assert _map_property_type("number") == "number"
    assert _map_property_type("boolean") == "boolean"
    assert _map_property_type("options") == "select"
    assert _map_property_type("multiOptions") == "multi_select"
    assert _map_property_type("json") == "json"
    assert _map_property_type("collection") == "object"


def test_map_property_type_unknown_fallback():
    assert _map_property_type("weirdType") == "string"


def test_convert_property_string():
    prop = {"name": "url", "type": "string", "default": "http://example.com"}
    result = _convert_property(prop)
    assert result == {"type": "string", "default": "http://example.com"}


def test_convert_property_number_with_range():
    prop = {"name": "timeout", "type": "number", "default": 5000, "minValue": 1, "maxValue": 100}
    result = _convert_property(prop)
    assert result["type"] == "number"
    assert result["min"] == 1
    assert result["max"] == 100


def test_convert_property_options():
    prop = {
        "name": "method",
        "type": "options",
        "default": "GET",
        "options": [
            {"name": "GET", "value": "GET"},
            {"name": "POST", "value": "POST"},
        ],
    }
    result = _convert_property(prop)
    assert result["type"] == "select"
    assert result["options"] == ["GET", "POST"]


def test_convert_property_boolean():
    prop = {"name": "flag", "type": "boolean", "default": True}
    result = _convert_property(prop)
    assert result["type"] == "boolean"
    assert result["default"] is True


def test_build_inputs_with_main():
    result = _build_inputs(["main"])
    assert len(result) == 1
    assert result[0]["name"] == "input"
    assert result[0]["required"] is True


def test_build_inputs_empty():
    assert _build_inputs([]) == []
    assert _build_inputs(None) == []


def test_build_outputs_with_main():
    result = _build_outputs(["main"])
    assert len(result) == 1
    assert result[0]["name"] == "output"


def test_build_outputs_empty():
    assert _build_outputs([]) == []
    assert _build_outputs(None) == []


# ---------------------------------------------------------------------------
# Adapter.convert() tests
# ---------------------------------------------------------------------------

def test_convert_http_node(adapter, sample_http_node):
    result = adapter.convert(sample_http_node)
    assert result is not None
    assert result["id"] == "n8n_httpRequest"
    assert result["name"] == "HTTP Request"
    assert result["type"] == "action"
    assert result["category"] == "general"
    assert result["icon"] == "public"
    assert result["metadata"]["source"] == "n8n"
    assert result["metadata"]["original_name"] == "n8n-nodes-base.httpRequest"

    # Inputs / outputs
    assert len(result["inputs"]) == 1
    assert len(result["outputs"]) == 1

    # Config fields
    config = result["config"]
    assert "method" in config
    assert config["method"]["type"] == "select"
    assert config["method"]["options"] == ["GET", "POST"]
    assert config["url"]["type"] == "string"
    assert config["timeout"]["type"] == "number"
    assert config["timeout"]["min"] == 1
    assert config["timeout"]["max"] == 300000
    assert config["allowUnauthorizedCerts"]["type"] == "boolean"


def test_convert_slack_node(adapter, sample_slack_node):
    result = adapter.convert(sample_slack_node)
    assert result is not None
    assert result["id"] == "n8n_slack"
    assert result["name"] == "Slack"
    assert result["category"] == "output"
    assert result["icon"] == "message"
    assert "channel" in result["config"]
    assert "text" in result["config"]


def test_convert_missing_name_returns_none(adapter):
    result = adapter.convert({"displayName": "No Name"})
    assert result is None


def test_convert_empty_dict_returns_none(adapter):
    result = adapter.convert({})
    assert result is None


def test_convert_group_as_string(adapter):
    node = {
        "name": "n8n-nodes-base.scheduleTrigger",
        "displayName": "Schedule Trigger",
        "group": "schedule",
        "inputs": [],
        "outputs": ["main"],
        "properties": [],
    }
    result = adapter.convert(node)
    assert result is not None
    assert result["category"] == "control"


def test_convert_with_defaults_name(adapter):
    node = {
        "name": "n8n-nodes-base.foo",
        "defaults": {"name": "Foo Default"},
        "group": ["transform"],
        "inputs": ["main"],
        "outputs": ["main"],
        "properties": [],
    }
    result = adapter.convert(node)
    assert result["name"] == "Foo Default"


# ---------------------------------------------------------------------------
# Batch conversion tests
# ---------------------------------------------------------------------------

def test_convert_batch(adapter, sample_http_node, sample_slack_node):
    results = adapter.convert_batch([sample_http_node, sample_slack_node])
    assert len(results) == 2
    ids = {r["id"] for r in results}
    assert ids == {"n8n_httpRequest", "n8n_slack"}


def test_convert_batch_skips_invalid(adapter, sample_http_node):
    results = adapter.convert_batch([sample_http_node, {"displayName": "Bad"}, {}])
    assert len(results) == 1
    assert results[0]["id"] == "n8n_httpRequest"


def test_convert_batch_empty_list(adapter):
    assert adapter.convert_batch([]) == []


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

def test_parse_jsonl(adapter):
    jsonl = '{"name":"a","displayName":"A"}\n{"name":"b","displayName":"B"}'
    nodes = adapter.parse_jsonl(jsonl)
    assert len(nodes) == 2
    assert nodes[0]["name"] == "a"


def test_parse_jsonl_skips_invalid_lines(adapter):
    jsonl = '{"name":"a"}\nnot json\n{"name":"b"}'
    nodes = adapter.parse_jsonl(jsonl)
    assert len(nodes) == 2


def test_parse_json_array(adapter):
    json_text = '[{"name":"a"},{"name":"b"}]'
    nodes = adapter.parse_json(json_text)
    assert len(nodes) == 2


def test_parse_json_single_object(adapter):
    json_text = '{"name":"a","displayName":"A"}'
    nodes = adapter.parse_json(json_text)
    assert len(nodes) == 1
    assert nodes[0]["name"] == "a"


def test_parse_json_wrapped_nodes(adapter):
    json_text = '{"nodes":[{"name":"a"},{"name":"b"}]}'
    nodes = adapter.parse_json(json_text)
    assert len(nodes) == 2


def test_parse_json_invalid(adapter):
    with pytest.raises(Exception):
        adapter.parse_json("not json")


# ---------------------------------------------------------------------------
# Graceful degradation tests (C4)
# ---------------------------------------------------------------------------

def test_convert_handles_exception_gracefully(adapter):
    # Passing something that causes an unexpected error inside convert
    class BadDict(dict):
        def get(self, key, default=None):
            if key == "group":
                raise RuntimeError("boom")
            return super().get(key, default)

    result = adapter.convert(BadDict(name="bad"))
    assert result is None


def test_convert_property_missing_name():
    prop = {"type": "string", "default": ""}
    assert _convert_property(prop) is None


def test_build_inputs_none():
    assert _build_inputs(None) == []
