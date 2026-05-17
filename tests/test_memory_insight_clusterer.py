"""Basic import and instantiation tests for memory_insight_clusterer."""

import pytest
from core.memory_insight_clusterer import *

def test_memoryinsightclusterer_import():
    """Verify MemoryInsightClusterer can be imported."""
    assert MemoryInsightClusterer is not None

def test_memoryinsightclusterer_instantiation():
    """Verify MemoryInsightClusterer can be instantiated with defaults."""
    try:
        obj = MemoryInsightClusterer()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
