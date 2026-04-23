"""
用户隔离的文档检索器 (P12-002)

为每个用户维护独立的 FAISS 索引，确保：
- 用户 A 的查询不返回用户 B 的文档
- 每个用户的索引独立存储在 data/faiss_per_user/{user_id}/

降级策略：
- 用户索引不存在 -> 创建空索引
- FAISS 不可用 -> 回退到 TF-IDF
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 支持直接运行
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)


class UserIsolatedRetriever:
    """
    按用户隔离的文档检索器
    
    包装 LocalDocumentRetriever，为每个用户维护独立索引。
    """
    
    def __init__(self, base_dir: str = "data/faiss_per_user"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._retrievers: Dict[str, Any] = {}
    
    def _get_retriever(self, user_id: str):
        """获取或创建用户的检索器"""
        if user_id in self._retrievers:
            return self._retrievers[user_id]
        
        try:
            from core.knowledge_retriever import LocalDocumentRetriever
            user_dir = self.base_dir / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # 每个用户独立的文档目录和索引
            retriever = LocalDocumentRetriever(
                doc_dir=str(user_dir / "documents"),
                persist_dir=str(user_dir / "index")
            )
            self._retrievers[user_id] = retriever
            return retriever
        except Exception as e:
            logger.error(f"Failed to create retriever for {user_id}: {e}")
            return None
    
    def index_document(
        self,
        user_id: str,
        doc_id: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        为用户索引文档
        
        Args:
            user_id: 用户ID
            doc_id: 文档ID
            content: 文档内容
            metadata: 元数据
            
        Returns:
            bool: 是否成功
        """
        retriever = self._get_retriever(user_id)
        if not retriever:
            return False
        
        try:
            # 将文档写入用户专属目录
            user_doc_dir = self.base_dir / user_id / "documents"
            user_doc_dir.mkdir(parents=True, exist_ok=True)
            
            doc_path = user_doc_dir / f"{doc_id}.txt"
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # 触发索引重建
            retriever.index_documents(force_reindex=True)
            logger.info(f"Document indexed for {user_id}: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Index failed for {user_id}: {e}")
            return False
    
    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        在用户隔离范围内搜索
        
        Args:
            user_id: 用户ID
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            List[Dict]: 搜索结果（仅该用户的文档）
        """
        retriever = self._get_retriever(user_id)
        if not retriever:
            return []
        
        try:
            results = retriever.search(query, top_k=top_k)
            # 标记结果来源
            for r in results:
                r["user_id"] = user_id
            return results
        except Exception as e:
            logger.error(f"Search failed for {user_id}: {e}")
            return []
    
    def delete_user_index(self, user_id: str) -> bool:
        """删除用户的全部索引数据"""
        user_dir = self.base_dir / user_id
        if not user_dir.exists():
            return True
        
        try:
            import shutil
            shutil.rmtree(str(user_dir))
            if user_id in self._retrievers:
                del self._retrievers[user_id]
            logger.info(f"User index deleted: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Delete failed for {user_id}: {e}")
            return False
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户的索引统计"""
        user_dir = self.base_dir / user_id
        if not user_dir.exists():
            return {"user_id": user_id, "documents": 0, "indexed": False}
        
        doc_dir = user_dir / "documents"
        doc_count = len(list(doc_dir.glob("*.txt"))) if doc_dir.exists() else 0
        
        return {
            "user_id": user_id,
            "documents": doc_count,
            "indexed": doc_count > 0,
            "index_dir": str(user_dir / "index")
        }


# 全局实例
_isolated_retriever_instance: Optional[UserIsolatedRetriever] = None


def get_user_isolated_retriever() -> UserIsolatedRetriever:
    """获取全局用户隔离检索器"""
    global _isolated_retriever_instance
    if _isolated_retriever_instance is None:
        _isolated_retriever_instance = UserIsolatedRetriever()
    return _isolated_retriever_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试用户隔离检索器 ===")
    retriever = UserIsolatedRetriever()
    
    # 为用户 A 索引文档
    retriever.index_document("user_A", "doc1", "PLS-DA is a statistical method for metabolomics.")
    retriever.index_document("user_A", "doc2", "Random Forest for classification tasks.")
    
    # 为用户 B 索引文档
    retriever.index_document("user_B", "doc3", "Neural networks for deep learning.")
    
    # 搜索测试
    results_a = retriever.search("user_A", "PLS-DA", top_k=3)
    results_b = retriever.search("user_B", "neural", top_k=3)
    
    print(f"User A results: {len(results_a)}")
    print(f"User B results: {len(results_b)}")
    
    # 统计
    print(f"Stats A: {retriever.get_user_stats('user_A')}")
    print(f"Stats B: {retriever.get_user_stats('user_B')}")
    
    print("\n[OK] UserIsolatedRetriever test completed")
