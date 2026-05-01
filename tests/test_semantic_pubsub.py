"""
Semantic pub/sub tests
"""
import pytest
import tempfile
import shutil
import time


class TestSemanticPubSubEngine:
    @pytest.fixture
    def engine(self):
        import core.semantic_pubsub as ps_module
        ps_module._engine_instance = None
        from core.semantic_pubsub import SemanticPubSubEngine
        tmpdir = tempfile.mkdtemp()
        yield SemanticPubSubEngine(db_dir=tmpdir)
        ps_module._engine_instance = None
        time.sleep(0.1)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_subscribe(self, engine):
        sub_id = engine.subscribe(
            space_id="space1",
            tags=["news"],
            query_pattern="tech",
            similarity_threshold=0.8,
            callback=lambda x: x
        )
        assert isinstance(sub_id, str)
        fetched = engine.get_subscription(sub_id)
        assert fetched is not None
        assert fetched["space_id"] == "space1"

    def test_unsubscribe(self, engine):
        sub_id = engine.subscribe(
            space_id="s1",
            tags=["t"],
            query_pattern="*",
            similarity_threshold=0.5,
            callback=lambda x: x
        )
        ok = engine.unsubscribe(sub_id)
        assert ok is True
        fetched = engine.get_subscription(sub_id)
        assert fetched is None

    def test_list_subscriptions(self, engine):
        engine.subscribe(
            space_id="a", tags=["a"], query_pattern="*",
            similarity_threshold=0.5, callback=lambda x: x
        )
        engine.subscribe(
            space_id="b", tags=["b"], query_pattern="*",
            similarity_threshold=0.5, callback=lambda x: x
        )
        subs = engine.list_subscriptions()
        assert len(subs) == 2

    def test_publish_no_subscribers(self, engine):
        deliveries = engine.publish(
            space_id="empty", key="k1", value="hello",
            tags=[], metadata={}
        )
        assert isinstance(deliveries, (list, int))

    def test_publish_with_subscriber(self, engine):
        received = []
        engine.subscribe(
            space_id="events", tags=["evt"], query_pattern="*",
            similarity_threshold=0.1, callback=lambda p: received.append(p)
        )
        deliveries = engine.publish(
            space_id="events", key="k1", value="hi",
            tags=["evt"], metadata={}
        )
        assert isinstance(deliveries, (list, int))

    def test_get_delivery_history(self, engine):
        history = engine.get_delivery_history()
        assert isinstance(history, list)


class TestSubscription:
    def test_matches_exact(self):
        from core.semantic_pubsub import Subscription
        sub = Subscription(
            sub_id="s1", space_id="space1", tags=["news"],
            query_pattern="tech", similarity_threshold=0.8,
            created_at="2024-01-01"
        )
        assert sub.matches("tech", "value") is True
        assert sub.matches("sports", "value") is False

    def test_matches_wildcard(self):
        from core.semantic_pubsub import Subscription
        sub = Subscription(
            sub_id="s1", space_id="space1", tags=["news"],
            query_pattern="news", similarity_threshold=0.8,
            created_at="2024-01-01"
        )
        assert sub.matches("news.tech", "value") is True
        assert sub.matches("news sports", "value") is True
        assert sub.matches("weather", "value") is False

    def test_to_dict(self):
        from core.semantic_pubsub import Subscription
        sub = Subscription(
            sub_id="s1", space_id="space1", tags=["t"],
            query_pattern="*", similarity_threshold=0.5,
            created_at="2024-01-01"
        )
        d = sub.to_dict()
        assert d["sub_id"] == "s1"
        assert d["space_id"] == "space1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
