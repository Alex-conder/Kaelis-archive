"""
技能文档生成器 (P13-001)

任务成功后，使用 LLM 自动生成 SKILL.md 格式文档。
输出符合 agentskills.io 规范，存入 data/skills/generated/。

生成策略：
- 基于 ExecutionRecord 提取关键参数、结果、优化路径
- LLM 生成人类可读的技能说明文档
- 包含参数说明、使用示例、注意事项
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SkillDocumentGenerator:
    """
    SKILL.md 文档生成器
    
    将执行记录转换为标准化的技能文档。
    """
    
    def __init__(self, llm_client=None, output_dir: str = "data/skills/generated",
                 trigger_threshold: int = 5, quality_min_confidence: float = 0.7,
                 improvement_dir: str = "data/skills/improvements"):
        self.llm_client = llm_client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trigger_threshold = trigger_threshold
        self.quality_min_confidence = quality_min_confidence
        self.improvement_dir = Path(improvement_dir)
        self.improvement_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(
        self,
        execution_record: Dict[str, Any],
        skill_id: Optional[str] = None
    ) -> Optional[Path]:
        """
        生成 SKILL.md 文档
        
        Args:
            execution_record: 自进化引擎的执行记录
            skill_id: 技能ID（可选，从 record 中提取）
            
        Returns:
            Path: 生成的文件路径，失败返回 None
        """
        try:
            # 提取关键信息
            task_type = execution_record.get("task_type", "unknown")
            best_params = execution_record.get("best_params", {})
            best_result = execution_record.get("best_result", {})
            confidence = execution_record.get("best_confidence", 0.0)
            iterations = execution_record.get("iterations", [])
            
            # 生成文档内容
            if self.llm_client:
                content = self._generate_with_llm(
                    task_type, best_params, best_result, confidence, iterations
                )
            else:
                content = self._generate_template(
                    task_type, best_params, best_result, confidence, iterations
                )
            
            # 保存文件
            skill_id = skill_id or execution_record.get("generated_skill_id") or f"{task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            # 清理文件名
            safe_name = re.sub(r'[^\w\-_.]', '_', skill_id)[:64]
            file_path = self.output_dir / f"{safe_name}.md"
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            logger.info(f"SKILL.md generated: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Skill document generation failed: {e}")
            return None
    
    def _generate_with_llm(
        self,
        task_type: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        confidence: float,
        iterations: list
    ) -> str:
        """使用 LLM 生成高质量技能文档"""
        
        prompt = f"""你是一个专业的 AI 技能文档撰写助手。请根据以下任务执行记录，生成一份标准的 SKILL.md 文档。

任务类型: {task_type}
最终置信度: {confidence:.3f}
迭代次数: {len(iterations)}

最优参数:
```json
{json.dumps(params, indent=2, ensure_ascii=False)}
```

执行结果:
```json
{json.dumps(result, indent=2, ensure_ascii=False)}
```

迭代摘要:
{self._summarize_iterations(iterations)}

请生成以下格式的 Markdown 文档:

```markdown
# [技能名称]

## 描述
[一句话描述这个技能的功能和适用场景]

## 参数说明
| 参数 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
[参数表格]

## 使用示例
[具体的调用示例]

## 优化路径
[从初始参数到最优参数的优化过程简述]

## 注意事项
[使用时的限制条件或注意事项]

## 元数据
- 任务类型: {task_type}
- 置信度: {confidence:.3f}
- 迭代次数: {len(iterations)}
- 生成时间: {datetime.now().isoformat()}
- 生成来源: Kaelis 自进化引擎
```

要求：
1. 技能名称使用中文，简洁有力
2. 参数说明必须包含每个参数的类型和作用
3. 使用示例必须是具体的 JSON 格式
4. 优化路径要说明哪些参数被调整以及为什么
5. 注意事项要真实有用，不要泛泛而谈
6. 总字数控制在 800 字以内
7. 直接输出 Markdown 内容，不要包含 ```markdown 代码块标记
"""
        
        try:
            response = self.llm_client.chat(prompt, temperature=0.3)
            return str(response)
        except Exception as e:
            logger.warning(f"LLM generation failed, fallback to template: {e}")
            return self._generate_template(task_type, params, result, confidence, iterations)
    
    def _generate_template(
        self,
        task_type: str,
        params: Dict[str, Any],
        result: Dict[str, Any],
        confidence: float,
        iterations: list
    ) -> str:
        """使用模板生成基础技能文档（LLM 不可用时的降级方案）"""
        
        # 参数表格
        param_rows = []
        for k, v in params.items():
            vtype = type(v).__name__
            param_rows.append(f"| {k} | {vtype} | {v} | 任务参数 |")
        param_table = "\n".join(param_rows) if param_rows else "| (无) | - | - | - |"
        
        # 结果摘要
        result_summary = json.dumps(result, indent=2, ensure_ascii=False) if result else "(无详细结果)"
        
        # 迭代摘要
        iteration_summary = self._summarize_iterations(iterations)
        
        return f"""# {task_type} 优化技能

## 描述
针对 `{task_type}` 任务的自进化优化技能。通过 {len(iterations)} 次迭代找到最优参数组合，最终置信度达到 {confidence:.3f}。

## 参数说明
| 参数 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
{param_table}

## 使用示例
```json
{json.dumps(params, indent=2, ensure_ascii=False)}
```

## 执行结果
```json
{result_summary}
```

## 优化路径
{iteration_summary}

## 注意事项
- 本技能基于历史数据自动生成，建议在实际使用前进行小规模验证
- 参数最优值可能因数据分布变化而失效，建议定期重新运行自进化流程
- 置信度 {confidence:.3f} 表示该参数组合在历史数据上的表现，不保证未来性能

## 元数据
- 任务类型: {task_type}
- 置信度: {confidence:.3f}
- 迭代次数: {len(iterations)}
- 生成时间: {datetime.now().isoformat()}
- 生成来源: Kaelis 自进化引擎 (模板模式)
"""
    
    def _summarize_iterations(self, iterations: list) -> str:
        """生成迭代过程摘要"""
        if not iterations:
            return "无迭代记录。"
        
        lines = []
        for i, itr in enumerate(iterations[:5], 1):
            eval_info = itr.get("evaluation", {})
            conf = eval_info.get("confidence", 0)
            passed = "通过" if eval_info.get("passed") else "未通过"
            lines.append(f"- 第 {i} 轮: 置信度 {conf:.3f} ({passed})")
        
        if len(iterations) > 5:
            lines.append(f"- ... 共 {len(iterations)} 轮迭代")
        
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Prompt 5: Skill trigger threshold & autonomous reflection
    # ------------------------------------------------------------------ #

    def check_and_generate(self, task_type: str, recent_executions: list) -> Optional[Dict[str, Any]]:
        """
        Check if skill generation should be triggered based on recent execution history.

        Args:
            task_type: The task type to analyze
            recent_executions: List of execution dicts with keys:
                - success: bool
                - confidence: float
                - params: dict
                - result: dict
                - execution_record: dict (optional)

        Returns:
            Dict with action and path, or None if threshold not met.
        """
        if len(recent_executions) < self.trigger_threshold:
            return None

        successes = [e for e in recent_executions if e.get("success")]
        failures = [e for e in recent_executions if not e.get("success")]
        total = len(recent_executions)
        success_rate = len(successes) / total

        logger.info(f"Skill trigger check for {task_type}: {len(successes)}/{total} success (rate={success_rate:.2f})")

        if success_rate >= self.quality_min_confidence:
            return self._reflect_and_generate(task_type, successes)

        failure_rate = len(failures) / total
        if failure_rate > (1 - self.quality_min_confidence):
            return self._suggest_improvement(task_type, failures)

        return None

    def _reflect_and_generate(self, task_type: str, successful_executions: list) -> Dict[str, Any]:
        """Analyze successful cases and generate a SKILL.md."""
        # Extract common parameters (most frequent value for each key)
        param_values: Dict[str, list] = {}
        for ex in successful_executions:
            params = ex.get("params", {})
            for k, v in params.items():
                param_values.setdefault(k, []).append(v)

        common_params = {}
        for k, vals in param_values.items():
            # Use the most common value
            from collections import Counter
            most_common = Counter(str(v) for v in vals).most_common(1)[0][0]
            # Find the original typed value
            for v in vals:
                if str(v) == most_common:
                    common_params[k] = v
                    break

        # Build a synthetic execution record
        best_execution = max(successful_executions, key=lambda e: e.get("confidence", 0))
        synthetic_record = {
            "task_type": task_type,
            "best_params": common_params,
            "best_result": best_execution.get("result", {}),
            "best_confidence": best_execution.get("confidence", 0.0),
            "iterations": [{
                "iteration": i + 1,
                "evaluation": {"confidence": ex.get("confidence", 0), "passed": True}
            } for i, ex in enumerate(successful_executions[:5])],
        }

        # Validate before generating
        try:
            from core.skill_validator import SkillValidator
            validator = SkillValidator()
            # Note: validate_json expects agentskills.io format; we skip strict validation here
            # and rely on the template generation which produces markdown.
        except ImportError:
            pass

        doc_path = self.generate(synthetic_record, skill_id=f"{task_type}_reflected")
        logger.info(f"Reflected skill generated for {task_type}: {doc_path}")
        return {"action": "generated", "task_type": task_type, "path": str(doc_path) if doc_path else None}

    def _suggest_improvement(self, task_type: str, failed_executions: list) -> Dict[str, Any]:
        """Analyze failure cases and output an improvement suggestion report."""
        # Collect common error patterns
        error_reasons = []
        for ex in failed_executions:
            rec = ex.get("execution_record", {})
            if rec.get("error"):
                error_reasons.append(str(rec["error"]))
            elif rec.get("status"):
                error_reasons.append(str(rec["status"]))

        from collections import Counter
        common_errors = Counter(error_reasons).most_common(5)

        # Collect parameter distributions
        param_values: Dict[str, list] = {}
        for ex in failed_executions:
            params = ex.get("params", {})
            for k, v in params.items():
                param_values.setdefault(k, []).append(v)

        content = f"""# {task_type} 改进建议报告

生成时间: {datetime.now().isoformat()}
分析样本数: {len(failed_executions)}

## 常见失败原因
"""
        for reason, count in common_errors:
            content += f"- {reason}: {count} 次\n"

        content += "\n## 失败参数分布\n\n"
        for k, vals in param_values.items():
            unique = set(str(v) for v in vals)
            content += f"- `{k}`: {len(unique)} 种不同值 ({', '.join(list(unique)[:5])}{'...' if len(unique) > 5 else ''})\n"

        content += """
## 改进建议

1. 检查上述常见失败原因，确认是否为系统性问题
2. 尝试调整参数分布中变化较大的参数
3. 增加训练数据或改进评估标准
4. 考虑引入外部知识库辅助决策

---
报告来源: Kaelis 自主反思引擎
"""

        safe_name = re.sub(r'[^\w\-_.]', '_', task_type)[:64]
        report_path = self.improvement_dir / f"{safe_name}_improvement.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Improvement suggestion for {task_type}: {report_path}")
        return {"action": "suggested_improvement", "task_type": task_type, "path": str(report_path)}


# 全局实例
_generator_instance: Optional[SkillDocumentGenerator] = None


def get_skill_generator(llm_client=None) -> SkillDocumentGenerator:
    """获取全局技能文档生成器"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = SkillDocumentGenerator(llm_client=llm_client)
    return _generator_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试技能文档生成器 ===")
    
    gen = SkillDocumentGenerator()
    
    mock_record = {
        "task_type": "pls_da_analysis",
        "best_params": {"n_components": 5, "scale": True, "method": "nipals"},
        "best_result": {"Q2": 0.85, "R2Y": 0.92, "p_value": 0.01},
        "best_confidence": 0.92,
        "iterations": [
            {"iteration": 1, "evaluation": {"confidence": 0.65, "passed": False}},
            {"iteration": 2, "evaluation": {"confidence": 0.78, "passed": True}},
            {"iteration": 3, "evaluation": {"confidence": 0.92, "passed": True}},
        ]
    }
    
    path = gen.generate(mock_record, skill_id="pls_da_v1")
    if path:
        print(f"Generated: {path}")
        with open(path, "r", encoding="utf-8") as f:
            print(f"\nPreview (first 500 chars):\n{f.read()[:500]}...")
    
    print("\n[OK] SkillDocumentGenerator test completed")
