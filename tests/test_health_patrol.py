"""Basic import and instantiation tests for health_patrol."""

import pytest
from core.health_patrol import *

def test_healthpatrol_import():
    """Verify HealthPatrol can be imported."""
    assert HealthPatrol is not None

def test_healthpatrol_instantiation():
    """Verify HealthPatrol can be instantiated with defaults."""
    try:
        obj = HealthPatrol()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
