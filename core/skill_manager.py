"""
技能管理器 - Skill Manager

功能：
1. 技能的创建、存储、检索
2. 技能版本管理
3. 技能评分与使用统计
4. 从自进化成果自动创建技能
"""

import json
import logging
import hashlib
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# 尝试导入 ChromaDB
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


@dataclass
class Skill:
    """技能数据类"""
    id: str
    name: str
    task_type: str
    params: Dict[str, Any]
    workflow: Optional[Dict[str, Any]] = None
    description: str = ""
    source: str = "manual"  # manual, evolution, import
    rating: float = 0.0  # 0-5
    usage_count: int = 0
    success_count: int = 0
    created_by: str = "system"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    evolution_source: Optional[str] = None  # 关联的进化任务ID
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_embedding_text(self) -> str:
        """转换为用于向量检索的文本"""
        return f"{self.name} {self.description} {self.task_type} {' '.join(self.tags)}"
    
    @property
    def success_rate(self) -> float:
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count
    
    def increment_usage(self, success: bool = True):
        self.usage_count += 1
        if success:
            self.success_count += 1
        self.updated_at = datetime.now().isoformat()


class SkillStorage:
    """技能存储后端"""
    
    def __init__(self, persist_dir: str = "data/skills"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.chroma_client = None
        self.collection = None
        self._init_chromadb()
        
        # JSON文件存储（作为主存储）
        self.skills_file = self.persist_dir / "skills.json"
        self._skills_cache: Dict[str, Skill] = {}
        self._load_from_json()
    
    def _init_chromadb(self):
        """初始化ChromaDB用于向量检索"""
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available, using file-only storage")
            return
        
        try:
            # ChromaDB >= 1.5 推荐使用 PersistentClient
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.persist_dir / "chroma")
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name="skills",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("SkillStorage ChromaDB initialized")
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
    
    def _load_from_json(self):
        """从JSON文件加载技能"""
        if not self.skills_file.exists():
            return
        
        try:
            with open(self.skills_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for skill_data in data.get("skills", []):
                skill = Skill(**skill_data)
                self._skills_cache[skill.id] = skill
            
            logger.info(f"Loaded {len(self._skills_cache)} skills from JSON")
        except Exception as e:
            logger.error(f"Failed to load skills: {e}")
    
    def _save_to_json(self):
        """保存技能到JSON文件"""
        try:
            data = {
                "updated_at": datetime.now().isoformat(),
                "skills": [skill.to_dict() for skill in self._skills_cache.values()]
            }
            
            with open(self.skills_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save skills: {e}")
            return False
    
    def save(self, skill: Skill) -> bool:
        """保存技能"""
        try:
            # 更新缓存
            self._skills_cache[skill.id] = skill
            
            # 保存到JSON
            self._save_to_json()
            
            # 保存到ChromaDB（用于向量检索）
            if self.collection:
                self.collection.upsert(
                    ids=[skill.id],
                    documents=[skill.to_embedding_text()],
                    metadatas=[{
                        "task_type": skill.task_type,
                        "rating": skill.rating,
                        "usage_count": skill.usage_count,
                        "source": skill.source,
                        "success_rate": skill.success_rate
                    }]
                )
            
            return True
        except Exception as e:
            logger.error(f"Failed to save skill {skill.id}: {e}")
            return False
    
    def get(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills_cache.get(skill_id)
    
    def get_all(self) -> List[Skill]:
        """获取所有技能"""
        return list(self._skills_cache.values())
    
    def get_by_task_type(self, task_type: str) -> List[Skill]:
        """按任务类型获取技能"""
        return [
            skill for skill in self._skills_cache.values()
            if skill.task_type == task_type
        ]
    
    def delete(self, skill_id: str) -> bool:
        """删除技能"""
        if skill_id not in self._skills_cache:
            return False
        
        del self._skills_cache[skill_id]
        self._save_to_json()
        
        if self.collection:
            self.collection.delete(ids=[skill_id])
        
        return True
    
    def search_similar(self, query: str, top_k: int = 5) -> List[Tuple[Skill, float]]:
        """向量相似度搜索"""
        if not self.collection:
            # 回退到简单字符串匹配
            return self._simple_search(query, top_k)
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            output = []
            for i in range(len(results['ids'][0])):
                skill_id = results['ids'][0][i]
                distance = results['distances'][0][i]
                skill = self._skills_cache.get(skill_id)
                if skill:
                    output.append((skill, 1 - distance))  # 转换为相似度
            
            return output
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return self._simple_search(query, top_k)
    
    def _simple_search(self, query: str, top_k: int) -> List[Tuple[Skill, float]]:
        """简单字符串匹配搜索（回退方案）"""
        query_lower = query.lower()
        scored = []
        
        for skill in self._skills_cache.values():
            score = 0.0
            text = skill.to_embedding_text().lower()
            
            # 简单词频匹配
            words = query_lower.split()
            for word in words:
                if word in text:
                    score += 0.2
            
            if score > 0:
                scored.append((skill, min(score, 1.0)))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


class SkillManager:
    """
    技能管理器主类
    
    提供技能的全生命周期管理。
    """
    
    def __init__(self, storage: Optional[SkillStorage] = None):
        self.storage = storage or SkillStorage()
        logger.info("SkillManager initialized")
    
    def create_skill(
        self,
        name: str,
        task_type: str,
        params: Dict[str, Any],
        workflow: Optional[Dict] = None,
        description: str = "",
        tags: List[str] = None,
        created_by: str = "user"
    ) -> Optional[Skill]:
        """
        创建新技能
        
        Args:
            name: 技能名称
            task_type: 任务类型
            params: 技能参数
            workflow: 工作流定义（可选）
            description: 描述
            tags: 标签列表
            created_by: 创建者
            
        Returns:
            Skill: 创建的技能对象
        """
        # 生成唯一ID
        skill_id = hashlib.md5(
            f"{name}:{task_type}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        skill = Skill(
            id=skill_id,
            name=name,
            task_type=task_type,
            params=params,
            workflow=workflow,
            description=description,
            source="manual",
            tags=tags or [],
            created_by=created_by
        )
        
        if self.storage.save(skill):
            logger.info(f"Skill created: {skill_id} ({name})")
            return skill
        return None
    
    def create_from_evolution(
        self,
        task_type: str,
        params: Dict[str, Any],
        execution_record: Dict[str, Any],
        confidence: float
    ) -> Optional[Skill]:
        """
        从自进化成果创建技能
        
        Args:
            task_type: 任务类型
            params: 进化得到的最优参数
            execution_record: 执行记录
            confidence: 置信度
            
        Returns:
            Skill: 创建的技能对象
        """
        execution_id = execution_record.get("execution_id", "unknown")
        iterations = execution_record.get("iterations", [])
        
        # 生成技能名称
        skill_name = f"{task_type}_进化_{execution_id[:8]}"
        
        # 生成描述
        description = (
            f"由自进化引擎自动生成\n"
            f"执行ID: {execution_id}\n"
            f"迭代次数: {len(iterations)}\n"
            f"最终置信度: {confidence:.3f}\n"
            f"状态: {execution_record.get('status', 'unknown')}"
        )
        
        # 构建工作流（简化版）
        workflow = {
            "type": "evolution_optimized",
            "initial_params": execution_record.get("initial_params", {}),
            "optimized_params": params,
            "evolution_iterations": len(iterations),
            "criteria": execution_record.get("expectation", {}).get("criteria", "")
        }
        
        # 创建技能
        skill_id = hashlib.md5(
            f"evo:{execution_id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        skill = Skill(
            id=skill_id,
            name=skill_name,
            task_type=task_type,
            params=params,
            workflow=workflow,
            description=description,
            source="evolution",
            rating=min(5.0, confidence * 5),  # 根据置信度计算初始评分
            tags=["auto-generated", "evolution", task_type],
            created_by="self_evolving_engine",
            evolution_source=execution_id
        )
        
        if self.storage.save(skill):
            logger.info(f"Skill auto-created from evolution: {skill_id}")
            return skill
        return None
    
    def get_best_skill_for_task(
        self,
        task_type: str,
        min_rating: float = 3.0
    ) -> Optional[Skill]:
        """
        获取任务的最佳技能
        
        Args:
            task_type: 任务类型
            min_rating: 最低评分要求
            
        Returns:
            Optional[Skill]: 最佳技能
        """
        skills = self.storage.get_by_task_type(task_type)
        
        if not skills:
            return None
        
        # 按成功率、评分、使用次数综合排序
        def score_skill(skill: Skill) -> float:
            return (
                skill.success_rate * 0.4 +
                (skill.rating / 5.0) * 0.3 +
                min(skill.usage_count / 100, 1.0) * 0.3
            )
        
        # 过滤低评分
        qualified = [s for s in skills if s.rating >= min_rating]
        if not qualified:
            qualified = skills  # 如果没有达标的，返回所有
        
        best = max(qualified, key=score_skill)
        return best
    
    def search_skills(
        self,
        query: str,
        task_type: Optional[str] = None,
        top_k: int = 5
    ) -> List[Skill]:
        """
        搜索技能
        
        Args:
            query: 搜索查询
            task_type: 任务类型过滤
            top_k: 返回数量
            
        Returns:
            List[Skill]: 技能列表
        """
        results = self.storage.search_similar(query, top_k * 2)  # 多取一些用于过滤
        
        skills = [skill for skill, _ in results]
        
        if task_type:
            skills = [s for s in skills if s.task_type == task_type]
        
        return skills[:top_k]
    
    def use_skill(self, skill_id: str, success: bool = True) -> bool:
        """
        记录技能使用
        
        Args:
            skill_id: 技能ID
            success: 是否成功
            
        Returns:
            bool: 是否成功记录
        """
        skill = self.storage.get(skill_id)
        if not skill:
            return False
        
        skill.increment_usage(success)
        return self.storage.save(skill)
    
    def rate_skill(self, skill_id: str, rating: float) -> bool:
        """
        为技能评分
        
        Args:
            skill_id: 技能ID
            rating: 评分 (0-5)
            
        Returns:
            bool: 是否成功
        """
        skill = self.storage.get(skill_id)
        if not skill:
            return False
        
        # 移动平均更新评分
        if skill.usage_count == 0:
            skill.rating = rating
        else:
            skill.rating = (skill.rating * skill.usage_count + rating) / (skill.usage_count + 1)
        
        skill.rating = max(0, min(5, skill.rating))
        skill.updated_at = datetime.now().isoformat()
        
        return self.storage.save(skill)
    
    def list_skills(
        self,
        task_type: Optional[str] = None,
        source: Optional[str] = None,
        sort_by: str = "rating"
    ) -> List[Skill]:
        """
        列出技能
        
        Args:
            task_type: 任务类型过滤
            source: 来源过滤
            sort_by: 排序字段
            
        Returns:
            List[Skill]: 技能列表
        """
        skills = self.storage.get_all()
        
        if task_type:
            skills = [s for s in skills if s.task_type == task_type]
        
        if source:
            skills = [s for s in skills if s.source == source]
        
        # 排序
        if sort_by == "rating":
            skills.sort(key=lambda s: s.rating, reverse=True)
        elif sort_by == "usage":
            skills.sort(key=lambda s: s.usage_count, reverse=True)
        elif sort_by == "success_rate":
            skills.sort(key=lambda s: s.success_rate, reverse=True)
        elif sort_by == "created":
            skills.sort(key=lambda s: s.created_at, reverse=True)
        
        return skills
    
    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        return self.storage.delete(skill_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取技能统计信息"""
        skills = self.storage.get_all()
        
        if not skills:
            return {"total": 0}
        
        sources = {}
        task_types = {}
        total_usage = 0
        total_success = 0
        
        for skill in skills:
            sources[skill.source] = sources.get(skill.source, 0) + 1
            task_types[skill.task_type] = task_types.get(skill.task_type, 0) + 1
            total_usage += skill.usage_count
            total_success += skill.success_count
        
        return {
            "total": len(skills),
            "by_source": sources,
            "by_task_type": task_types,
            "total_usage": total_usage,
            "total_success": total_success,
            "overall_success_rate": total_success / total_usage if total_usage > 0 else 0,
            "avg_rating": sum(s.rating for s in skills) / len(skills)
        }
    
    # ==================== agentskills.io 格式兼容 ====================
    
    def export_to_agentskills(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        导出技能为 agentskills.io 标准格式
        
        Args:
            skill_id: 技能ID
            
        Returns:
            Dict: agentskills.io JSON 对象，失败返回 None
        """
        skill = self.storage.get(skill_id)
        if not skill:
            return None
        
        return {
            "schema_version": "1.0",
            "skill": {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "task_type": skill.task_type,
                "parameters": skill.params,
                "workflow": skill.workflow,
                "tags": skill.tags,
                "metadata": {
                    "created_at": skill.created_at,
                    "updated_at": skill.updated_at,
                    "version": skill.version,
                    "source": skill.source,
                    "created_by": skill.created_by,
                    "rating": skill.rating,
                    "usage_count": skill.usage_count,
                    "success_count": skill.success_count,
                    "success_rate": skill.success_rate,
                    "evolution_source": skill.evolution_source
                }
            }
        }
    
    def export_all_agentskills(self) -> Dict[str, Any]:
        """
        导出所有技能为 agentskills.io 批量格式
        
        Returns:
            Dict: 包含 skills 数组的标准包
        """
        skills = self.storage.get_all()
        return {
            "schema_version": "1.0",
            "export_metadata": {
                "exported_at": datetime.now().isoformat(),
                "total_skills": len(skills),
                "source_system": "Kaelis",
                "source_version": "8.0.0"
            },
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "task_type": s.task_type,
                    "parameters": s.params,
                    "workflow": s.workflow,
                    "tags": s.tags,
                    "metadata": {
                        "created_at": s.created_at,
                        "updated_at": s.updated_at,
                        "version": s.version,
                        "source": s.source,
                        "created_by": s.created_by,
                        "rating": s.rating,
                        "usage_count": s.usage_count,
                        "success_count": s.success_count,
                        "success_rate": s.success_rate,
                        "evolution_source": s.evolution_source
                    }
                }
                for s in skills
            ]
        }
    
    def import_from_agentskills(self, data: Dict[str, Any]) -> Optional[Skill]:
        """
        从 agentskills.io 格式导入技能
        
        支持两种输入格式：
        1. 单技能: {"schema_version": "1.0", "skill": {...}}
        2. 批量包: {"schema_version": "1.0", "skills": [...]}
        
        Args:
            data: agentskills.io JSON 数据
            
        Returns:
            Skill: 导入的第一个技能（批量导入时），失败返回 None
        """
        if not isinstance(data, dict):
            logger.error("Invalid agentskills data: expected dict")
            return None
        
        schema_version = data.get("schema_version", "1.0")
        if schema_version not in ("1.0",):
            logger.warning(f"Unknown agentskills schema version: {schema_version}")
        
        # 批量导入
        if "skills" in data and isinstance(data["skills"], list):
            imported = []
            for skill_data in data["skills"]:
                result = self._import_single_agentskill(skill_data)
                if result:
                    imported.append(result)
            logger.info(f"Bulk imported {len(imported)}/{len(data['skills'])} skills from agentskills")
            return imported[0] if imported else None
        
        # 单技能导入
        if "skill" in data:
            return self._import_single_agentskill(data["skill"])
        
        # 直接是 skill 对象
        if "id" in data and "name" in data:
            return self._import_single_agentskill(data)
        
        logger.error("Invalid agentskills data: missing 'skill' or 'skills' key")
        return None
    
    def _import_single_agentskill(self, skill_data: Dict[str, Any]) -> Optional[Skill]:
        """导入单个 agentskills 技能"""
        try:
            skill_id = skill_data.get("id") or hashlib.md5(
                f"import:{skill_data.get('name')}:{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
            
            meta = skill_data.get("metadata", {})
            
            skill = Skill(
                id=skill_id,
                name=skill_data.get("name", "Unnamed Skill"),
                task_type=skill_data.get("task_type", "general"),
                params=skill_data.get("parameters", skill_data.get("params", {})),
                workflow=skill_data.get("workflow"),
                description=skill_data.get("description", ""),
                source="import",
                rating=meta.get("rating", 0.0),
                usage_count=meta.get("usage_count", 0),
                success_count=meta.get("success_count", 0),
                created_by=meta.get("created_by", "agentskills.io"),
                created_at=meta.get("created_at", datetime.now().isoformat()),
                updated_at=meta.get("updated_at", datetime.now().isoformat()),
                version=meta.get("version", "1.0.0"),
                tags=skill_data.get("tags", []),
                evolution_source=meta.get("evolution_source")
            )
            
            if self.storage.save(skill):
                logger.info(f"Imported skill from agentskills: {skill.id} ({skill.name})")
                return skill
            return None
            
        except Exception as e:
            logger.error(f"Failed to import agentskills skill: {e}")
            return None


# 全局实例
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """获取全局技能管理器实例"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager


if __name__ == "__main__":
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试技能管理器 ===")
    
    manager = SkillManager()
    
    # 创建测试技能
    skill = manager.create_skill(
        name="PLS-DA 代谢组学分析",
        task_type="metabolomics_pls_da",
        params={"n_components": 5, "scale": True, "method": "nipals"},
        description="针对代谢组学数据优化的PLS-DA参数",
        tags=["metabolomics", "multivariate", "optimized"]
    )
    
    if skill:
        print(f"\n创建技能成功: {skill.id}")
        print(f"  名称: {skill.name}")
        print(f"  参数: {skill.params}")
        
        # 模拟使用
        manager.use_skill(skill.id, success=True)
        manager.use_skill(skill.id, success=True)
        manager.use_skill(skill.id, success=False)
        
        # 评分
        manager.rate_skill(skill.id, 4.5)
        
        # 获取更新后的技能
        updated = manager.storage.get(skill.id)
        print(f"\n更新后:")
        print(f"  使用次数: {updated.usage_count}")
        print(f"  成功率: {updated.success_rate:.2%}")
        print(f"  评分: {updated.rating:.2f}")
    
    # 统计
    stats = manager.get_statistics()
    print(f"\n统计信息: {stats}")
