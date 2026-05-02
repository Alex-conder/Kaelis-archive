"""
KgFlywheel 记忆管理
OpenClaw 架构 - Markdown 本地记忆 + JSON 元数据
"""
import os
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class KgFlywheelMemory:
    """
    知识图谱飞轮记忆管理
    
    存储结构：
    data/memory/{user_id}/
      ├── {session_id}.md       # Markdown 会话记录
      ├── {session_id}.meta.json # JSON 元数据
      └── reports/
            └── {report_id}.json  # 检查报告
    
    Markdown 格式：
    ```markdown
    # KgFlywheel Session - {session_id}
    Created: {timestamp}
    
    ## Action [extraction] - {timestamp}
    ### Input
    {user_input}
    
    ### Result
    - Extracted: {count} triples
    - Task ID: {task_id}
    
    ## Action [query] - {timestamp}
    ### Cypher
    ```cypher
    {query}
    ```
    
    ### Results
    {formatted_results}
    
    ## Action [inspection] - {timestamp}
    ### Summary
    - Overall Score: {score}%
    - Issues Found: {count}
    ```
    """
    
    def __init__(self, user_id: str, session_id: Optional[str] = None):
        self.user_id = user_id
        self.session_id = session_id or self._generate_session_id()
        self.base_path = Path("data/memory") / user_id
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.session_file = self.base_path / f"{self.session_id}.md"
        self.meta_file = self.base_path / f"{self.session_id}.meta.json"
        self.reports_dir = self.base_path / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # 初始化文件
        self._init_session_file()
    
    def _generate_session_id(self) -> str:
        return f"kg{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def _init_session_file(self):
        """初始化会话 Markdown 文件"""
        if not self.session_file.exists():
            header = f"""# KgFlywheel Session - {self.session_id}

**User**: {self.user_id}  
**Created**: {datetime.now().isoformat()}  
**Status**: Active

---

## Session Overview

This is a knowledge graph flywheel session following the Extract → Query → Inspect pipeline.

### Graph Statistics
- Total Entities: {{entity_count}}
- Total Relations: {{relation_count}}
- Last Inspection: {{last_inspection}}

---

"""
            self.session_file.write_text(header, encoding="utf-8")
            
            # 初始化元数据
            self._save_meta({
                "session_id": self.session_id,
                "user_id": self.user_id,
                "created_at": datetime.now().isoformat(),
                "entity_count": 0,
                "relation_count": 0,
                "last_inspection": None,
                "actions": [],
                "mentioned_entities": []  # 新增：记录会话中涉及的实体
            })
    
    def _save_meta(self, meta: Dict):
        """保存元数据"""
        self.meta_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def _load_meta(self) -> Dict:
        """加载元数据"""
        if self.meta_file.exists():
            return json.loads(self.meta_file.read_text(encoding="utf-8"))
        return {}
    
    def save_action(self, action_type: str, data: Dict):
        """
        保存动作记录到 Markdown
        
        Args:
            action_type: extraction | query | inspection
            data: 动作数据
        """
        timestamp = datetime.now().isoformat()
        
        # 构建 Markdown 片段
        md_section = f"\n## Action [{action_type}] - {timestamp}\n\n"
        
        if action_type == "extraction":
            md_section += self._format_extraction(data)
        elif action_type == "query":
            md_section += self._format_query(data)
        elif action_type == "inspection":
            md_section += self._format_inspection(data)
        else:
            md_section += f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n"
        
        md_section += "\n---\n"
        
        # 追加到文件
        with open(self.session_file, "a", encoding="utf-8") as f:
            f.write(md_section)
        
        # 更新元数据
        meta = self._load_meta()
        meta["actions"].append({
            "type": action_type,
            "timestamp": timestamp,
            "summary": self._summarize_action(action_type, data)
        })
        
        # 更新统计
        if action_type == "extraction":
            meta["entity_count"] += data.get("triples_extracted", 0)
        elif action_type == "inspection":
            meta["last_inspection"] = timestamp
            summary = data.get("summary", {})
            meta["entity_count"] = summary.get("entity_count", meta["entity_count"])
            meta["relation_count"] = summary.get("relation_count", meta["relation_count"])
        
        self._save_meta(meta)
    
    def _format_extraction(self, data: Dict) -> str:
        """格式化提取结果"""
        md = f"""### Extraction Result

**Task ID**: {data.get('task_id', 'N/A')}  
**Source**: {data.get('source', 'N/A')}  
**Triples Extracted**: {data.get('triples_extracted', 0)}

#### Extracted Triples

| Subject | Predicate | Object | Confidence |
|---------|-----------|--------|------------|
"""
        for t in data.get('triples', []):
            md += f"| {t.get('subject', '?')} | {t.get('predicate', '?')} | {t.get('object', '?')} | {t.get('confidence', 0):.2f} |\n"
        
        return md
    
    def _format_query(self, data: Dict) -> str:
        """格式化查询结果"""
        query_info = data.get('input', data.get('query', 'N/A'))
        md = f"""### Query Result

**Query**: `{query_info}`  
**Success**: {data.get('success', False)}  
**Result Count**: {data.get('result_count', 0)}

"""
        if data.get('cypher'):
            md += f"""#### Cypher Query
```cypher
{data['cypher']}
```

"""
        
        md += "#### Results\n\n"
        results = data.get('result', data.get('results', []))
        if results:
            md += "```json\n"
            md += json.dumps(results[:5], ensure_ascii=False, indent=2)
            if len(results) > 5:
                md += f"\n\n... ({len(results) - 5} more results)"
            md += "\n```\n"
        
        return md
    
    def _format_inspection(self, data: Dict) -> str:
        """格式化检查结果"""
        summary = data.get('summary', {})
        scores = data.get('scores', {})
        
        md = f"""### Quality Inspection Report

**Check ID**: {data.get('check_id', 'N/A')}  
**Type**: {data.get('check_type', 'full')}  
**Status**: {summary.get('status', 'unknown')}  
**Overall Score**: {summary.get('overall_score', 0) * 100:.1f}%

#### Statistics
- Entities: {summary.get('entity_count', 0)}
- Relations: {summary.get('relation_count', 0)}

#### Scores

| Metric | Score |
|--------|-------|
| Completeness | {scores.get('completeness', 0) * 100:.1f}% |
| Consistency | {scores.get('consistency', 0) * 100:.1f}% |
| Accuracy | {scores.get('accuracy', 0) * 100:.1f}% |

"""
        issues = data.get('issues', [])
        if issues:
            md += "#### Issues Found\n\n"
            for i, issue in enumerate(issues, 1):
                md += f"{i}. **[{issue.get('severity', 'info').upper()}]** {issue.get('description', '')}\n"
            md += "\n"
        
        return md
    
    def _summarize_action(self, action_type: str, data: Dict) -> str:
        """生成动作摘要"""
        if action_type == "extraction":
            return f"Extracted {data.get('triples_extracted', 0)} triples"
        elif action_type == "query":
            return f"Query returned {data.get('result_count', 0)} results"
        elif action_type == "inspection":
            score = data.get('summary', {}).get('overall_score', 0)
            return f"Inspection score: {score * 100:.1f}%"
        return "Action completed"
    
    def save_report(self, report: Dict) -> str:
        """保存检查报告到独立文件"""
        report_id = report.get('check_id', datetime.now().strftime('%Y%m%d%H%M%S'))
        report_file = self.reports_dir / f"{report_id}.json"
        
        report_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        return report_id
    
    def get_report(self, report_id: str) -> Optional[Dict]:
        """读取检查报告"""
        report_file = self.reports_dir / f"{report_id}.json"
        
        if report_file.exists():
            return json.loads(report_file.read_text(encoding="utf-8"))
        return None
    
    def list_reports(self) -> List[Dict]:
        """列出所有报告"""
        reports = []
        for report_file in self.reports_dir.glob("*.json"):
            try:
                data = json.loads(report_file.read_text(encoding="utf-8"))
                reports.append({
                    "report_id": report_file.stem,
                    "timestamp": data.get('timestamp'),
                    "status": data.get('summary', {}).get('status')
                })
            except Exception:
                pass
        
        return sorted(reports, key=lambda x: x['timestamp'] or '', reverse=True)
    
    def search_history(self, keyword: str) -> List[Dict]:
        """搜索历史记录"""
        meta = self._load_meta()
        matches = []
        
        for action in meta.get('actions', []):
            if keyword.lower() in action.get('summary', '').lower():
                matches.append(action)
        
        return matches
    
    def get_session_summary(self) -> Dict[str, Any]:
        """获取会话摘要"""
        meta = self._load_meta()
        
        # 统计动作
        action_counts = {}
        for action in meta.get('actions', []):
            t = action.get('type', 'unknown')
            action_counts[t] = action_counts.get(t, 0) + 1
        
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": meta.get('created_at'),
            "total_actions": len(meta.get('actions', [])),
            "action_breakdown": action_counts,
            "entity_count": meta.get('entity_count', 0),
            "relation_count": meta.get('relation_count', 0),
            "last_inspection": meta.get('last_inspection')
        }


    def _extract_entities(self, text: str) -> List[str]:
        """
        从文本中提取实体（简化版）
        生产环境可替换为 LLM 提取
        """
        import re
        # 匹配中文实体（2-10个中文字符）
        chinese_pattern = r'[\u4e00-\u9fa5]{2,10}'
        chinese_entities = re.findall(chinese_pattern, text)
        
        # 匹配英文实体（大写字母开头的单词序列）
        english_pattern = r'[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*'
        english_entities = re.findall(english_pattern, text)
        
        # 合并并去重
        all_entities = list(set(chinese_entities + english_entities))
        
        # 过滤掉常见停用词
        stopwords = {'一个', '这个', '那个', '什么', '怎么', '为什么', '如何', '可以', '需要', '进行', '完成', '开始', '结束'}
        return [e for e in all_entities if e not in stopwords and len(e) > 1]
    
    def record_entities(self, text: str):
        """
        记录文本中提到的实体到元数据
        """
        entities = self._extract_entities(text)
        if not entities:
            return
        
        meta = self._load_meta()
        existing = meta.get("mentioned_entities", [])
        meta["mentioned_entities"] = list(set(existing + entities))
        self._save_meta(meta)
    
    def get_session_graph_data(self) -> Dict[str, Any]:
        """
        获取会话相关的图谱数据
        返回：{ nodes: [...], edges: [...] }
        """
        meta = self._load_meta()
        entities = meta.get("mentioned_entities", [])
        
        return {
            "session_id": self.session_id,
            "entities": entities,
            "entity_count": len(entities)
        }


def create_kg_memory(user_id: str, session_id: Optional[str] = None) -> KgFlywheelMemory:
    """工厂函数"""
    return KgFlywheelMemory(user_id, session_id)
