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
    
    def __init__(self, memory_manager=None):
        self.memory = memory_manager
    
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
            db_path = Path("data/kaelis_graph.db")
            if not db_path.exists():
                return []
            
            with sqlite3.connect(str(db_path)) as conn:
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
    
    def infer_decision_style(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """
        推断用户决策风格（激进/保守/均衡）

        基于 L2 Episodic 中的任务结果分析：
        - 高成功率 + 短耗时 → 激进
        - 高成功率 + 长耗时 → 保守
        - 低成功率 + 多次重试 → 探索型
        """
        try:
            import sqlite3
            from pathlib import Path
            db_path = Path("data/kaelis_dev.db")
            if not db_path.exists():
                return {"style": "unknown", "confidence": 0.0}

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT value, metadata FROM memory_l2 WHERE user_id = ? AND (source = 'skill' OR source = 'agent') LIMIT 100",
                    (user_id,),
                ).fetchall()

            success_count = 0
            failure_count = 0
            retry_total = 0
            durations = []

            for r in rows:
                try:
                    value = json.loads(r["value"]) if r["value"] else {}
                    meta = json.loads(r["metadata"]) if r["metadata"] else {}
                    status = value.get("status") or meta.get("status")
                    if status == "success":
                        success_count += 1
                    elif status == "failure":
                        failure_count += 1
                    retry_total += meta.get("retry_count", 0)
                    dur = meta.get("duration_ms")
                    if dur:
                        durations.append(dur)
                except Exception:
                    continue

            total = success_count + failure_count
            if total == 0:
                return {"style": "unknown", "confidence": 0.0}

            success_rate = success_count / total
            avg_duration = sum(durations) / len(durations) if durations else 0
            avg_retry = retry_total / total

            # 决策风格判定
            if success_rate > 0.8 and avg_duration < 5000 and avg_retry < 1:
                style = "aggressive"
                desc = "快速决策、高成功率，倾向于尝试新方案"
            elif success_rate > 0.8 and avg_duration > 10000:
                style = "conservative"
                desc = "谨慎验证、长耗时但高成功率，倾向于稳妥方案"
            elif avg_retry > 2:
                style = "exploratory"
                desc = "多次尝试、从失败中学习，倾向于探索不同路径"
            else:
                style = "balanced"
                desc = "决策风格均衡，能根据情境调整策略"

            return {
                "style": style,
                "description": desc,
                "success_rate": round(success_rate, 2),
                "avg_duration_ms": round(avg_duration, 0),
                "avg_retry": round(avg_retry, 2),
                "confidence": min(1.0, total / 20),  # 20次以上为高置信度
            }
        except Exception as e:
            logger.warning(f"Decision style inference failed: {e}")
            return {"style": "unknown", "confidence": 0.0}

    def infer_temporal_pattern(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """
        推断用户时间偏好模式

        分析用户活跃时间段、会话时长分布
        """
        try:
            import sqlite3
            from pathlib import Path
            from collections import Counter
            db_path = Path("data/kaelis_dev.db")
            if not db_path.exists():
                return {"peak_hour": "unknown", "confidence": 0.0}

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT created_at FROM memory_l2 WHERE user_id = ? AND source = 'chat'",
                    (user_id,),
                ).fetchall()

            hours = []
            for r in rows:
                try:
                    dt = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00").replace(" ", "T"))
                    hours.append(dt.hour)
                except Exception:
                    continue

            if not hours:
                return {"peak_hour": "unknown", "confidence": 0.0}

            hour_counter = Counter(hours)
            peak_hour, peak_count = hour_counter.most_common(1)[0]

            # 时段分类
            if 6 <= peak_hour < 12:
                period = "morning"
            elif 12 <= peak_hour < 18:
                period = "afternoon"
            elif 18 <= peak_hour < 23:
                period = "evening"
            else:
                period = "night"

            return {
                "peak_hour": peak_hour,
                "peak_period": period,
                "active_hours": sorted(hour_counter.keys()),
                "session_count": len(hours),
                "confidence": min(1.0, len(hours) / 10),
            }
        except Exception as e:
            logger.warning(f"Temporal pattern inference failed: {e}")
            return {"peak_hour": "unknown", "confidence": 0.0}

    def infer_communication_style(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """
        推断用户沟通习惯

        基于对话内容长度、指令清晰度、反馈频率
        """
        try:
            import sqlite3
            from pathlib import Path
            db_path = Path("data/kaelis_dev.db")
            if not db_path.exists():
                return {"style": "unknown", "confidence": 0.0}

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT value FROM memory_l2 WHERE user_id = ? AND source = 'chat' LIMIT 200",
                    (user_id,),
                ).fetchall()

            lengths = []
            for r in rows:
                try:
                    value = json.loads(r["value"]) if r["value"] else {}
                    content = str(value.get("content", value.get("message", "")))
                    lengths.append(len(content))
                except Exception:
                    continue

            if not lengths:
                return {"style": "unknown", "confidence": 0.0}

            avg_len = sum(lengths) / len(lengths)
            if avg_len < 20:
                style = "concise"
                desc = "简洁直接，偏好短指令"
            elif avg_len < 100:
                style = "moderate"
                desc = "表达适中，信息量合理"
            else:
                style = "verbose"
                desc = "详细描述，偏好完整上下文"

            return {
                "style": style,
                "description": desc,
                "avg_message_length": round(avg_len, 0),
                "message_count": len(lengths),
                "confidence": min(1.0, len(lengths) / 20),
            }
        except Exception as e:
            logger.warning(f"Communication style inference failed: {e}")
            return {"style": "unknown", "confidence": 0.0}

    def profile_advanced(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """
        生成完整的多维用户画像

        包含：基础偏好 + 决策风格 + 时间模式 + 沟通习惯 + 知识结构
        """
        base = self.profile(user_id)

        advanced = {
            **base,
            "decision_style": self.infer_decision_style(user_id),
            "temporal_pattern": self.infer_temporal_pattern(user_id),
            "communication_style": self.infer_communication_style(user_id),
            "knowledge_gaps": self._infer_knowledge_gaps(user_id),
        }

        return advanced

    def _infer_knowledge_gaps(self, user_id: str = "anonymous") -> List[Dict[str, Any]]:
        """
        推断用户知识盲区

        基于用户频繁查询但未获得满意结果的主题
        """
        try:
            import sqlite3
            from pathlib import Path
            from collections import Counter
            db_path = Path("data/kaelis_dev.db")
            if not db_path.exists():
                return []

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT key, value, metadata FROM memory_l2 WHERE user_id = ? AND source = 'chat' LIMIT 200",
                    (user_id,),
                ).fetchall()

            # 提取查询关键词（简化：取 key 中的主题词）
            topics = []
            for r in rows:
                key = r["key"]
                if "search" in key or "query" in key:
                    topics.append(key.replace("search_", "").replace("query_", ""))

            counter = Counter(topics)
            # 高频查询但未找到结果（metadata 中标记 failed）
            gaps = []
            for topic, count in counter.most_common(5):
                if count >= 3:
                    gaps.append({"topic": topic, "query_count": count, "suggestion": f"建议补充 {topic} 相关知识"})

            return gaps
        except Exception as e:
            logger.debug(f"Knowledge gap inference failed: {e}")
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
