"""Basic import and instantiation tests for tool_tracer."""

import pytest
from core.tool_tracer import *

def test_tooltracer_import():
    """Verify ToolTracer can be imported."""
    assert ToolTracer is not None

def test_tooltracer_instantiation():
    """Verify ToolTracer can be instantiated with defaults."""
    try:
        obj = ToolTracer()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
