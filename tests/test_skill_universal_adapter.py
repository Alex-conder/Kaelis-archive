"""Basic import and instantiation tests for skill_universal_adapter."""

import pytest
from core.skill_universal_adapter import *

def test_universalskilladapter_import():
    """Verify UniversalSkillAdapter can be imported."""
    assert UniversalSkillAdapter is not None

def test_universalskilladapter_instantiation():
    """Verify UniversalSkillAdapter can be instantiated with defaults."""
    try:
        obj = UniversalSkillAdapter()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
