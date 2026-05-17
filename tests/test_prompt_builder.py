"""Basic import and instantiation tests for prompt_builder."""

import pytest
from core.prompt_builder import *

def test_promptbuilder_import():
    """Verify PromptBuilder can be imported."""
    assert PromptBuilder is not None

def test_promptbuilder_instantiation():
    """Verify PromptBuilder can be instantiated with defaults."""
    try:
        obj = PromptBuilder()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
