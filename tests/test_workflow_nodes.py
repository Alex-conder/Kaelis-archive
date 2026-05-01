"""
Workflow nodes tests
"""
import pytest


class TestWebScraperNode:
    @pytest.fixture
    def node(self):
        from core.workflow_nodes.web_scraper import WebScraperNode
        return WebScraperNode()

    def test_validate_inputs_url(self, node):
        errors = node.validate_inputs({"url": "https://example.com"})
        assert len(errors) == 0

    def test_validate_inputs_missing_url(self, node):
        errors = node.validate_inputs({})
        assert len(errors) > 0

    def test_execute_mock(self, node):
        result = node.execute(
            {"url": "https://example.com", "selector": "h1"},
            config={}
        )
        assert result is not None
        assert isinstance(result, dict)


class TestSimpleSelectorParser:
    def test_parse_simple_html(self):
        from core.workflow_nodes.web_scraper import SimpleSelectorParser
        parser = SimpleSelectorParser("h1")
        parser.feed("<html><body><h1>Title</h1></body></html>")
        assert "Title" in parser.results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
