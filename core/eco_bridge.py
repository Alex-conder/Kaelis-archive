"""
生态互操作桥接器 — Eco Bridge

跨框架技能发现、同步与社区市场索引。

用法:
    from core.eco_bridge import EcoBridge
    bridge = EcoBridge()
    bridge.discover_local_agents()
    bridge.sync_skills_from("openclaw")
    results = bridge.search_community("数据分析")
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.migration.smart_detector import scan_for_competitors
from core.skill_universal_adapter import UniversalSkillAdapter

logger = logging.getLogger(__name__)


class EcoBridge:
    """
    生态桥接器：连接 Kaelis 与外部 Agent 生态。
    """

    def __init__(self):
        self.adapter = UniversalSkillAdapter()
        self.discovered: List[Dict[str, Any]] = []
        self.community_index: List[Dict[str, Any]] = []

    # ======================================================================
    # 本地 Agent 发现
    # ======================================================================

    def discover_local_agents(self) -> List[Dict[str, Any]]:
        """
        扫描本地安装的 Agent 框架。
        返回发现的数据源列表。
        """
        self.discovered = scan_for_competitors()
        logger.info(f"本地 Agent 扫描完成: 发现 {len(self.discovered)} 个数据源")
        return self.discovered

    def get_agent_summary(self) -> Dict[str, Any]:
        """获取已发现 Agent 的摘要统计"""
        summary = {"total": 0, "by_name": {}, "by_type": {}}
        for d in self.discovered:
            summary["total"] += 1
            name = d["name"]
            data_type = d["type"]
            summary["by_name"][name] = summary["by_name"].get(name, 0) + 1
            summary["by_type"][data_type] = summary["by_type"].get(data_type, 0) + 1
        return summary

    # ======================================================================
    # 技能同步
    # ======================================================================

    def sync_skills_from(self, source_framework: str, auto_import: bool = False) -> Dict[str, Any]:
        """
        从指定框架拉取技能并导入。

        Args:
            source_framework: "openclaw" | "hermes" | "agentskills"
            auto_import: 是否自动导入识别到的技能

        Returns:
            同步报告
        """
        if not self.discovered:
            self.discover_local_agents()

        targets = [d for d in self.discovered if d["name"] == source_framework]
        if not targets:
            return {"error": f"未检测到 {source_framework} 安装"}

        total_imported = 0
        total_failed = 0
        details = []

        for target in targets:
            path = target["path"]
            if auto_import:
                stats = self.adapter.batch_import(path)
                total_imported += stats.get("registered", 0)
                total_failed += stats.get("failed", 0)
                details.append({"source": path, "stats": stats})
            else:
                details.append({"source": path, "status": "detected", "size": target["size_human"]})

        return {
            "source": source_framework,
            "targets_found": len(targets),
            "imported": total_imported,
            "failed": total_failed,
            "details": details,
        }

    def push_skill_to(self, target_framework: str, skill_id: str) -> Dict[str, Any]:
        """
        将 Kaelis 技能导出并推送到其他框架。
        （当前为预留接口，待各框架开放写入 API 后实现）
        """
        skill = self.adapter.export_skill(skill_id, target_format="agentskills")
        if not skill:
            return {"error": f"技能 {skill_id} 不存在或导出失败"}

        # 写入到框架特定目录
        home = Path.home()
        export_dir = home / ".kaelis" / "exports" / target_framework
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"{skill['name']}.json"
        export_path.write_text(json.dumps(skill, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "skill_id": skill_id,
            "target": target_framework,
            "export_path": str(export_path),
            "status": "exported",
        }

    # ======================================================================
    # 社区技能市场索引
    # ======================================================================

    def search_community(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        搜索社区技能索引。
        优先使用已缓存的索引，必要时拉取最新。
        """
        if not self.community_index:
            self.refresh_community_index()

        # 简单关键词匹配（未来可接入向量检索）
        query_lower = query.lower()
        results = []
        for skill in self.community_index:
            score = 0
            text = f"{skill.get('name', '')} {skill.get('description', '')} {skill.get('task_type', '')}".lower()
            if query_lower in text:
                score += 1
            # 关键词分词匹配
            for word in query_lower.split():
                if word in text:
                    score += 0.5
            if score > 0:
                results.append({**skill, "_score": score})

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:top_k]

    def refresh_community_index(self) -> Dict[str, Any]:
        """
        刷新社区技能市场索引。
        当前从本地缓存和预置列表构建。
        """
        # 预置精选技能列表（agentskills.io 风格）
        preset = [
            {
                "name": "web_search",
                "task_type": "search",
                "description": "使用搜索引擎获取实时信息",
                "params": {"query": {"type": "string", "required": True}},
                "source": "agentskills_community",
                "rating": 4.5,
            },
            {
                "name": "code_review",
                "task_type": "development",
                "description": "自动审查代码质量并提出改进建议",
                "params": {"code": {"type": "string", "required": True}, "language": {"type": "string"}},
                "source": "agentskills_community",
                "rating": 4.2,
            },
            {
                "name": "data_analysis",
                "task_type": "analytics",
                "description": "对 CSV/JSON 数据进行统计分析和可视化建议",
                "params": {"data_path": {"type": "string", "required": True}},
                "source": "agentskills_community",
                "rating": 4.0,
            },
            {
                "name": "document_summarize",
                "task_type": "nlp",
                "description": "长文档自动摘要，支持多种输出格式",
                "params": {"document": {"type": "string", "required": True}, "max_length": {"type": "integer"}},
                "source": "agentskills_community",
                "rating": 4.3,
            },
            {
                "name": "metabolomics_pls_da",
                "task_type": "bioinformatics",
                "description": "代谢组学 PLS-DA 分析，自动参数优化",
                "params": {"file_path": {"type": "string", "required": True}},
                "source": "kaelis_built_in",
                "rating": 4.8,
            },
        ]

        self.community_index = preset
        logger.info(f"社区索引刷新完成: {len(preset)} 个技能")
        return {"total": len(preset), "source": "preset_cache"}

    def cache_index_to_memory(self) -> None:
        """将社区索引缓存到 L3 Semantic 记忆"""
        from core.memory_manager_v2 import get_memory_manager
        mm = get_memory_manager()
        mm.write(
            layer="L3",
            key="eco_bridge_community_index",
            value={
                "index": self.community_index,
                "updated_at": datetime.now().isoformat(),
            },
            metadata={"source": "eco_bridge", "type": "community_index"},
        )
        logger.info("社区索引已缓存到 L3 Semantic 记忆")


# ======================================================================
# 便捷函数
# ======================================================================

def get_eco_bridge() -> EcoBridge:
    """获取 EcoBridge 单例"""
    return EcoBridge()
