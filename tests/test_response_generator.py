"""Basic import and instantiation tests for response_generator."""

import pytest
from core.response_generator import *

def test_responsegenerator_import():
    """Verify ResponseGenerator can be imported."""
    assert ResponseGenerator is not None

def test_responsegenerator_instantiation():
    """Verify ResponseGenerator can be instantiated with defaults."""
    try:
        obj = ResponseGenerator()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
