"""
Web Scraper 工作流节点

抓取指定 URL 的网页内容，支持 CSS 选择器提取和元数据解析。
"""

import logging
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from core.workflow_nodes import NodeExecutor, WorkflowNodeError

logger = logging.getLogger(__name__)

# Optional: use requests if available, otherwise fallback to urllib
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class SimpleSelectorParser(HTMLParser):
    """极简 CSS 选择器解析器（无需 BeautifulSoup）"""
    
    def __init__(self, selector: str):
        super().__init__()
        self.selector = selector.strip()
        self.results: List[str] = []
        self._current_text = ""
        self._in_target = False
        self._target_depth = 0
        self._depth = 0
        
        # Parse selector: tag, #id, .class
        self.tag = None
        self.elem_id = None
        self.classes = []
        
        parts = self.selector.split()
        last = parts[-1] if parts else self.selector
        
        if last.startswith('#'):
            self.elem_id = last[1:]
        elif last.startswith('.'):
            self.classes = [last[1:]]
        elif last:
            self.tag = last.lower()
    
    def handle_starttag(self, tag: str, attrs: List[tuple]):
        self._depth += 1
        attr_dict = dict(attrs)
        
        matches = True
        if self.tag and tag != self.tag:
            matches = False
        if self.elem_id and attr_dict.get('id') != self.elem_id:
            matches = False
        if self.classes:
            class_attr = attr_dict.get('class', '')
            class_list = class_attr.split() if class_attr else []
            if not all(c in class_list for c in self.classes):
                matches = False
        
        if matches and not self._in_target:
            self._in_target = True
            self._target_depth = self._depth
            self._current_text = ""
    
    def handle_endtag(self, tag: str):
        if self._in_target and self._depth == self._target_depth:
            text = self._current_text.strip()
            if text:
                self.results.append(text)
            self._in_target = False
            self._current_text = ""
        self._depth -= 1
    
    def handle_data(self, data: str):
        if self._in_target:
            self._current_text += data


def _fetch_with_requests(url: str, timeout: int, headers: dict, allow_redirects: bool) -> tuple:
    """使用 requests 获取页面"""
    response = requests.get(
        url,
        timeout=timeout,
        headers=headers,
        allow_redirects=allow_redirects
    )
    response.raise_for_status()
    return response.status_code, response.text, response.url


def _fetch_with_urllib(url: str, timeout: int, headers: dict) -> tuple:
    """使用 urllib 获取页面（降级）"""
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or 'utf-8'
            text = resp.read().decode(charset, errors='replace')
            return resp.getcode(), text, resp.geturl()
    except HTTPError as e:
        raise WorkflowNodeError(f"HTTP {e.code}: {e.reason}")
    except URLError as e:
        raise WorkflowNodeError(f"URL Error: {e.reason}")


def extract_title(html: str) -> Optional[str]:
    """从 HTML 中提取 <title>"""
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r'\s+', ' ', match.group(1)).strip()
    return None


def extract_meta_description(html: str) -> Optional[str]:
    """提取 meta description"""
    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    # Try reverse order
    match = re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
        html,
        re.IGNORECASE
    )
    if match:
        return match.group(1).strip()
    return None


def extract_links(html: str, base_url: str) -> List[Dict[str, str]]:
    """提取页面中的所有链接"""
    links = []
    seen = set()
    for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
        href = match.group(1).strip()
        text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        full_url = urljoin(base_url, href)
        # Deduplicate
        if full_url not in seen:
            seen.add(full_url)
            links.append({"url": full_url, "text": text[:200]})
    return links[:50]  # Limit to 50 links


class WebScraperNode(NodeExecutor):
    """
    Web Scraper 节点
    
    输入:
        - url: 目标网页 URL (required)
        - selector: CSS 选择器，用于提取特定内容 (optional)
    
    输出:
        - content: 提取的文本内容
        - title: 页面标题
        - status_code: HTTP 状态码
        - final_url: 最终 URL（考虑重定向后）
        - meta_description: 页面描述
        - links: 页面中的前 50 个链接
        - extracted_count: 选择器匹配的元素数量
    
    配置:
        - timeout: 请求超时（秒），默认 30
        - user_agent: User-Agent 字符串
        - follow_redirects: 是否跟随重定向，默认 True
        - max_length: 返回内容的最大长度，默认 10000
    """
    
    node_id = "web_scraper"
    name = "网页抓取"
    description = "抓取指定 URL 的网页内容，支持 CSS 选择器提取"
    
    def execute(self, inputs: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
        config = config or {}
        
        url = inputs.get("url", "").strip()
        selector = inputs.get("selector", "").strip()
        
        if not url:
            raise WorkflowNodeError("Missing required input: url")
        
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise WorkflowNodeError(f"Invalid URL: {url}")
        
        # Config with defaults
        timeout = config.get("timeout", 30)
        user_agent = config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        follow_redirects = config.get("follow_redirects", True)
        max_length = config.get("max_length", 10000)
        
        headers = {"User-Agent": user_agent}
        
        # Fetch page
        logger.info(f"Scraping: {url} (selector={selector or 'none'})")
        
        try:
            if REQUESTS_AVAILABLE:
                status_code, html, final_url = _fetch_with_requests(
                    url, timeout, headers, follow_redirects
                )
            else:
                status_code, html, final_url = _fetch_with_urllib(
                    url, timeout, headers
                )
        except WorkflowNodeError:
            raise
        except Exception as e:
            raise WorkflowNodeError(f"Failed to fetch {url}: {e}")
        
        # Extract content
        if selector:
            parser = SimpleSelectorParser(selector)
            parser.feed(html)
            extracted = parser.results
            content = "\n\n".join(extracted)
            extracted_count = len(extracted)
        else:
            # Strip tags for full text
            content = re.sub(r'<[^>]+>', ' ', html)
            content = re.sub(r'\s+', ' ', content).strip()
            extracted_count = 1
        
        # Truncate if needed
        if len(content) > max_length:
            content = content[:max_length] + "\n...[truncated]"
        
        result = {
            "content": content,
            "title": extract_title(html),
            "status_code": status_code,
            "final_url": final_url,
            "meta_description": extract_meta_description(html),
            "links": extract_links(html, final_url),
            "extracted_count": extracted_count,
        }
        
        logger.info(f"Scraped {url} -> {status_code}, extracted {extracted_count} elements")
        return result
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> List[str]:
        errors = []
        url = inputs.get("url", "").strip()
        if not url:
            errors.append("url is required")
        elif not url.startswith(("http://", "https://")):
            errors.append("url must start with http:// or https://")
        return errors


# Convenience function for direct use
def scrape_webpage(
    url: str,
    selector: str = "",
    timeout: int = 30,
    user_agent: str = None,
    follow_redirects: bool = True,
    max_length: int = 10000,
) -> Dict[str, Any]:
    """
    便捷函数：直接抓取网页
    
    Example:
        >>> result = scrape_webpage("https://example.com", selector="h1")
        >>> print(result["content"])
    """
    node = WebScraperNode()
    return node.execute(
        inputs={"url": url, "selector": selector},
        config={
            "timeout": timeout,
            "user_agent": user_agent,
            "follow_redirects": follow_redirects,
            "max_length": max_length,
        }
    )
