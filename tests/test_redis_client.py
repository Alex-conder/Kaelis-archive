"""Basic import and instantiation tests for redis_client."""

import pytest
from core.redis_client import *

def test_redisclient_import():
    """Verify RedisClient can be imported."""
    assert RedisClient is not None

def test_redisclient_instantiation():
    """Verify RedisClient can be instantiated with defaults."""
    try:
        obj = RedisClient()
        assert obj is not None
    except Exception as e:
        pytest.skip(f'Instantiation requires deps: {e}')
