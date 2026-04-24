"""
KnowledgeRetriever 优雅降级测试 (C4)

覆盖所有可选依赖不可用的回退路径。
命名规范: test_<功能>_when_<依赖>_unavailable
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import KaelisTestBase


class TestKnowledgeRetrieverWhenRequestsUnavailable(KaelisTestBase):
    """requests 不可用时降级"""

    def test_search_arxiv_when_requests_unavailable(self):
        """requests 不可用时 arxiv 搜索返回空列表"""
        import core.knowledge_retriever as kr
        with patch.object(kr, 'REQUESTS_AVAILABLE', False):
            kr_inst = kr.KnowledgeRetriever(
                local_doc_dir=os.path.join(self.temp_dir, "documents"),
                cache_dir=os.path.join(self.temp_dir, "cache")
            )
            results = kr_inst._search_arxiv("test", max_results=1)
            self.assertEqual(results, [])


class TestKnowledgeRetrieverWhenDuckduckgoUnavailable(KaelisTestBase):
    """duckduckgo_search 不可用时降级"""

    def test_web_search_when_duckduckgo_unavailable(self):
        """DDGS 不可用时网页搜索返回空字符串"""
        import core.knowledge_retriever as kr
        with patch.object(kr, 'DDGS_AVAILABLE', False):
            retriever = kr.WebSearchRetriever()
            result = retriever.search("test", max_results=1)
            self.assertEqual(result, "")


class TestKnowledgeRetrieverWhenChromadbUnavailable(KaelisTestBase):
    """chromadb 不可用时降级"""

    def test_local_retriever_index_when_chromadb_unavailable(self):
        """chromadb 不可用时 LocalDocumentRetriever 仍可用 TF-IDF"""
        import core.knowledge_retriever as kr
        with patch.object(kr, 'CHROMADB_AVAILABLE', False):
            doc_dir = os.path.join(self.temp_dir, "docs")
            os.makedirs(doc_dir, exist_ok=True)
            with open(os.path.join(doc_dir, "test.txt"), "w", encoding="utf-8") as f:
                f.write("machine learning test document")

            retriever = kr.LocalDocumentRetriever(
                doc_dir=doc_dir,
                collection_name="test",
                persist_dir=os.path.join(self.temp_dir, "chroma")
            )
            # TF-IDF 不依赖 chromadb，应正常工作
            embeddings = retriever._create_tfidf_embeddings()
            vec = embeddings.embed_query("test")
            self.assertIsInstance(vec, list)


class TestKnowledgeRetrieverWhenDiskcacheUnavailable(KaelisTestBase):
    """diskcache 不可用时降级"""

    def test_cache_when_diskcache_unavailable(self):
        """diskcache 不可用时 CacheWrapper 返回 None"""
        import core.knowledge_retriever as kr
        with patch.object(kr, 'DISKCACHE_AVAILABLE', False):
            cache = kr.DiskCacheWrapper(
                cache_dir=os.path.join(self.temp_dir, "cache")
            )
            self.assertIsNone(cache._cache)
            cache.set("key", "value")
            result = cache.get("key")
            self.assertIsNone(result)


class TestKnowledgeRetrieverWhenWatchdogUnavailable(KaelisTestBase):
    """watchdog 不可用时降级"""

    def test_watcher_when_watchdog_unavailable(self):
        """watchdog 不可用时文件监听器不启动"""
        import core.knowledge_retriever as kr
        with patch.object(kr, 'WATCHDOG_AVAILABLE', False):
            kr_inst = kr.KnowledgeRetriever(
                local_doc_dir=os.path.join(self.temp_dir, "documents"),
                cache_dir=os.path.join(self.temp_dir, "cache")
            )
            # 不应抛异常，observer 应为 None
            kr_inst.stop_watcher()


class TestKnowledgeRetrieverWhenLangchainUnavailable(KaelisTestBase):
    """langchain 不可用时降级"""

    def test_embeddings_when_langchain_unavailable(self):
        """langchain 不可用时 LocalDocumentRetriever 回退到 TF-IDF"""
        import core.knowledge_retriever as kr
        with patch.object(kr, 'LANGCHAIN_AVAILABLE', False):
            doc_dir = os.path.join(self.temp_dir, "docs")
            os.makedirs(doc_dir, exist_ok=True)
            retriever = kr.LocalDocumentRetriever(
                doc_dir=doc_dir,
                collection_name="test",
                persist_dir=os.path.join(self.temp_dir, "chroma")
            )
            # _create_tfidf_embeddings 内部定义 TfidfEmbeddings，不依赖 langchain
            embeddings = retriever._create_tfidf_embeddings()
            vec = embeddings.embed_query("test")
            self.assertIsInstance(vec, list)


if __name__ == "__main__":
    unittest.main()
