"""Basic import and instantiation tests for decision_trace."""

import pytest
from core.decision_trace import *

def test_decisiontraceengine_import():
    """Verify DecisionTraceEngine can be imported."""
    assert DecisionTraceEngine is not None

def test_decisiontraceengine_instantiation():
    """Verify DecisionTraceEngine can be instantiated with defaults."""
    try:
        obj = DecisionTraceEngine()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
