"""
用户偏好推断模块 (P12-003)

基于 L2/L3 记忆数据，自动推断用户 Top-5 偏好标签。

推断维度：
1. 任务类型偏好（最常执行的任务）
2. 参数偏好（高频使用的参数值）
3. 交互模式偏好（活跃时间段、操作频率）
4. 主题偏好（L3 知识图谱中的高频实体类型）

输出格式：
    {
        "user_id": "xxx",
        "top_preferences": [
            {"tag": "metabolomics", "score": 0.85, "source": "task_frequency"},
            ...
        ],
        "confidence": 0.72
    }
"""

import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 支持直接运行
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)


class UserProfiler:
    """
    用户偏好推断器
    
    从四层记忆中提取用户行为模式，生成偏好标签。
    """
    
    def __init__(self, memory_manager=None, db_path: str = None):
        self.memory = memory_manager
        self.db_path = Path(db_path) if db_path else Path("data/kaelis_graph.db")
    
    def profile(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """
        生成用户偏好画像
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 偏好画像
        """
        if not self.memory:
            try:
                from core.memory_manager_v2 import get_memory_manager
                self.memory = get_memory_manager()
            except Exception as e:
                logger.warning(f"Memory manager not available: {e}")
                return {"user_id": user_id, "top_preferences": [], "confidence": 0.0}
        
        preferences = []
        
        # 1. 任务类型偏好（基于 L2 事件）
        task_prefs = self._analyze_task_preferences(user_id)
        preferences.extend(task_prefs)
        
        # 2. 参数偏好（基于 L1 活跃记忆）
        param_prefs = self._analyze_param_preferences(user_id)
        preferences.extend(param_prefs)
        
        # 3. 实体类型偏好（基于 L3 语义）
        entity_prefs = self._analyze_entity_preferences(user_id)
        preferences.extend(entity_prefs)
        
        # 合并同类项，取 Top-5
        merged = self._merge_preferences(preferences)
        top5 = merged[:5]
        
        # 计算整体置信度
        confidence = sum(p["score"] for p in top5) / len(top5) if top5 else 0.0
        
        return {
            "user_id": user_id,
            "top_preferences": top5,
            "preference_count": len(merged),
            "confidence": round(confidence, 2),
            "generated_at": datetime.now().isoformat()
        }
    
    def _analyze_task_preferences(self, user_id: str) -> List[Dict]:
        """分析任务类型偏好"""
        try:
            # 搜索 L2 中的任务记录
            results = self.memory.search("L2", "task_", top_k=50, user_id=user_id)
            task_types = []
            
            for r in results:
                meta = r.get("metadata", {})
                task_type = meta.get("task_type")
                if task_type:
                    task_types.append(task_type)
            
            if not task_types:
                return []
            
            counter = Counter(task_types)
            total = len(task_types)
            
            return [
                {
                    "tag": task_type,
                    "score": round(count / total, 2),
                    "source": "task_frequency",
                    "count": count
                }
                for task_type, count in counter.most_common(3)
            ]
        except Exception as e:
            logger.debug(f"Task preference analysis failed: {e}")
            return []
    
    def _analyze_param_preferences(self, user_id: str) -> List[Dict]:
        """分析参数偏好"""
        try:
            results = self.memory.search("L1", "", top_k=30, user_id=user_id)
            param_tags = []
            
            for r in results:
                value = r.get("value", {})
                if isinstance(value, dict):
                    # 提取参数键作为标签
                    for k in value.keys():
                        if not k.startswith("_"):
                            param_tags.append(k)
            
            if not param_tags:
                return []
            
            counter = Counter(param_tags)
            total = len(param_tags)
            
            return [
                {
                    "tag": f"param:{param}",
                    "score": round(count / total, 2),
                    "source": "param_frequency",
                    "count": count
                }
                for param, count in counter.most_common(3)
            ]
        except Exception as e:
            logger.debug(f"Param preference analysis failed: {e}")
            return []
    
    def _analyze_entity_preferences(self, user_id: str) -> List[Dict]:
        """分析知识图谱实体类型偏好"""
        try:
            import sqlite3
            from pathlib import Path
            if not self.db_path.exists():
                return []
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT type, COUNT(*) as cnt FROM kg_entities WHERE user_id = ? GROUP BY type ORDER BY cnt DESC LIMIT 5",
                    (user_id,)
                )
                rows = cursor.fetchall()
            
                if not rows:
                    return []
            
                total = sum(r[1] for r in rows)
                return [
                    {
                        "tag": f"entity:{entity_type}",
                        "score": round(count / total, 2),
                        "source": "entity_frequency",
                        "count": count
                    }
                    for entity_type, count in rows
                ]
        except Exception as e:
            logger.debug(f"Entity preference analysis failed: {e}")
            return []
    
    def _merge_preferences(self, preferences: List[Dict]) -> List[Dict]:
        """合并同类偏好，按分数排序"""
        # 按 tag 聚合
        groups = {}
        for p in preferences:
            tag = p["tag"]
            if tag not in groups:
                groups[tag] = {"tag": tag, "scores": [], "sources": set(), "count": 0}
            groups[tag]["scores"].append(p["score"])
            groups[tag]["sources"].add(p["source"])
            groups[tag]["count"] += p.get("count", 1)
        
        # 计算合并分数（取最高分 + 来源多样性加成）
        merged = []
        for tag, data in groups.items():
            max_score = max(data["scores"])
            diversity_bonus = min(0.1, len(data["sources"]) * 0.03)
            merged.append({
                "tag": tag,
                "score": round(min(1.0, max_score + diversity_bonus), 2),
                "sources": list(data["sources"]),
                "count": data["count"]
            })
        
        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged


# 全局实例
_profiler_instance: Optional[UserProfiler] = None


def get_user_profiler() -> UserProfiler:
    """获取全局用户画像器"""
    global _profiler_instance
    if _profiler_instance is None:
        _profiler_instance = UserProfiler()
    return _profiler_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试用户偏好推断 ===")
    profiler = UserProfiler()
    
    profile = profiler.profile("anonymous")
    print(f"Profile: {json.dumps(profile, indent=2, ensure_ascii=False)}")
    
    print("\n[OK] UserProfiler test completed")
