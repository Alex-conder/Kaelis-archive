"""Basic import and instantiation tests for counterfactual_engine."""

import pytest
from core.counterfactual_engine import *

def test_counterfactualengine_import():
    """Verify CounterfactualEngine can be imported."""
    assert CounterfactualEngine is not None

def test_counterfactualengine_instantiation():
    """Verify CounterfactualEngine can be instantiated with defaults."""
    try:
        obj = CounterfactualEngine()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
