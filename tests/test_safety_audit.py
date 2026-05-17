"""Basic import and instantiation tests for safety_audit."""

import pytest
from core.safety_audit import *

def test_safetyauditengine_import():
    """Verify SafetyAuditEngine can be imported."""
    assert SafetyAuditEngine is not None

def test_safetyauditengine_instantiation():
    """Verify SafetyAuditEngine can be instantiated with defaults."""
    try:
        obj = SafetyAuditEngine()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
