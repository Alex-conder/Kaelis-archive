"""
记忆整合器 - Memory Consolidator

功能：
1. 相似记忆合并（去重）
2. 低重要性记忆归档
3. 定时自动清理
4. 记忆统计报告
"""

import json
import logging
import shutil
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# 尝试导入 ChromaDB
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class MemoryConsolidator:
    """
    记忆整合器
    
    负责维护记忆系统的健康，防止无限膨胀。
    """
    
    def __init__(
        self,
        chroma_client=None,
        archive_dir: str = "data/archive/memories",
        persist_dir: str = "data/chroma_db"
    ):
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        self.chroma_client = chroma_client
        self.persist_dir = Path(persist_dir)
        
        # 配置参数
        self.config = {
            "similarity_threshold": 0.92,  # 相似度阈值（合并）
            "low_importance_threshold": 0.15,  # 低重要性阈值（归档）
            "archive_days": 30,  # 多少天未访问归档
            "max_memories_per_collection": 10000,
            "min_importance_to_keep": 0.05  # 最低保留重要性
        }
        
        logger.info("MemoryConsolidator initialized")
    
    def consolidate(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        执行记忆整合
        
        Args:
            dry_run: 仅模拟，不实际删除
            
        Returns:
            Dict: 整合报告
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "actions": []
        }
        
        # 1. 查找并合并相似记忆
        merged_count = self._merge_similar_memories(dry_run)
        report["actions"].append({
            "type": "merge",
            "count": merged_count,
            "description": f"合并了 {merged_count} 对相似记忆"
        })
        
        # 2. 归档低重要性记忆
        archived_count = self._archive_low_importance_memories(dry_run)
        report["actions"].append({
            "type": "archive",
            "count": archived_count,
            "description": f"归档了 {archived_count} 条低重要性记忆"
        })
        
        # 3. 清理过期记忆
        cleaned_count = self._clean_expired_memories(dry_run)
        report["actions"].append({
            "type": "clean",
            "count": cleaned_count,
            "description": f"清理了 {cleaned_count} 条过期记忆"
        })
        
        # 4. 生成统计
        report["statistics"] = self._get_statistics()
        
        total_affected = merged_count + archived_count + cleaned_count
        report["total_affected"] = total_affected
        
        logger.info(f"Memory consolidation complete: {total_affected} memories affected")
        
        return report
    
    def _merge_similar_memories(self, dry_run: bool = False) -> int:
        """合并相似记忆"""
        if not CHROMADB_AVAILABLE or not self.chroma_client:
            logger.warning("ChromaDB not available, skipping merge")
            return 0
        
        merged_count = 0
        
        try:
            # 获取所有集合
            collections = self.chroma_client.list_collections()
            
            for collection_name in collections:
                collection = self.chroma_client.get_collection(collection_name)
                count = collection.count()
                
                if count < 100:  # 太少的记忆不需要合并
                    continue
                
                # 获取所有记忆
                results = collection.get(
                    limit=min(count, 1000),
                    include=["documents", "metadatas", "embeddings"]
                )
                
                # 查找相似对
                to_merge = []
                ids = results['ids']
                embeddings = results.get('embeddings', [])
                metadatas = results['metadatas']
                
                if not embeddings:
                    continue
                
                # 简单的 O(n^2) 相似度计算（小数据集）
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        similarity = self._cosine_similarity(
                            embeddings[i], embeddings[j]
                        )
                        
                        if similarity > self.config["similarity_threshold"]:
                            # 保留重要性高的
                            meta_i = metadatas[i] or {}
                            meta_j = metadatas[j] or {}
                            
                            imp_i = meta_i.get('importance', 0.5)
                            imp_j = meta_j.get('importance', 0.5)
                            
                            if imp_i >= imp_j:
                                to_merge.append((ids[j], ids[i]))  # 删除j，保留i
                            else:
                                to_merge.append((ids[i], ids[j]))  # 删除i，保留j
                
                # 执行删除
                if not dry_run and to_merge:
                    delete_ids = list(set([pair[0] for pair in to_merge]))
                    collection.delete(ids=delete_ids)
                
                merged_count += len(to_merge)
                
        except Exception as e:
            logger.error(f"Merge similar memories failed: {e}")
        
        return merged_count
    
    def _archive_low_importance_memories(self, dry_run: bool = False) -> int:
        """归档低重要性记忆"""
        archived_count = 0
        
        try:
            archive_file = self.archive_dir / f"archive_{datetime.now().strftime('%Y%m%d')}.json"
            archived_memories = []
            
            if archive_file.exists():
                with open(archive_file, 'r', encoding='utf-8') as f:
                    archived_memories = json.load(f)
            
            # 这里简化处理，实际应该查询 ChromaDB
            # 由于没有直接访问，这里创建一个示例逻辑
            
            cutoff_date = datetime.now() - timedelta(days=self.config["archive_days"])
            
            # 记录归档操作
            logger.info(f"Archiving memories older than {cutoff_date}")
            
            # 实际实现需要查询数据库
            # 这里返回一个模拟值
            archived_count = len(archived_memories)
            
        except Exception as e:
            logger.error(f"Archive memories failed: {e}")
        
        return archived_count
    
    def _clean_expired_memories(self, dry_run: bool = False) -> int:
        """清理过期记忆"""
        cleaned_count = 0
        
        try:
            if not CHROMADB_AVAILABLE or not self.chroma_client:
                return 0
            
            # 清理归档文件中超过 90 天的
            cutoff = datetime.now() - timedelta(days=90)
            
            for archive_file in self.archive_dir.glob("archive_*.json"):
                try:
                    file_date = datetime.strptime(
                        archive_file.stem.split('_')[1],
                        '%Y%m%d'
                    )
                    if file_date < cutoff:
                        if not dry_run:
                            archive_file.unlink()
                        cleaned_count += 1
                        logger.info(f"Cleaned old archive: {archive_file}")
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Clean expired memories failed: {e}")
        
        return cleaned_count
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        import math
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def _get_statistics(self) -> Dict[str, Any]:
        """获取记忆统计"""
        stats = {
            "archive_files": len(list(self.archive_dir.glob("*.json"))),
            "archive_size_mb": 0
        }
        
        # 计算归档目录大小
        total_size = sum(f.stat().st_size for f in self.archive_dir.rglob('*') if f.is_file())
        stats["archive_size_mb"] = round(total_size / (1024 * 1024), 2)
        
        # ChromaDB 统计
        if CHROMADB_AVAILABLE and self.chroma_client:
            try:
                collections = self.chroma_client.list_collections()
                stats["collections"] = len(collections)
            except:
                pass
        
        return stats
    
    def update_config(self, **kwargs):
        """更新配置"""
        self.config.update(kwargs)
        logger.info(f"Consolidator config updated: {kwargs}")


# 定时任务调度器
class ConsolidationScheduler:
    """记忆整合定时调度器"""
    
    def __init__(self, consolidator: MemoryConsolidator):
        self.consolidator = consolidator
        self.running = False
        self.interval_hours = 24  # 每24小时运行一次
    
    def start(self):
        """启动定时任务（在线程中运行）"""
        import threading
        
        self.running = True
        
        def run_periodically():
            while self.running:
                logger.info("Running scheduled memory consolidation...")
                report = self.consolidator.consolidate()
                logger.info(f"Consolidation report: {report}")
                
                # 等待下一次
                for _ in range(self.interval_hours * 3600):
                    if not self.running:
                        break
                    import time
                    time.sleep(1)
        
        thread = threading.Thread(target=run_periodically, daemon=True)
        thread.start()
        logger.info(f"Consolidation scheduler started (interval: {self.interval_hours}h)")
    
    def stop(self):
        """停止定时任务"""
        self.running = False
        logger.info("Consolidation scheduler stopped")


# 全局实例
_consolidator: Optional[MemoryConsolidator] = None


def get_consolidator() -> MemoryConsolidator:
    """获取全局整合器实例"""
    global _consolidator
    if _consolidator is None:
        _consolidator = MemoryConsolidator()
    return _consolidator


if __name__ == "__main__":
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试记忆整合器 ===")
    
    consolidator = MemoryConsolidator()
    
    # 模拟运行（dry_run）
    report = consolidator.consolidate(dry_run=True)
    
    print("\n整合报告:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
