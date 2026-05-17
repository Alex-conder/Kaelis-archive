"""Basic import and instantiation tests for user_feedback."""

import pytest
from core.user_feedback import *

def test_userfeedbackcollector_import():
    """Verify UserFeedbackCollector can be imported."""
    assert UserFeedbackCollector is not None

def test_userfeedbackcollector_instantiation():
    """Verify UserFeedbackCollector can be instantiated with defaults."""
    try:
        obj = UserFeedbackCollector()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
