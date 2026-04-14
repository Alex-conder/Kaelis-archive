"""
知识检索器 - 增强版

功能：
1. arXiv 论文检索（原有功能）
2. 本地文档检索（PDF/TXT/MD）
3. 网页搜索（DuckDuckGo）
4. 缓存机制
"""

import os
import json
import logging
import hashlib
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 尝试导入可选依赖
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from langchain.document_loaders import DirectoryLoader, TextLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

try:
    from diskcache import Cache
    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class DiskCacheWrapper:
    """磁盘缓存包装器"""
    
    def __init__(self, cache_dir: str = "data/cache/knowledge", max_size: int = 100):
        self.cache_dir = cache_dir
        self.max_size = max_size
        self._cache = None
        
        if DISKCACHE_AVAILABLE:
            try:
                os.makedirs(cache_dir, exist_ok=True)
                self._cache = Cache(cache_dir, size_limit=100*1024*1024)
            except Exception as e:
                logger.warning(f"初始化磁盘缓存失败: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        if self._cache is None:
            return None
        try:
            value = self._cache.get(key)
            if value is not None:
                timestamp = value.get("_timestamp") if isinstance(value, dict) else None
                if timestamp:
                    cached_time = datetime.fromisoformat(timestamp)
                    if datetime.now() - cached_time > timedelta(hours=24):
                        self._cache.delete(key)
                        return None
                return value.get("data") if isinstance(value, dict) else value
        except Exception as e:
            logger.debug(f"缓存读取失败: {e}")
        return None
    
    def set(self, key: str, value: Any):
        if self._cache is None:
            return
        try:
            wrapped = {
                "data": value,
                "_timestamp": datetime.now().isoformat()
            }
            self._cache.set(key, wrapped)
        except Exception as e:
            logger.debug(f"缓存写入失败: {e}")


class LocalDocumentRetriever:
    """本地文档检索器"""
    
    def __init__(
        self, 
        doc_dir: str = "data/documents",
        collection_name: str = "local_docs",
        persist_dir: str = "data/chroma_db"
    ):
        self.doc_dir = doc_dir
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self.chroma_client = None
        self.collection = None
        self._init_chromadb()
    
    def _init_chromadb(self):
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available")
            return
        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            self.chroma_client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_dir
            ))
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
    
    def index_documents(self, force_reindex: bool = False) -> int:
        if not self.collection or not LANGCHAIN_AVAILABLE:
            return 0
        if not os.path.exists(self.doc_dir):
            return 0
        try:
            if not force_reindex and self.collection.count() > 0:
                return self.collection.count()
            
            from langchain.document_loaders import TextLoader
            documents = []
            for root, _, files in os.walk(self.doc_dir):
                for file in files:
                    if file.endswith(('.txt', '.md')):
                        try:
                            path = os.path.join(root, file)
                            loader = TextLoader(path, encoding='utf-8')
                            documents.extend(loader.load())
                        except Exception as e:
                            logger.debug(f"Load {file} failed: {e}")
            
            if not documents:
                return 0
            
            # Fixer C1: 针对中文文档优化切片参数，减少语义断层
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=800, chunk_overlap=200
            )
            chunks = text_splitter.split_documents(documents)
            
            texts = [c.page_content for c in chunks]
            ids = [f"doc_{i}" for i in range(len(texts))]
            metadatas = [{"source": c.metadata.get("source", "")} for c in chunks]
            
            for i in range(0, len(texts), 100):
                end = min(i + 100, len(texts))
                self.collection.add(
                    ids=ids[i:end],
                    documents=texts[i:end],
                    metadatas=metadatas[i:end]
                )
            
            logger.info(f"Indexed {len(texts)} document chunks")
            return len(texts)
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            return 0
    
    def search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        if not self.collection:
            return []
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            output = []
            for i in range(len(results['ids'][0])):
                output.append({
                    "content": results['documents'][0][i],
                    "source": results['metadatas'][0][i].get('source', ''),
                    "distance": results['distances'][0][i] if results.get('distances') else None
                })
            return output
        except Exception as e:
            logger.error(f"Local search failed: {e}")
            return []


class WebSearchRetriever:
    """网页搜索检索器"""
    
    def __init__(self):
        self.ddgs = None
        if DDGS_AVAILABLE:
            try:
                self.ddgs = DDGS()
            except Exception as e:
                logger.warning(f"DDGS init failed: {e}")
    
    def search(self, query: str, max_results: int = 2) -> str:
        if not self.ddgs:
            return ""
        try:
            results = self.ddgs.text(query, max_results=max_results)
            if not results:
                return ""
            
            summaries = []
            for r in results:
                title = r.get('title', '')
                body = r.get('body', '')
                href = r.get('href', '')
                summaries.append(f"[{title}]\n{body}\n来源: {href}\n")
            
            return "\n---\n".join(summaries)
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return ""


class _CacheInvalidationHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """
    Fixer C2: 文件监听驱动的缓存失效
    当知识库目录中的文件发生变更时，清空缓存并触发重新索引
    """
    def __init__(self, retriever: "KnowledgeRetriever"):
        self.retriever = retriever
        self._debounce_timer = None

    def on_any_event(self, event):
        if event.is_directory:
            return
        # 只关心文本和 markdown 文件
        if not event.src_path.endswith(('.txt', '.md')):
            return
        logger.info(f"Document change detected: {event.src_path} ({event.event_type})")
        # 简单防抖：500ms 内多次变更只处理一次
        if self._debounce_timer is not None:
            try:
                self._debounce_timer.cancel()
            except Exception:
                pass
        import threading
        self._debounce_timer = threading.Timer(0.5, self._invalidate)
        self._debounce_timer.start()

    def _invalidate(self):
        try:
            if self.retriever.cache and self.retriever.cache._cache:
                self.retriever.cache._cache.clear()
                logger.info("Knowledge cache cleared due to document changes")
            # 触发重新索引
            self.retriever.index_local_documents(force_reindex=True)
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")


class KnowledgeRetriever:
    """统一知识检索器"""
    
    def __init__(
        self,
        local_doc_dir: str = "data/documents",
        enable_web_search: bool = False,
        cache_dir: str = "data/cache/knowledge"
    ):
        self.enable_web_search = enable_web_search and DDGS_AVAILABLE
        self.local_retriever = LocalDocumentRetriever(local_doc_dir)
        self.web_retriever = WebSearchRetriever() if self.enable_web_search else None
        self.cache = DiskCacheWrapper(cache_dir)
        self._observer = None
        
        # Fixer C2: 启动文件监听器自动失效缓存
        if WATCHDOG_AVAILABLE and os.path.isdir(local_doc_dir):
            try:
                self._observer = Observer()
                handler = _CacheInvalidationHandler(self)
                self._observer.schedule(handler, local_doc_dir, recursive=True)
                self._observer.start()
                logger.info(f"File watcher started for {local_doc_dir}")
            except Exception as e:
                logger.warning(f"Failed to start file watcher: {e}")
        
        logger.info(f"KnowledgeRetriever initialized (web_search={self.enable_web_search})")
    
    def stop_watcher(self):
        """停止文件监听器（用于优雅关闭）"""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join()
                logger.info("File watcher stopped")
            except Exception as e:
                logger.warning(f"Error stopping file watcher: {e}")
    
    def search(
        self,
        query: str,
        sources: List[str] = None,
        top_k: int = 2,
        allow_web: bool = None
    ) -> Dict[str, Any]:
        """
        统一搜索接口
        
        Args:
            query: 搜索查询
            sources: 搜索源 ["arxiv", "local", "web"]
            top_k: 返回结果数量
            allow_web: 是否允许网页搜索
            
        Returns:
            Dict: 各来源的搜索结果
        """
        sources = sources or ["local", "arxiv"]
        allow_web = allow_web if allow_web is not None else self.enable_web_search
        
        cache_key = hashlib.md5(f"{query}:{','.join(sources)}:{top_k}".encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for query: {query[:30]}...")
            return cached
        
        results = {"query": query, "sources": {}}
        
        # 本地文档检索
        if "local" in sources:
            local_results = self.local_retriever.search(query, top_k)
            if local_results:
                results["sources"]["local"] = local_results
        
        # arXiv 检索
        if "arxiv" in sources:
            arxiv_results = self._search_arxiv(query, top_k)
            if arxiv_results:
                results["sources"]["arxiv"] = arxiv_results
        
        # 网页搜索
        if "web" in sources and allow_web and self.web_retriever:
            web_results = self.web_retriever.search(query, max_results=top_k)
            if web_results:
                results["sources"]["web"] = web_results
        
        # 缓存结果
        self.cache.set(cache_key, results)
        
        return results
    
    def _search_arxiv(self, query: str, max_results: int = 2) -> List[Dict]:
        """搜索 arXiv"""
        if not REQUESTS_AVAILABLE:
            return []
        
        try:
            url = "http://export.arxiv.org/api/query"
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending"
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return []
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('atom:entry', ns)
            
            results = []
            for entry in entries:
                title = entry.find('atom:title', ns)
                summary = entry.find('atom:summary', ns)
                link = entry.find('atom:id', ns)
                
                results.append({
                    "title": title.text if title is not None else "",
                    "summary": summary.text[:500] + "..." if summary and len(summary.text) > 500 else (summary.text if summary else ""),
                    "link": link.text if link is not None else ""
                })
            
            return results
            
        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []
    
    def index_local_documents(self, force_reindex: bool = False) -> int:
        """索引本地文档"""
        return self.local_retriever.index_documents(force_reindex)
    
    def get_search_summary(self, results: Dict[str, Any]) -> str:
        """获取搜索结果的文本摘要"""
        parts = []
        
        if "local" in results.get("sources", {}):
            parts.append("=== 本地文档 ===")
            for doc in results["sources"]["local"]:
                parts.append(f"[{doc.get('source', '')}]\n{doc.get('content', '')[:300]}...")
        
        if "arxiv" in results.get("sources", {}):
            parts.append("\n=== arXiv 论文 ===")
            for paper in results["sources"]["arxiv"]:
                parts.append(f"[{paper.get('title', '')}]\n{paper.get('summary', '')}")
        
        if "web" in results.get("sources", {}):
            parts.append("\n=== 网页搜索结果 ===")
            parts.append(results["sources"]["web"])
        
        return "\n\n".join(parts)


if __name__ == "__main__":
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试知识检索器 ===")
    retriever = KnowledgeRetriever(enable_web_search=False)
    
    # 测试 arXiv 搜索
    print("\n搜索 arXiv...")
    results = retriever.search("PLS-DA metabolomics", sources=["arxiv"], top_k=2)
    print(retriever.get_search_summary(results)[:500])
