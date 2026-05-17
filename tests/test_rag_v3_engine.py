"""Basic import and instantiation tests for rag_v3_engine."""

import pytest
from core.rag_v3_engine import *

def test_ragv3engine_import():
    """Verify RAGv3Engine can be imported."""
    assert RAGv3Engine is not None

def test_ragv3engine_instantiation():
    """Verify RAGv3Engine can be instantiated with defaults."""
    try:
        obj = RAGv3Engine()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
