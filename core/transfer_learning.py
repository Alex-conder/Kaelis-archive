"""
迁移学习模块 - 跨任务参数迁移

功能：
1. 成功案例存储
2. 相似参数检索（基于向量相似度）
3. 经验复用
"""

import json
import logging
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# 尝试导入 ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


@dataclass
class SuccessCase:
    """成功案例"""
    task_type: str
    params: Dict[str, Any]
    result: Dict[str, Any]
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    case_id: str = ""
    
    def __post_init__(self):
        if not self.case_id:
            self.case_id = hashlib.md5(
                f"{self.task_type}:{json.dumps(self.params, sort_keys=True)}".encode()
            ).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "task_type": self.task_type,
            "params": self.params,
            "result": self.result,
            "confidence": self.confidence,
            "timestamp": self.timestamp
        }
    
    def to_embedding_text(self) -> str:
        """转换为用于嵌入的文本"""
        return json.dumps({
            "task_type": self.task_type,
            "params": self.params,
            "result_keys": list(self.result.keys())
        }, sort_keys=True)


class TransferLearning:
    """
    迁移学习管理器
    
    使用 ChromaDB 存储和检索成功案例。
    """
    
    def __init__(
        self,
        collection_name: str = "success_cases",
        persist_dir: str = "data/chroma_db"
    ):
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self.chroma_client = None
        self.collection = None
        self._local_cache: List[SuccessCase] = []
        
        self._init_chromadb()
    
    def _init_chromadb(self):
        """初始化 ChromaDB"""
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available, using memory-only storage")
            return
        
        try:
            import os
            os.makedirs(self.persist_dir, exist_ok=True)
            
            self.chroma_client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_dir
            ))
            
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info(f"TransferLearning initialized: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
            self.chroma_client = None
            self.collection = None
    
    def update_success_case(
        self,
        task_type: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        confidence: float
    ) -> bool:
        """
        记录成功案例
        
        Args:
            task_type: 任务类型
            params: 成功参数
            result: 任务结果
            confidence: 置信度
            
        Returns:
            bool: 是否成功记录
        """
        case = SuccessCase(
            task_type=task_type,
            params=params,
            result=result,
            confidence=confidence
        )
        
        # 添加到本地缓存
        self._local_cache.append(case)
        
        # 添加到 ChromaDB
        if self.collection:
            try:
                self.collection.add(
                    ids=[case.case_id],
                    documents=[case.to_embedding_text()],
                    metadatas=[{
                        "task_type": task_type,
                        "confidence": confidence,
                        "timestamp": case.timestamp,
                        "params_json": json.dumps(params)
                    }]
                )
                
                if hasattr(self.chroma_client, 'persist'):
                    self.chroma_client.persist()
                
                logger.info(f"Success case recorded: {case.case_id} ({task_type})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to store case: {e}")
        
        return False
    
    def get_best_similar_params(
        self,
        current_params: Dict[str, Any],
        task_type: str,
        top_k: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        检索最相似的成功参数
        
        Args:
            current_params: 当前参数
            task_type: 任务类型
            top_k: 检索数量
            
        Returns:
            Optional[Dict]: 最佳相似参数
        """
        # 构建查询文本
        query_text = json.dumps({
            "task_type": task_type,
            "params": current_params
        }, sort_keys=True)
        
        candidates = []
        
        # 从 ChromaDB 检索
        if self.collection:
            try:
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=top_k,
                    where={"task_type": task_type}
                )
                
                for i in range(len(results['ids'][0])):
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i] if results.get('distances') else 1.0
                    
                    try:
                        params = json.loads(metadata.get('params_json', '{}'))
                        confidence = metadata.get('confidence', 0.5)
                        
                        # 相似度加权置信度
                        similarity_score = confidence * (1 - distance)
                        candidates.append((params, similarity_score, confidence))
                    except json.JSONDecodeError:
                        continue
                        
            except Exception as e:
                logger.debug(f"ChromaDB query failed: {e}")
        
        # 从本地缓存检索（作为回退）
        if not candidates:
            for case in self._local_cache:
                if case.task_type == task_type:
                    candidates.append((case.params, case.confidence, case.confidence))
        
        if not candidates:
            logger.debug(f"No similar cases found for {task_type}")
            return None
        
        # 选择最佳参数
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_params, score, conf = candidates[0]
        
        logger.info(f"Found similar case: score={score:.3f}, confidence={conf:.3f}")
        return best_params
    
    def get_task_statistics(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """
        获取任务统计信息
        
        Args:
            task_type: 任务类型过滤
            
        Returns:
            Dict: 统计信息
        """
        cases = self._local_cache
        
        if task_type:
            cases = [c for c in cases if c.task_type == task_type]
        
        if not cases:
            return {"total_cases": 0}
        
        confidences = [c.confidence for c in cases]
        task_types = set(c.task_type for c in cases)
        
        return {
            "total_cases": len(cases),
            "unique_task_types": len(task_types),
            "avg_confidence": sum(confidences) / len(confidences),
            "max_confidence": max(confidences),
            "task_types": list(task_types)
        }
    
    def suggest_params_for_new_task(
        self,
        task_type: str,
        known_params: List[str]
    ) -> Dict[str, Any]:
        """
        为新任务类型建议初始参数
        
        Args:
            task_type: 任务类型
            known_params: 已知参数名列表
            
        Returns:
            Dict: 建议参数
        """
        # 检索相似任务
        similar_tasks = []
        
        for case in self._local_cache:
            # 简单启发式：任务名相似度
            similarity = self._task_similarity(task_type, case.task_type)
            if similarity > 0.5:
                similar_tasks.append((case, similarity))
        
        if not similar_tasks:
            # 使用默认参数
            return self._get_default_params(known_params)
        
        # 按相似度加权平均
        similar_tasks.sort(key=lambda x: x[1], reverse=True)
        
        # 取前3个最相似的任务
        top_tasks = similar_tasks[:3]
        
        suggested = {}
        for param in known_params:
            values = []
            for case, weight in top_tasks:
                if param in case.params:
                    values.append((case.params[param], weight))
            
            if values:
                # 加权平均
                total_weight = sum(w for _, w in values)
                if isinstance(values[0][0], (int, float)):
                    suggested[param] = sum(v * w for v, w in values) / total_weight
                else:
                    # 对于离散值，选择权重最高的
                    suggested[param] = max(values, key=lambda x: x[1])[0]
        
        return suggested
    
    def _task_similarity(self, task1: str, task2: str) -> float:
        """计算任务类型相似度"""
        # 简单实现：基于字符串重叠
        words1 = set(task1.lower().split('_'))
        words2 = set(task2.lower().split('_'))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _get_default_params(self, known_params: List[str]) -> Dict[str, Any]:
        """获取默认参数值"""
        defaults = {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 10,
            "max_iter": 100,
            "tol": 1e-4,
            "n_components": 2,
            "n_neighbors": 5,
            "alpha": 1.0,
            "C": 1.0,
            "gamma": "scale",
            "kernel": "rbf",
            "max_depth": 3,
            "n_estimators": 100
        }
        
        return {p: defaults.get(p, 0) for p in known_params}


if __name__ == "__main__":
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试迁移学习模块 ===")
    
    tl = TransferLearning()
    
    # 记录一些成功案例
    print("\n1. 记录成功案例")
    tl.update_success_case(
        "pls_da_analysis",
        {"n_components": 3, "scale": True, "method": "svd"},
        {"Q2": 0.75, "R2Y": 0.82},
        0.85
    )
    
    tl.update_success_case(
        "pls_da_analysis",
        {"n_components": 5, "scale": True, "method": "nipals"},
        {"Q2": 0.82, "R2Y": 0.88},
        0.90
    )
    
    tl.update_success_case(
        "pca_analysis",
        {"n_components": 4, "scale": True},
        {"explained_variance": 0.85},
        0.80
    )
    
    # 检索相似参数
    print("\n2. 检索相似参数")
    similar = tl.get_best_similar_params(
        {"n_components": 2, "scale": False},
        "pls_da_analysis"
    )
    print(f"相似参数: {similar}")
    
    # 获取统计
    print("\n3. 任务统计")
    stats = tl.get_task_statistics()
    print(f"统计: {stats}")
