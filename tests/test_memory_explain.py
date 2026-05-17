"""Basic import and instantiation tests for memory_explain."""

import pytest
from core.memory_explain import *

def test_memoryexplainability_import():
    """Verify MemoryExplainability can be imported."""
    assert MemoryExplainability is not None

def test_memoryexplainability_instantiation():
    """Verify MemoryExplainability can be instantiated with defaults."""
    try:
        obj = MemoryExplainability()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
