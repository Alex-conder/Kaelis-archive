"""Basic import and instantiation tests for eco_bridge."""

import pytest
from core.eco_bridge import *

def test_eco_bridge_module_import():
    """Verify core.eco_bridge module imports successfully."""
    import core.eco_bridge
    assert core.eco_bridge is not None
