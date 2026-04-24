"""
KnowledgeRetriever 单元测试
"""

import os
import tempfile
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestDiskCacheWrapper(KaelisTestBase):
    """测试磁盘缓存包装器"""
    
    def setUp(self):
        super().setUp()
        from core.knowledge_retriever import DiskCacheWrapper
        self.cache_dir = os.path.join(self.temp_dir, "test_cache")
        self.cache = DiskCacheWrapper(cache_dir=self.cache_dir)
    
    def test_get_empty(self):
        """空缓存读取"""
        result = self.cache.get("nonexistent_key")
        self.assertIsNone(result)
    
    def test_set_and_get(self):
        """写入和读取"""
        self.cache.set("key1", "value1")
        result = self.cache.get("key1")
        self.assertEqual(result, "value1")
    
    def test_get_expired(self):
        """过期缓存"""
        from datetime import datetime, timedelta
        
        if self.cache._cache:
            expired_value = {
                "data": "old",
                "_timestamp": (datetime.now() - timedelta(hours=25)).isoformat()
            }
            self.cache._cache.set("expired_key", expired_value)
            result = self.cache.get("expired_key")
            self.assertIsNone(result)
    
    def test_set_without_cache(self):
        """无缓存时的写入"""
        self.cache._cache = None
        self.cache.set("key", "value")
        result = self.cache.get("key")
        self.assertIsNone(result)


class TestLocalDocumentRetriever(KaelisTestBase):
    """测试本地文档检索器"""
    
    def setUp(self):
        super().setUp()
        from core.knowledge_retriever import LocalDocumentRetriever
        self.doc_dir = os.path.join(self.temp_dir, "docs")
        os.makedirs(self.doc_dir, exist_ok=True)
        self.retriever = LocalDocumentRetriever(
            doc_dir=self.doc_dir,
            collection_name="test_collection",
            persist_dir=os.path.join(self.temp_dir, "chroma")
        )
    
    def test_init(self):
        """初始化"""
        self.assertEqual(self.retriever.doc_dir, self.doc_dir)
    
    def test_index_empty_dir(self):
        """空目录索引"""
        from core.knowledge_retriever import LocalDocumentRetriever
        # 使用一个全新的空目录避免状态污染
        empty_dir = os.path.join(self.temp_dir, "empty_docs")
        os.makedirs(empty_dir, exist_ok=True)
        retriever = LocalDocumentRetriever(
            doc_dir=empty_dir,
            collection_name="empty_test",
            persist_dir=os.path.join(self.temp_dir, "empty_chroma")
        )
        count = retriever.index_documents()
        self.assertEqual(count, 0)
    
    def test_index_documents(self):
        """索引文档"""
        with open(os.path.join(self.doc_dir, "test.txt"), "w", encoding="utf-8") as f:
            f.write("This is a test document about machine learning.")
        
        count = self.retriever.index_documents()
        self.assertIsInstance(count, int)
    
    def test_search_empty(self):
        """空检索"""
        results = self.retriever.search("machine learning", top_k=3)
        self.assertIsInstance(results, list)
    
    def test_create_tfidf_embeddings(self):
        """TF-IDF 嵌入模型"""
        embeddings = self.retriever._create_tfidf_embeddings()
        vec = embeddings.embed_query("test query")
        self.assertIsInstance(vec, list)


class TestKnowledgeRetriever(KaelisTestBase):
    """测试知识检索器主类"""
    
    def setUp(self):
        super().setUp()
        from core.knowledge_retriever import KnowledgeRetriever
        self.kr = KnowledgeRetriever(
            local_doc_dir=os.path.join(self.temp_dir, "documents"),
            cache_dir=os.path.join(self.temp_dir, "cache")
        )
    
    def test_init(self):
        """初始化"""
        self.assertIsNotNone(self.kr)
    
    def test_search_local(self):
        """本地搜索"""
        results = self.kr.search("machine learning", sources=["local"], top_k=3)
        self.assertIn("query", results)
        self.assertIn("sources", results)
    
    def test_search_arxiv(self):
        """arXiv 搜索"""
        results = self.kr.search("test query", sources=["arxiv"], top_k=2)
        self.assertIn("query", results)
    
    def test_search_all(self):
        """全来源搜索"""
        results = self.kr.search("test", sources=["local", "arxiv"], top_k=2)
        self.assertIn("query", results)
        self.assertIn("sources", results)
    
    def test_search_with_cache(self):
        """缓存命中"""
        r1 = self.kr.search("cached query", sources=["local"], top_k=2)
        r2 = self.kr.search("cached query", sources=["local"], top_k=2)
        self.assertEqual(r1["query"], r2["query"])
    
    def test_search_allow_web(self):
        """允许网页搜索"""
        results = self.kr.search("test", sources=["local"], allow_web=False)
        self.assertIn("query", results)
    
    def test_index_local_documents(self):
        """索引本地文档"""
        count = self.kr.index_local_documents()
        self.assertIsInstance(count, int)
    
    def test_get_search_summary(self):
        """搜索结果摘要"""
        results = {
            "sources": {
                "local": [{"source": "test.txt", "content": "hello world"}],
                "arxiv": [{"title": "Test Paper", "summary": "This is a test."}]
            }
        }
        summary = self.kr.get_search_summary(results)
        self.assertIsInstance(summary, str)
        self.assertIn("本地文档", summary)
    
    def test_get_search_summary_empty(self):
        """空结果摘要"""
        summary = self.kr.get_search_summary({})
        self.assertIsInstance(summary, str)
    
    def test_stop_watcher(self):
        """停止文件监听器"""
        self.kr.stop_watcher()
        # 不应抛异常
    
    def test_search_web_source_disabled(self):
        """web source 被禁用时返回空"""
        results = self.kr.search("test", sources=["web"], allow_web=False)
        self.assertNotIn("web", results.get("sources", {}))
    
    def test_get_search_summary_web(self):
        """包含网页搜索结果的摘要"""
        results = {
            "sources": {
                "web": "Web search results here"
            }
        }
        summary = self.kr.get_search_summary(results)
        self.assertIn("网页搜索", summary)
    
    def test_search_arxiv_mocked_success(self):
        """mock arxiv 搜索成功"""
        from unittest.mock import patch, MagicMock
        xml_response = b'''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Test Paper</title>
            <summary>Test summary.</summary>
            <id>http://arxiv.org/abs/1234</id>
          </entry>
        </feed>'''
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = xml_response
        with patch('core.knowledge_retriever.requests.get', return_value=mock_resp):
            results = self.kr._search_arxiv("test", max_results=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Paper")
    
    def test_search_arxiv_mocked_http_error(self):
        """mock arxiv 搜索 HTTP 错误"""
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch('core.knowledge_retriever.requests.get', return_value=mock_resp):
            results = self.kr._search_arxiv("test", max_results=1)
        self.assertEqual(results, [])
    
    def test_search_arxiv_mocked_exception(self):
        """mock arxiv 搜索异常"""
        from unittest.mock import patch
        with patch('core.knowledge_retriever.requests.get', side_effect=Exception("network error")):
            results = self.kr._search_arxiv("test", max_results=1)
        self.assertEqual(results, [])
    
    def test_index_local_documents_force(self):
        """强制重新索引"""
        count = self.kr.index_local_documents(force_reindex=True)
        self.assertIsInstance(count, int)
    
    def test_diskcache_wrapper_exception_in_get(self):
        """DiskCache get 时抛出异常"""
        from core.knowledge_retriever import DiskCacheWrapper
        cache = DiskCacheWrapper(cache_dir=os.path.join(self.temp_dir, "exc_cache"))
        if cache._cache:
            # 通过 monkeypatch 让 get 抛出异常
            original_get = cache._cache.get
            def bad_get(key):
                raise RuntimeError("boom")
            cache._cache.get = bad_get
            result = cache.get("any_key")
            self.assertIsNone(result)
            cache._cache.get = original_get


if __name__ == "__main__":
    unittest.main()
