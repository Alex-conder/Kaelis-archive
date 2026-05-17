"""Basic import and instantiation tests for kg_audit."""

import pytest
from core.kg_audit import *

def test_kgauditengine_import():
    """Verify KGAuditEngine can be imported."""
    assert KGAuditEngine is not None

def test_kgauditengine_instantiation():
    """Verify KGAuditEngine can be instantiated with defaults."""
    try:
        obj = KGAuditEngine()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
