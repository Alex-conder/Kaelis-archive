"""
KgFlywheel Agent 编排器
知识图谱飞轮：提取-查询-质检 闭环智能体
"""
import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# MemoryStore 占位符（如需使用 core.memory_consolidator 可在此扩展）
class MemoryStore:
    def __init__(self, user_id: str, namespace: str = "default"):
        self.user_id = user_id
        self.namespace = namespace
    
    def save(self, data: dict):
        pass
    
    def load(self) -> list:
        return []
    
    def record_entities(self, text: str):
        """记录实体（用于图谱可视化）"""
        pass


class AgentState(Enum):
    """Agent 执行状态"""
    IDLE = "idle"
    EXTRACTING = "extracting"
    QUERYING = "querying"
    INSPECTING = "inspecting"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class FlywheelResponse:
    """飞轮响应"""
    reply: str
    session_id: str
    state: AgentState
    data: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[str] = field(default_factory=list)


class KgFlywheelAgent:
    """知识图谱飞轮 Agent - OpenClaw 架构实现"""
    
    def __init__(self, user_id: str, session_id: Optional[str] = None, tool_registry=None):
        self.user_id = user_id
        self.session_id = session_id or self._generate_session_id()
        self.state = AgentState.IDLE
        self.tools = tool_registry
        self.memory = MemoryStore(user_id=user_id, namespace=f"kg_{self.session_id}")
    
    def _generate_session_id(self) -> str:
        return f"kg{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def _extract_user_info(self, text: str) -> Dict[str, str]:
        """从用户输入中提取姓名、职业、偏好等关键信息"""
        info: Dict[str, str] = {}
        text_lower = text.lower()
        
        # 姓名提取
        name_patterns = [
            r'我叫([^\s，。,；;!?！?]{1,10})',
            r'我的名字是([^\s，。,；;!?！?]{1,10})',
            r'我是([^\s，。,；;!?！?]{2,10})(?:，|。|,|\s)',
        ]
        for pat in name_patterns:
            m = re.search(pat, text)
            if m:
                info['name'] = m.group(1).strip('，。,. ')
                break
        
        # 职业提取
        job_patterns = [
            r'(?:我是|做|从事|职业是|工作)(.*?)(?:工程师|开发|设计师|经理|研究员|医生|教师|律师|会计|分析师|运营|产品|销售|市场)(?:师|员|经理|主管|总监)?',
            r'(?:我是|做|从事|职业是|工作)(.*?)(?:工作|职业)',
        ]
        for pat in job_patterns:
            m = re.search(pat, text)
            if m:
                info['job'] = m.group(0).strip('，。,. ')
                break
        
        # 偏好/技能提取
        pref_patterns = [
            r'我(?:喜欢|偏好|习惯|常用|擅长)(.*?)(?:，|。|,|\s|；|;|$)',
            r'我(?:用|使用)(.*?)(?:，|。|,|\s|；|;|$)',
        ]
        for pat in pref_patterns:
            m = re.search(pat, text)
            if m:
                info['preference'] = m.group(1).strip('，。,. ')
                break
        
        return info
    
    async def process(self, user_input: str, context: Optional[Dict] = None) -> FlywheelResponse:
        """
        Agent 主循环 - Plan → Execute → Reflect
        
        意图分类：
        - extract: 提取知识三元组
        - query: 查询图谱
        - inspect: 质量检查
        - flywheel: 执行完整闭环
        """
        try:
            # Plan: 分析意图
            intent, confidence = self._analyze_intent(user_input)
            
            # Execute: 根据意图执行
            if intent == "extract":
                result = await self._run_extraction(user_input)
            elif intent == "query":
                result = await self._run_query(user_input)
            elif intent == "inspect":
                result = await self._run_inspection()
            elif intent == "flywheel":
                result = await self._run_flywheel(user_input)
            else:
                result = await self._run_general_chat(user_input)
            
            # 注入策略信息到 data
            result.data["strategy"] = {
                "intent": intent,
                "confidence": round(confidence, 2),
                "agent_state": result.state.value if hasattr(result.state, 'value') else str(result.state),
            }
            
            # 检测用户个人信息
            user_info = self._extract_user_info(user_input)
            if user_info:
                result.data["new_user_info"] = user_info
            
            return result
                
        except Exception as e:
            self.state = AgentState.ERROR
            return FlywheelResponse(
                reply=f"执行错误: {str(e)}",
                session_id=self.session_id,
                state=self.state,
                data={
                    "strategy": {
                        "intent": "error",
                        "confidence": 0.0,
                        "agent_state": "error",
                    }
                }
            )
    
    def _analyze_intent(self, text: str) -> tuple[str, float]:
        """分析用户意图，返回 (意图, 置信度)"""
        text_lower = text.lower()
        keywords = {
            "extract": ["提取", "抽取", "分析文本", "解析", "parse", "extract", "从", "中分析"],
            "query": ["查询", "查找", "搜索", "query", "search", "find", "什么关系"],
            "inspect": ["质检", "检查", "质量", "评估", "inspect", "check", "质量如何"],
            "flywheel": ["飞轮", "完整流程", "闭环", "全流程", "flywheel", "pipeline", "执行全部"]
        }
        
        best_intent = "general"
        best_score = 0.0
        
        for intent, kws in keywords.items():
            matches = sum(1 for kw in kws if kw in text_lower)
            if matches > 0:
                score = min(matches / 3.0, 1.0)  # 最多匹配 3 个关键词达到 1.0
                if score > best_score:
                    best_score = score
                    best_intent = intent
        
        # general 的默认置信度为 0.5
        if best_intent == "general":
            best_score = 0.5
            
        return best_intent, best_score
    
    async def _run_extraction(self, text: str) -> FlywheelResponse:
        """Step 1: 提取知识三元组"""
        self.state = AgentState.EXTRACTING
        
        result = await self.tools.call("extract_triples", {
            "text": text,
            "source": f"session_{self.session_id}",
            "user_id": self.user_id
        })
        
        # 保存到记忆
        self.memory.save({
            "type": "extraction",
            "input": text,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        # 记录文本中提到的实体（用于图谱可视化）
        self.memory.record_entities(text)
        
        # 从提取的三元组中记录实体
        for triple in result.get('triples', []):
            entities_str = f"{triple.get('subject', '')} {triple.get('object', '')}"
            self.memory.record_entities(entities_str)
        
        # 构建回复
        reply = f"✅ 知识提取完成!\n\n"
        reply += f"📊 提取三元组数：{result.get('triples_extracted', 0)}\n"
        reply += f"🆔 任务ID：{result.get('task_id', 'N/A')}\n\n"
        
        triples = result.get('triples', [])
        if triples:
            reply += "📋 提取结果示例：\n"
            for i, t in enumerate(triples[:3], 1):
                reply += f"  {i}. [{t.get('subject', '?')}] → "
                reply += f"({t.get('predicate', '?')}) → "
                reply += f"[{t.get('object', '?')}] "
                reply += f"置信度: {t.get('confidence', 0):.2f}\n"
            if len(triples) > 3:
                reply += f"  ... 还有 {len(triples) - 3} 个\n"
        
        self.state = AgentState.COMPLETED
        return FlywheelResponse(
            reply=reply,
            session_id=self.session_id,
            state=self.state,
            data=result,
            tool_calls=["extract_triples"]
        )
    
    async def _run_query(self, query_text: str) -> FlywheelResponse:
        """Step 2: 查询图谱"""
        self.state = AgentState.QUERYING
        
        # 构建 Cypher 查询
        cypher = self._build_cypher(query_text)
        
        result = await self.tools.call("query_graph", {
            "query": cypher,
            "user_id": self.user_id
        })
        
        self.memory.save({
            "type": "query",
            "input": query_text,
            "cypher": cypher,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        if result.get("success"):
            reply = f"🔍 图谱查询结果：\n\n"
            reply += f"📊 找到 {result.get('result_count', 0)} 条记录\n\n"
            
            results = result.get('results', [])
            for i, record in enumerate(results[:5], 1):
                reply += f"  {i}. {json.dumps(record, ensure_ascii=False)[:100]}...\n"
            
            if len(results) > 5:
                reply += f"  ... 还有 {len(results) - 5} 条\n"
        else:
            reply = f"❌ 查询失败：{result.get('error', '未知错误')}"
        
        self.state = AgentState.COMPLETED
        return FlywheelResponse(
            reply=reply,
            session_id=self.session_id,
            state=self.state,
            data=result,
            tool_calls=["query_graph"]
        )
    
    def _build_cypher(self, text: str) -> str:
        """自然语言转 Cypher"""
        text_lower = text.lower()
        
        # 查询所有实体
        if any(kw in text for kw in ["所有", "全部", "list", "all"]):
            return "MATCH (n:Entity) RETURN n LIMIT 20"
        
        # 查询关系
        if "关系" in text or "related" in text_lower:
            return "MATCH (s:Entity)-[r:RELATES]->(o:Entity) RETURN s, r, o LIMIT 20"
        
        # 提取中文实体名
        entities = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        if entities:
            return f"MATCH (n:Entity {{name: '{entities[0]}'}})-[r]-(m) RETURN n, r, m"
        
        # 默认
        return "MATCH (n:Entity) RETURN n LIMIT 10"
    
    async def _run_inspection(self) -> FlywheelResponse:
        """Step 3: 质量检查"""
        self.state = AgentState.INSPECTING
        
        result = await self.tools.call("run_quality_check", {
            "check_type": "full",
            "user_id": self.user_id
        })
        
        self.memory.save({
            "type": "inspection",
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        summary = result.get("summary", {})
        scores = result.get("scores", {})
        
        reply = f"🔍 质量检查报告\n"
        reply += f"{'='*40}\n\n"
        reply += f"📊 综合评分: {summary.get('overall_score', 0) * 100:.1f}%\n"
        reply += f"📝 检查实体数: {summary.get('entity_count', 0)}\n"
        reply += f"🔗 检查关系数: {summary.get('relation_count', 0)}\n\n"
        
        reply += "📈 详细指标：\n"
        reply += f"  • 完整性: {scores.get('completeness', 0) * 100:.1f}%\n"
        reply += f"  • 一致性: {scores.get('consistency', 0) * 100:.1f}%\n"
        reply += f"  • 准确性: {scores.get('accuracy', 0) * 100:.1f}%\n\n"
        
        issues = result.get("issues", [])
        if issues:
            reply += f"⚠️ 发现 {len(issues)} 个问题：\n"
            for i, issue in enumerate(issues[:5], 1):
                reply += f"  {i}. [{issue.get('severity', 'info')}] {issue.get('description', '')[:50]}\n"
        else:
            reply += "✅ 未发现质量问题\n"
        
        self.state = AgentState.COMPLETED
        return FlywheelResponse(
            reply=reply,
            session_id=self.session_id,
            state=self.state,
            data=result,
            tool_calls=["run_quality_check"]
        )
    
    async def _run_flywheel(self, text: str) -> FlywheelResponse:
        """
        执行完整飞轮闭环
        Extract → Query → Inspect
        """
        reply_parts = ["🔄 知识图谱飞轮 - 完整闭环执行", "=" * 40, ""]
        all_results = {}
        
        # 1. Extract
        reply_parts.append("📥 Step 1: 知识提取")
        reply_parts.append("-" * 20)
        extract_resp = await self._run_extraction(text)
        reply_parts.append(extract_resp.reply)
        all_results["extraction"] = extract_resp.data
        reply_parts.append("")
        
        # 2. Query
        reply_parts.append("🔍 Step 2: 图谱查询")
        reply_parts.append("-" * 20)
        query_result = await self.tools.call("query_graph", {
            "query": "MATCH (n:Entity) RETURN count(n) as total_entities"
        })
        total = query_result.get('results', [{}])[0].get('total_entities', 0)
        reply_parts.append(f"✅ 图谱验证完成，当前共 {total} 个实体")
        all_results["query"] = query_result
        reply_parts.append("")
        
        # 3. Inspect
        reply_parts.append("🔍 Step 3: 质量检查")
        reply_parts.append("-" * 20)
        inspect_resp = await self._run_inspection()
        reply_parts.append(inspect_resp.reply)
        all_results["inspection"] = inspect_resp.data
        
        # 总结
        overall_score = inspect_resp.data.get("summary", {}).get("overall_score", 0)
        reply_parts.extend(["", "=" * 40, f"✨ 飞轮完成! 综合质量评分: {overall_score * 100:.1f}%"])
        
        return FlywheelResponse(
            reply="\n".join(reply_parts),
            session_id=self.session_id,
            state=AgentState.COMPLETED,
            data={"flywheel_results": all_results},
            tool_calls=["extract_triples", "query_graph", "run_quality_check"]
        )
    
    async def _run_general_chat(self, text: str) -> FlywheelResponse:
        """通用对话"""
        reply = """🤖 我是知识图谱飞轮助手，支持以下功能：

1️⃣ **知识提取** - 从文本中抽取实体关系
   例: "提取：阿里巴巴由马云创立"

2️⃣ **图谱查询** - 查询已构建的知识图谱  
   例: "查询马云的所有关系"

3️⃣ **质量检查** - 评估图谱完整性/一致性
   例: "运行质量检查"

4️⃣ **完整飞轮** - 执行 Extract→Query→Inspect 闭环
   例: "执行飞轮：分析这段文本"

请告诉我您想做什么？"""
        
        return FlywheelResponse(
            reply=reply,
            session_id=self.session_id,
            state=AgentState.COMPLETED,
            data={},
            tool_calls=[]
        )


def create_kg_flywheel_agent(user_id: str, session_id: Optional[str] = None, tool_registry=None):
    """工厂函数 - 创建 KgFlywheel Agent"""
    return KgFlywheelAgent(user_id, session_id, tool_registry)
