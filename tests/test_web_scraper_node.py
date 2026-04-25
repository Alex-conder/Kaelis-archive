"""
Tests for Web Scraper workflow node (FEAT-002)
"""

import pytest
from unittest.mock import patch, MagicMock

from core.workflow_nodes.web_scraper import (
    WebScraperNode,
    scrape_webpage,
    WorkflowNodeError,
    SimpleSelectorParser,
    extract_title,
    extract_meta_description,
    extract_links,
)


class TestSimpleSelectorParser:
    """测试极简 CSS 选择器解析器"""
    
    def test_select_by_tag(self):
        html = "<html><body><h1>Title</h1><p>Paragraph 1</p><p>Paragraph 2</p></body></html>"
        parser = SimpleSelectorParser("p")
        parser.feed(html)
        assert parser.results == ["Paragraph 1", "Paragraph 2"]
    
    def test_select_by_id(self):
        html = '<html><body><div id="content">Main Content</div></body></html>'
        parser = SimpleSelectorParser("#content")
        parser.feed(html)
        assert parser.results == ["Main Content"]
    
    def test_select_by_class(self):
        html = '<html><body><div class="article">Article 1</div><div class="other">Other</div></body></html>'
        parser = SimpleSelectorParser(".article")
        parser.feed(html)
        assert parser.results == ["Article 1"]
    
    def test_no_match(self):
        html = "<html><body><p>Text</p></body></html>"
        parser = SimpleSelectorParser("h2")
        parser.feed(html)
        assert parser.results == []


class TestExtractHelpers:
    """测试辅助提取函数"""
    
    def test_extract_title(self):
        html = "<html><head><title>  My Page  </title></head></html>"
        assert extract_title(html) == "My Page"
    
    def test_extract_title_missing(self):
        assert extract_title("<html></html>") is None
    
    def test_extract_meta_description(self):
        html = '<html><head><meta name="description" content="Test desc"></head></html>'
        assert extract_meta_description(html) == "Test desc"
    
    def test_extract_links(self):
        html = '<a href="/page1">Link 1</a><a href="https://other.com">Link 2</a>'
        links = extract_links(html, "https://example.com")
        assert len(links) == 2
        assert links[0]["url"] == "https://example.com/page1"
        assert links[0]["text"] == "Link 1"


class TestWebScraperNode:
    """测试 Web Scraper 节点"""
    
    def test_validate_inputs_missing_url(self):
        node = WebScraperNode()
        errors = node.validate_inputs({})
        assert "url is required" in errors
    
    def test_validate_inputs_invalid_scheme(self):
        node = WebScraperNode()
        errors = node.validate_inputs({"url": "ftp://example.com"})
        assert "url must start with http:// or https://" in errors
    
    def test_validate_inputs_valid(self):
        node = WebScraperNode()
        errors = node.validate_inputs({"url": "https://example.com"})
        assert errors == []
    
    def test_execute_missing_url_raises(self):
        node = WebScraperNode()
        with pytest.raises(WorkflowNodeError, match="Missing required input"):
            node.execute({})
    
    def test_execute_invalid_url_raises(self):
        node = WebScraperNode()
        with pytest.raises(WorkflowNodeError, match="Invalid URL"):
            node.execute({"url": "not-a-url"})
    
    @patch("core.workflow_nodes.web_scraper.requests.get")
    def test_execute_basic_scrape(self, mock_get):
        """测试基本抓取（无选择器）"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><head><title>Test</title></head><body><p>Hello World</p></body></html>"
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response
        
        node = WebScraperNode()
        result = node.execute({"url": "https://example.com"}, {})
        
        assert result["status_code"] == 200
        assert result["title"] == "Test"
        assert "Hello World" in result["content"]
        assert result["extracted_count"] == 1
        mock_get.assert_called_once()
    
    @patch("core.workflow_nodes.web_scraper.requests.get")
    def test_execute_with_selector(self, mock_get):
        """测试带选择器的抓取"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><h1 class="title">My Title</h1><p>Other</p></body></html>'
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response
        
        node = WebScraperNode()
        result = node.execute(
            {"url": "https://example.com", "selector": "h1"},
            {}
        )
        
        assert result["status_code"] == 200
        assert result["content"] == "My Title"
        assert result["extracted_count"] == 1
    
    @patch("core.workflow_nodes.web_scraper.requests.get")
    def test_execute_respects_config(self, mock_get):
        """测试配置参数被正确传递"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html></html>"
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response
        
        node = WebScraperNode()
        result = node.execute(
            {"url": "https://example.com"},
            {"timeout": 10, "user_agent": "CustomBot/1.0", "follow_redirects": False}
        )
        
        assert result["status_code"] == 200
        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 10
        assert kwargs["headers"]["User-Agent"] == "CustomBot/1.0"
        assert kwargs["allow_redirects"] is False
    
    @patch("core.workflow_nodes.web_scraper.requests.get")
    def test_execute_max_length_truncation(self, mock_get):
        """测试内容截断"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = f"<html><body>{'A' * 20000}</body></html>"
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response
        
        node = WebScraperNode()
        result = node.execute(
            {"url": "https://example.com"},
            {"max_length": 100}
        )
        
        assert len(result["content"]) <= 120  # 100 + truncation marker
        assert "...[truncated]" in result["content"]
    
    @patch("core.workflow_nodes.web_scraper.requests.get")
    def test_execute_http_error(self, mock_get):
        """测试 HTTP 错误处理"""
        from requests import HTTPError
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        node = WebScraperNode()
        with pytest.raises(WorkflowNodeError):
            node.execute({"url": "https://example.com/missing"}, {})


class TestScrapeWebpageConvenience:
    """测试便捷函数"""
    
    @patch("core.workflow_nodes.web_scraper.requests.get")
    def test_scrape_webpage(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><title>Quick</title><body>Text</body></html>"
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response
        
        result = scrape_webpage("https://example.com")
        assert result["status_code"] == 200
        assert result["title"] == "Quick"


class TestAPINodeExecution:
    """测试 API 执行端点（集成测试）"""
    
    @pytest.fixture
    def client(self):
        from flask import Flask
        from api.routes.workflow_nodes import bp
        app = Flask(__name__)
        app.register_blueprint(bp)
        return app.test_client()
    
    @patch("core.workflow_nodes.web_scraper.requests.get")
    def test_execute_web_scraper_api(self, mock_get, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><title>API Test</title><body><h1>Heading</h1></body></html>"
        mock_response.url = "https://test.com"
        mock_get.return_value = mock_response
        
        resp = client.post(
            "/api/workflow/nodes/web_scraper/execute",
            json={"inputs": {"url": "https://test.com", "selector": "h1"}}
        )
        
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["content"] == "Heading"
        assert data["data"]["title"] == "API Test"
    
    def test_execute_validation_error(self, client):
        resp = client.post(
            "/api/workflow/nodes/web_scraper/execute",
            json={"inputs": {}}
        )
        
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert "Validation failed" in data["error"]
    
    def test_execute_unknown_node(self, client):
        resp = client.post(
            "/api/workflow/nodes/unknown_node/execute",
            json={"inputs": {}}
        )
        
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False
