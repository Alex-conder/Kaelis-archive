"""
Hermes 数据迁移连接器

功能:
1. 解析 Hermes MEMORY.md 文件，按标题拆分为 L2 记忆条目
2. 读取 SKILL.md 并通过 import_from_agentskills 纳管
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class HermesConnector:
    """Hermes 迁移连接器"""

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        self.memory_entries: List[Dict[str, Any]] = []
        self.skills: List[Dict[str, Any]] = []

    def parse_memory_md(self, md_path: Path) -> List[Dict[str, Any]]:
        """将 Markdown 记忆文件按 # 标题拆分为条目"""
        if not md_path.exists():
            return []

        text = md_path.read_text(encoding="utf-8")
        # 按一级标题拆分
        sections = re.split(r'\n(?=# )', text)
        entries = []

        for section in sections:
            section = section.strip()
            if not section:
                continue
            lines = section.splitlines()
            title = lines[0].lstrip("# ").strip() if lines else "untitled"
            body = "\n".join(lines[1:]).strip()

            entries.append({
                "title": title,
                "content": body,
                "source_file": str(md_path),
            })

        return entries

    def scan_memory(self) -> List[Dict[str, Any]]:
        """扫描所有 Markdown 记忆文件"""
        entries = []
        for md_file in self.source_path.rglob("*.md"):
            if md_file.name.startswith("SKILL"):
                continue  # 技能文件单独处理
            entries.extend(self.parse_memory_md(md_file))

        self.memory_entries = entries
        logger.info(f"Hermes 记忆扫描完成: 发现 {len(entries)} 个条目")
        return entries

    def scan_skills(self) -> List[Dict[str, Any]]:
        """扫描 SKILL.md 等技能文件"""
        skills = []
        for pattern in ["SKILLS.md", "SKILL_*.md", "skill_*.md"]:
            for skill_file in self.source_path.glob(pattern):
                try:
                    text = skill_file.read_text(encoding="utf-8")
                    skills.append({
                        "source_file": str(skill_file),
                        "name": skill_file.stem,
                        "content": text,
                    })
                except Exception as e:
                    logger.warning(f"无法读取技能文件 {skill_file}: {e}")

        self.skills = skills
        return skills

    def import_memory_to_l2(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """导入记忆到 L2"""
        from core.memory_manager_v2 import get_memory_manager

        mm = get_memory_manager()
        entries = self.scan_memory()
        imported = 0

        for i, entry in enumerate(entries):
            try:
                mm.write(
                    layer="L2",
                    key=f"hermes_{entry['title'][:50]}_{i}",
                    value=entry,
                    metadata={"source": "hermes_migration", "migrated": True},
                    user_id=user_id,
                )
                imported += 1
            except Exception as e:
                logger.warning(f"记忆导入失败: {e}")

        return {"total_found": len(entries), "imported": imported}

    def import_skills(self) -> Dict[str, Any]:
        """通过 agentskills 方式导入技能（增强版：支持 YAML frontmatter、Markdown 表格参数、JSON 代码块参数提取）"""
        from core.skill_manager import get_skill_manager

        sm = get_skill_manager()
        skills = self.scan_skills()
        imported = 0
        failed = 0

        for s in skills:
            try:
                parsed = self._parse_hermes_skill_md(s["content"], s["name"])
                name = parsed.get("name", s["name"])
                description = parsed.get("description", f"Imported from Hermes: {name}")
                params = parsed.get("params", {})
                task_type = parsed.get("task_type", "general")
                tags = parsed.get("tags", [])
                workflow = parsed.get("workflow")

                # 尝试以 agentskills 格式直接导入（若结构完整）
                agentskills_payload = {
                    "schema_version": "1.0",
                    "skill": {
                        "id": parsed.get("id", ""),
                        "name": name,
                        "description": description,
                        "task_type": task_type,
                        "parameters": params,
                        "workflow": workflow,
                        "tags": tags,
                        "metadata": {
                            "source": "hermes_import",
                            "imported_at": __import__("datetime").datetime.now().isoformat(),
                            "original_file": s.get("source_file", ""),
                        },
                    }
                }

                # 若解析到足够完整的 agentskills 结构，使用标准 importer
                if parsed.get("agentskills_compatible"):
                    result = sm.import_from_agentskills(agentskills_payload, run_sandbox=True)
                    if result:
                        imported += 1
                        continue

                # 否则回退到 register_skill
                sm.register_skill({
                    "name": name,
                    "task_type": task_type,
                    "description": description,
                    "params": params,
                    "workflow": workflow,
                    "tags": tags,
                    "source": "hermes_import",
                })
                imported += 1
            except Exception as e:
                logger.error(f"技能导入失败 {s['name']}: {e}")
                failed += 1

        return {"total_found": len(skills), "imported": imported, "failed": failed}

    # ------------------------------------------------------------------
    # USER.md 解析
    # ------------------------------------------------------------------

    def parse_user_md(self, md_path: Path) -> Dict[str, Any]:
        """解析 Hermes USER.md 文件，提取用户偏好、角色设定与约束条件"""
        if not md_path.exists():
            return {}

        text = md_path.read_text(encoding="utf-8")
        result: Dict[str, Any] = {
            "source_file": str(md_path),
            "preferences": {},
            "persona": "",
            "constraints": [],
        }

        # 提取 YAML frontmatter（若存在）
        frontmatter = {}
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    text = parts[2]
                except Exception:
                    pass

        if isinstance(frontmatter, dict):
            result["preferences"].update(frontmatter.get("preferences", {}))
            result["persona"] = frontmatter.get("persona", "")
            result["constraints"].extend(frontmatter.get("constraints", []))

        # 按二级标题分块解析
        sections = re.split(r'\n(?=##\s)', text)
        current_section = None
        for section in sections:
            section = section.strip()
            if not section:
                continue
            lines = section.splitlines()
            header = lines[0].strip() if lines else ""
            body_lines = lines[1:]

            # 识别区块类型
            section_type = None
            header_lower = header.lower()
            if any(k in header_lower for k in ("preference", "偏好", "设置", "settings", "config")):
                section_type = "preferences"
            elif any(k in header_lower for k in ("persona", "角色", "profile", "用户画像", "identity")):
                section_type = "persona"
            elif any(k in header_lower for k in ("constraint", "约束", "rule", "限制", "禁忌", "边界")):
                section_type = "constraints"
            else:
                current_section = None
                continue

            current_section = section_type

            if section_type == "persona":
                # 取连续非空文本作为 persona 描述
                desc_lines = []
                for line in body_lines:
                    if line.strip():
                        desc_lines.append(line.strip())
                    elif desc_lines:
                        break
                result["persona"] = "\n".join(desc_lines) if desc_lines else result["persona"]
            elif section_type == "constraints":
                for line in body_lines:
                    line = line.strip()
                    if line.startswith(("- ", "* ", "1. ", "2. ", "3. ")):
                        result["constraints"].append(line.lstrip("- *123456789.").strip())
                    elif line and not line.startswith("#"):
                        result["constraints"].append(line)
            elif section_type == "preferences":
                for line in body_lines:
                    line = line.strip()
                    # 键值对: `key`: value 或 - key: value
                    m = re.match(r'[-\*]?\s*`?([^`:]+)`?\s*[:：]\s*(.+)', line)
                    if m:
                        k, v = m.group(1).strip(), m.group(2).strip()
                        # 尝试类型转换
                        result["preferences"][k] = self._coerce_value(v)
                    elif line.startswith(("- ", "* ")):
                        # 列表项视为布尔偏好（存在即 True）
                        pref_name = line.lstrip("- *").strip()
                        if pref_name:
                            result["preferences"][pref_name] = True

        return result

    # ------------------------------------------------------------------
    # 记忆分层分类器
    # ------------------------------------------------------------------

    def classify_memory_layer(self, entry: Dict[str, Any]) -> str:
        """
        根据内容分析为每个记忆条目决定 L0/L1/L2/L3 层级。

        规则:
        - L0: 极短事实 (<50字)、瞬态上下文、当前状态、简单指令
        - L1: 会话/任务上下文、进行中事项、工作变量、短期活跃记忆
        - L2: 情景/事件序列、对话摘要、用户行为记录、永久归档的片段
        - L3: 知识图谱、实体关系、结构化概念、长期事实、跨用户共享知识
        """
        title = (entry.get("title", "") or "").lower()
        content = (entry.get("content", "") or "").lower()
        combined = f"{title} {content}"

        # L3 指标：知识图谱、实体关系、结构化知识
        l3_indicators = [
            "knowledge graph", "entity", "relationship", "ontology", "concept",
            "知识图谱", "实体", "关系", "本体", "概念网络", "语义网络",
            "defines", "is a type of", "connected to", "property of",
        ]
        for ind in l3_indicators:
            if ind in combined:
                return "L3"

        # 显式标签/分类覆盖
        if re.search(r'\b(layer[:：]?\s*L3|level[:：]?\s*3|semantic)\b', combined):
            return "L3"
        if re.search(r'\b(layer[:：]?\s*L1|level[:：]?\s*1|working|session)\b', combined):
            return "L1"
        if re.search(r'\b(layer[:：]?\s*L0|level[:：]?\s*0|sensory|transient|temp)\b', combined):
            return "L0"

        # L0 指标：极短、瞬态
        content_len = len(entry.get("content", ""))
        if content_len < 50:
            return "L0"
        l0_indicators = [
            "current status", "now", "today", "just", "temp", "cached",
            "当前状态", "刚刚", "临时", "缓存", "此刻",
        ]
        if any(ind in combined for ind in l0_indicators) and content_len < 200:
            return "L0"

        # L1 指标：会话、任务进行中、活跃上下文
        l1_indicators = [
            "session", "conversation", "chat", "turn", "active", "working",
            "任务", "会话", "对话", "进行中", "当前任务", "活跃", "工作记忆",
            "plan:", "todo:", "next step", "draft", "wip",
        ]
        if any(ind in combined for ind in l1_indicators):
            return "L1"

        # L2 指标：情景、摘要、归档、事件、历史
        l2_indicators = [
            "summary", "episode", "event", "history", "record", "archive",
            "摘要", "情景", "事件", "历史", "记录", "归档", "回顾", "经历",
            "user said", "assistant replied", "对话记录", "行为记录",
        ]
        if any(ind in combined for ind in l2_indicators):
            return "L2"

        # 默认策略：中等长度 -> L1，较长叙事 -> L2，结构化 -> L3
        if content_len < 150:
            return "L0"
        elif content_len < 800:
            return "L1"
        elif content_len < 3000:
            return "L2"
        else:
            # 超长文本若包含结构化数据仍可能为 L3
            if re.search(r'[\{\[]\s*"\w+":', entry.get("content", "")):
                return "L3"
            return "L2"

    # ------------------------------------------------------------------
    # 分层记忆导入
    # ------------------------------------------------------------------

    def import_to_layered_memory(self, user_id: str = "anonymous") -> Dict[str, Any]:
        """使用分类器将 Hermes 记忆导入到正确的 Kaelis 记忆层（而非全部 L2）"""
        from core.memory_manager_v2 import get_memory_manager

        mm = get_memory_manager()
        entries = self.scan_memory()
        stats = {"total_found": len(entries), "L0": 0, "L1": 0, "L2": 0, "L3": 0, "failed": 0}

        for i, entry in enumerate(entries):
            layer = self.classify_memory_layer(entry)
            key = f"hermes_{entry['title'][:50]}_{i}"
            try:
                mm.write(
                    layer=layer,
                    key=key,
                    value=entry,
                    metadata={
                        "source": "hermes_migration",
                        "migrated": True,
                        "original_layer_inference": layer,
                    },
                    user_id=user_id,
                )
                stats[layer] += 1
            except Exception as e:
                logger.warning(f"记忆导入失败 [{layer}] {key}: {e}")
                stats["failed"] += 1

        logger.info(
            f"分层记忆导入完成: 总计 {stats['total_found']}, "
            f"L0={stats['L0']} L1={stats['L1']} L2={stats['L2']} L3={stats['L3']} "
            f"失败={stats['failed']}"
        )
        return stats

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_value(v: str) -> Any:
        """将字符串偏好值转为合适类型"""
        v_lower = v.lower()
        if v_lower in ("true", "yes", "on", "是", "开启"):
            return True
        if v_lower in ("false", "no", "off", "否", "关闭"):
            return False
        try:
            if "." in v:
                return float(v)
            return int(v)
        except ValueError:
            pass
        return v

    def _parse_hermes_skill_md(self, text: str, fallback_name: str) -> Dict[str, Any]:
        """解析 Hermes / agentskills Markdown 技能文件，提取参数、描述、工作流等"""
        result: Dict[str, Any] = {
            "name": fallback_name,
            "description": "",
            "params": {},
            "task_type": "general",
            "tags": [],
            "workflow": None,
            "agentskills_compatible": False,
        }

        # 1. YAML frontmatter
        frontmatter = {}
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    text = parts[2]
                except Exception:
                    pass

        if isinstance(frontmatter, dict):
            result["name"] = frontmatter.get("name", result["name"])
            result["task_type"] = frontmatter.get("task_type", frontmatter.get("taskType", result["task_type"]))
            result["tags"] = frontmatter.get("tags", result["tags"])
            if "params" in frontmatter:
                result["params"] = frontmatter["params"]
            if "id" in frontmatter:
                result["id"] = frontmatter["id"]

        lines = text.splitlines()
        current_section = None
        in_code_block = False
        code_buffer: List[str] = []
        code_lang = ""

        for line in lines:
            stripped = line.strip()

            # 代码块边界
            if stripped.startswith("```"):
                if in_code_block:
                    # 代码块结束
                    block = "\n".join(code_buffer)
                    if code_lang in ("json", ""):
                        try:
                            parsed_json = json.loads(block)
                            if isinstance(parsed_json, dict):
                                # 若 JSON 对象键看起来像参数，合并到 params
                                if current_section in ("parameters", "params", "参数说明", "使用示例", "examples"):
                                    for k, v in parsed_json.items():
                                        if isinstance(v, dict):
                                            result["params"][k] = v
                                        else:
                                            result["params"][k] = {"default": v, "type": type(v).__name__}
                                elif current_section in ("workflow", "执行流程", "steps"):
                                    result["workflow"] = parsed_json
                        except Exception:
                            pass
                    in_code_block = False
                    code_buffer = []
                    code_lang = ""
                else:
                    in_code_block = True
                    code_lang = stripped.lstrip("`").strip().lower()
                continue

            if in_code_block:
                code_buffer.append(line)
                continue

            # 标题行识别区块
            if stripped.startswith("# ") and not result["description"]:
                result["name"] = stripped.lstrip("# ").strip()
                continue
            if stripped.startswith("## "):
                current_section = stripped.lstrip("## ").strip().lower()
                continue

            # 描述提取
            if current_section in ("描述", "description", "desc", "overview"):
                if stripped and not stripped.startswith("#"):
                    result["description"] = (result["description"] + "\n" + stripped).strip()
                continue

            # 元数据列表（如 "- 任务类型: xxx"）
            if current_section in ("元数据", "metadata"):
                m = re.match(r'[-\*]?\s*(\w+)\s*[:：]\s*(.+)', stripped)
                if m:
                    k, v = m.group(1).strip().lower(), m.group(2).strip()
                    if k in ("task_type", "task type", "任务类型"):
                        result["task_type"] = v
                    elif k in ("confidence", "置信度"):
                        try:
                            result["confidence"] = float(v)
                        except ValueError:
                            pass
                continue

            # Markdown 表格参数解析（常见于 参数说明）
            if current_section in ("参数说明", "parameters", "params", "parameter"):
                if stripped.startswith("|") and stripped.endswith("|") and "---" not in stripped:
                    cells = [c.strip() for c in stripped.strip("|").split("|")]
                    if len(cells) >= 2:
                        param_name = cells[0]
                        if param_name and param_name.lower() not in ("parameter", "参数", "name", "名称"):
                            param_info: Dict[str, Any] = {"type": "string", "description": ""}
                            if len(cells) >= 2:
                                param_info["type"] = cells[1]
                            if len(cells) >= 3:
                                param_info["default"] = self._coerce_value(cells[2])
                            if len(cells) >= 4:
                                param_info["description"] = cells[3]
                            result["params"][param_name] = param_info
                continue

            # 列表式参数解析（如 `- \_param\_: description`）
            if current_section in ("参数说明", "parameters", "params", "parameter"):
                m = re.match(r'[-\*]?\s*`?([^`:]+)`?\s*[:：]\s*(.+)', stripped)
                if m:
                    result["params"][m.group(1).strip()] = {"type": "string", "description": m.group(2).strip()}
                continue

        # 评估 agentskills 兼容度
        if result["name"] and (result["params"] or result["workflow"]):
            result["agentskills_compatible"] = True

        return result
