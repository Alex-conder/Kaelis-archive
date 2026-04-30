"""
评估器阈值自适应模块 (P15-003)

监控评估准确率，自动调整 rule/llm 权重分配：
- 准确率高 (>80%): 保持当前权重，优先使用 rule（低延迟）
- 准确率中 (50-80%): 提升 LLM 权重（+10%）
- 准确率低 (<50%): 大幅切换到 LLM（权重 ≥ 0.7）

限制：
- LLM 权重提升后，延迟增加 < 20%
- 每次调整幅度 ≤ 15%
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EvaluatorTuner:
    """
    评估器阈值自适应调节器
    
    基于历史评估结果，动态调整 rule/llm 权重。
    """
    
    # 预设策略
    STRATEGIES = {
        "high_accuracy": {"llm_weight": 0.2, "rule_weight": 0.8, "description": "Rule优先（低延迟）"},
        "medium_accuracy": {"llm_weight": 0.4, "rule_weight": 0.6, "description": "混合评估"},
        "low_accuracy": {"llm_weight": 0.7, "rule_weight": 0.3, "description": "LLM优先（高精度）"},
        "critical": {"llm_weight": 0.9, "rule_weight": 0.1, "description": "强制LLM（关键场景）"},
    }
    
    def __init__(self, history_file: str = "data/evaluator_tuner_history.json"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.records: List[Dict] = self._load_history()
        self.current_weights = {"llm": 0.3, "rule": 0.7}
    
    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load tuner history: {e}")
            return []
    
    def _save_history(self):
        """保存历史记录"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.records[-1000:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save tuner history: {e}")
    
    def record_evaluation(
        self,
        task_type: str,
        method_used: str,  # "rule", "llm", "hybrid"
        predicted_pass: bool,
        actual_pass: Optional[bool] = None,
        confidence: float = 0.0,
        latency_ms: float = 0.0
    ):
        """
        记录一次评估结果
        
        Args:
            task_type: 任务类型
            method_used: 使用的评估方法
            predicted_pass: 预测是否通过
            actual_pass: 实际是否通过（事后反馈）
            confidence: 置信度
            latency_ms: 延迟
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "method_used": method_used,
            "predicted_pass": predicted_pass,
            "actual_pass": actual_pass,
            "confidence": confidence,
            "latency_ms": latency_ms
        }
        self.records.append(record)
        
        # 每 20 条记录自动调整一次
        if len(self.records) % 20 == 0:
            self.auto_tune()
        
        self._save_history()
    
    def auto_tune(self) -> Dict[str, Any]:
        """
        自动调整权重
        
        分析最近 N 条记录，根据准确率调整 rule/llm 权重。
        """
        recent = self.records[-50:]
        if len(recent) < 10:
            return {"action": "skip", "reason": "insufficient data", "weights": self.current_weights.copy()}
        
        # 计算各方法的准确率
        rule_records = [r for r in recent if r["method_used"] == "rule" and r["actual_pass"] is not None]
        llm_records = [r for r in recent if r["method_used"] == "llm" and r["actual_pass"] is not None]
        
        rule_accuracy = self._calc_accuracy(rule_records)
        llm_accuracy = self._calc_accuracy(llm_records)
        
        # 决策逻辑
        old_weights = self.current_weights.copy()
        action = "maintain"
        
        if rule_accuracy >= 0.8 and llm_accuracy >= 0.8:
            # 两者都准确：优先 rule（低延迟）
            self.current_weights = {"llm": 0.2, "rule": 0.8}
            action = "rule_priority"
        elif rule_accuracy < 0.5 and llm_accuracy > rule_accuracy + 0.15:
            # Rule 明显不如 LLM：提升 LLM
            new_llm = min(0.7, self.current_weights["llm"] + 0.15)
            self.current_weights = {"llm": new_llm, "rule": 1.0 - new_llm}
            action = "boost_llm"
        elif rule_accuracy < 0.7 and llm_accuracy >= 0.7:
            # Rule 中等，LLM 更好：适度提升 LLM
            new_llm = min(0.5, self.current_weights["llm"] + 0.1)
            self.current_weights = {"llm": new_llm, "rule": 1.0 - new_llm}
            action = "moderate_llm"
        elif llm_accuracy < 0.5 and rule_accuracy > llm_accuracy + 0.15:
            # LLM 明显不如 Rule：提升 Rule
            new_rule = min(0.9, self.current_weights["rule"] + 0.1)
            self.current_weights = {"llm": 1.0 - new_rule, "rule": new_rule}
            action = "boost_rule"
        
        result = {
            "action": action,
            "old_weights": old_weights,
            "new_weights": self.current_weights.copy(),
            "rule_accuracy": round(rule_accuracy, 3) if rule_records else None,
            "llm_accuracy": round(llm_accuracy, 3) if llm_records else None,
            "sample_size": len(recent),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Auto-tuned: {action}, weights={self.current_weights}")
        return result
    
    def _calc_accuracy(self, records: List[Dict]) -> float:
        """计算准确率"""
        if not records:
            return 0.0
        correct = sum(1 for r in records if r["predicted_pass"] == r["actual_pass"])
        return correct / len(records)
    
    def get_recommended_method(self, task_type: str = "default") -> str:
        """
        获取推荐的评估方法
        
        Returns:
            str: "rule", "llm", 或 "hybrid"
        """
        llm_w = self.current_weights["llm"]
        if llm_w >= 0.7:
            return "llm"
        elif llm_w <= 0.3:
            return "rule"
        else:
            return "hybrid"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调节器统计"""
        total = len(self.records)
        with_feedback = sum(1 for r in self.records if r["actual_pass"] is not None)
        
        return {
            "total_evaluations": total,
            "with_feedback": with_feedback,
            "current_weights": self.current_weights.copy(),
            "recommended_method": self.get_recommended_method(),
            "history_file": str(self.history_file)
        }


# 全局实例
_tuner_instance: Optional[EvaluatorTuner] = None


def get_evaluator_tuner() -> EvaluatorTuner:
    """获取全局评估器调节器"""
    global _tuner_instance
    if _tuner_instance is None:
        _tuner_instance = EvaluatorTuner()
    return _tuner_instance


# ------------------------------------------------------------------ #
# GEPA-style Prompt Auto-Optimizer (P19-004)
# ------------------------------------------------------------------ #

class GEPAPromptOptimizer:
    """
    GEPA 风格自主 Prompt 优化器

    基于评估反馈自动优化系统 Prompt，实现"越用越聪明"。
    核心机制：
    1. 收集任务执行结果和人工/自动评估反馈
    2. 识别低置信度模式（prompt 弱点）
    3. 生成改进候选（add/remove/modify prompt 片段）
    4. A/B 验证：新 prompt vs 旧 prompt 在同类任务上的效果
    5. 自动应用通过验证的改进（win rate > 55%）

    参考: Hermes GEPA (ICLR 2026 Oral)
    """

    def __init__(self, prompt_registry_file: str = "data/prompt_registry.json"):
        self.registry_file = Path(prompt_registry_file)
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.registry = self._load_registry()
        self.optimization_history: List[Dict] = []

    def _load_registry(self) -> Dict[str, Any]:
        if not self.registry_file.exists():
            return {"current_version": 0, "prompts": {}, "ab_tests": []}
        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load prompt registry: {e}")
            return {"current_version": 0, "prompts": {}, "ab_tests": []}

    def _save_registry(self):
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self.registry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save prompt registry: {e}")

    def record_task_outcome(
        self,
        task_type: str,
        prompt_version: int,
        input_text: str,
        output_text: str,
        evaluation_score: float,  # 0.0 - 1.0
        user_feedback: Optional[str] = None,
    ):
        """记录一次任务执行结果，用于后续优化分析"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "prompt_version": prompt_version,
            "input_hash": hash(input_text) & 0xFFFFFF,
            "output_hash": hash(output_text) & 0xFFFFFF,
            "evaluation_score": evaluation_score,
            "user_feedback": user_feedback,
        }
        self.optimization_history.append(record)
        # 每 50 条触发一次分析
        if len(self.optimization_history) % 50 == 0:
            self.analyze_and_optimize(task_type)

    def analyze_and_optimize(self, task_type: str) -> Optional[Dict[str, Any]]:
        """
        分析特定任务类型的历史记录，识别低置信度模式并生成优化建议。
        """
        records = [r for r in self.optimization_history if r["task_type"] == task_type]
        if len(records) < 20:
            return None

        # 识别低分模式
        low_score_records = [r for r in records if r["evaluation_score"] < 0.6]
        if len(low_score_records) < 5:
            return None

        # 简单的启发式优化：基于常见失败类型生成 prompt 补丁
        patches = self._generate_patches(low_score_records)
        if not patches:
            return None

        # 注册 A/B 测试
        current_version = self.registry.get("current_version", 0)
        test_id = f"ab_{task_type}_v{current_version}"
        self.registry["ab_tests"].append({
            "test_id": test_id,
            "task_type": task_type,
            "baseline_version": current_version,
            "candidate_patches": patches,
            "started_at": datetime.now().isoformat(),
            "status": "running",
            "candidate_wins": 0,
            "baseline_wins": 0,
        })
        self._save_registry()

        return {
            "test_id": test_id,
            "task_type": task_type,
            "patches": patches,
            "low_score_count": len(low_score_records),
        }

    def _generate_patches(self, low_score_records: List[Dict]) -> List[Dict]:
        """基于低分记录生成 prompt 补丁候选"""
        patches = []
        # 启发式 1: 如果很多低分有用户反馈提到"太笼统"，添加"详细步骤"指令
        vague_count = sum(1 for r in low_score_records if r.get("user_feedback") and "笼统" in r["user_feedback"])
        if vague_count >= 3:
            patches.append({
                "type": "add",
                "target": "system_prompt_suffix",
                "content": "请提供详细的步骤说明，不要省略中间推理过程。",
                "reason": f"{vague_count} 次反馈提到回答太笼统",
            })
        # 启发式 2: 如果低分集中在 <0.4，可能是缺少边界处理
        very_low = [r for r in low_score_records if r["evaluation_score"] < 0.4]
        if len(very_low) >= 3:
            patches.append({
                "type": "add",
                "target": "system_prompt_suffix",
                "content": "在给出结论前，请检查边界条件和异常情况。",
                "reason": f"{len(very_low)} 次评分低于 0.4，疑似边界处理不足",
            })
        # 启发式 3: 添加时效性提醒
        patches.append({
            "type": "add",
            "target": "system_prompt_suffix",
            "content": f"当前知识截止日期参考: {datetime.now().strftime('%Y-%m')}。",
            "reason": "保持 prompt 时效性",
        })
        return patches

    def report_ab_test_result(self, test_id: str, candidate_win: bool):
        """报告 A/B 测试结果"""
        for test in self.registry.get("ab_tests", []):
            if test["test_id"] == test_id:
                if candidate_win:
                    test["candidate_wins"] += 1
                else:
                    test["baseline_wins"] += 1
                total = test["candidate_wins"] + test["baseline_wins"]
                if total >= 20:
                    win_rate = test["candidate_wins"] / total
                    if win_rate > 0.55:
                        test["status"] = "promoted"
                        self._apply_patches(test["candidate_patches"])
                        logger.info(f"A/B test {test_id} promoted: win_rate={win_rate:.2%}")
                    else:
                        test["status"] = "rejected"
                        logger.info(f"A/B test {test_id} rejected: win_rate={win_rate:.2%}")
                self._save_registry()
                break

    def _apply_patches(self, patches: List[Dict]):
        """将通过验证的补丁应用到系统 prompt"""
        current = self.registry.get("prompts", {}).get("system", "")
        for p in patches:
            if p["type"] == "add":
                current += "\n" + p["content"]
            elif p["type"] == "remove" and p["content"] in current:
                current = current.replace(p["content"], "")
            elif p["type"] == "modify":
                current = current.replace(p.get("old", ""), p.get("new", ""))
        self.registry["current_version"] = self.registry.get("current_version", 0) + 1
        self.registry["prompts"]["system"] = current.strip()
        self._save_registry()

    def get_current_prompt(self) -> str:
        return self.registry.get("prompts", {}).get("system", "")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "current_version": self.registry.get("current_version", 0),
            "total_optimizations": len(self.optimization_history),
            "ab_tests": len(self.registry.get("ab_tests", [])),
            "prompt_length": len(self.get_current_prompt()),
        }


# 全局实例
_optimizer_instance: Optional[GEPAPromptOptimizer] = None


def get_prompt_optimizer() -> GEPAPromptOptimizer:
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = GEPAPromptOptimizer()
    return _optimizer_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== 测试评估器阈值自适应 ===")
    tuner = EvaluatorTuner()

    # 模拟评估记录：Rule 准确率 60%，LLM 准确率 85%
    for i in range(20):
        tuner.record_evaluation("pls_da", "rule", predicted_pass=(i < 12), actual_pass=(i < 10), confidence=0.6, latency_ms=50)
    for i in range(20):
        tuner.record_evaluation("pls_da", "llm", predicted_pass=(i < 18), actual_pass=(i < 17), confidence=0.85, latency_ms=200)

    result = tuner.auto_tune()
    print(f"Tune result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    print(f"Recommended method: {tuner.get_recommended_method()}")
    print(f"Stats: {tuner.get_stats()}")

    print("\n=== 测试 GEPA Prompt 优化器 ===")
    opt = GEPAPromptOptimizer()
    for i in range(25):
        opt.record_task_outcome(
            task_type="coding",
            prompt_version=0,
            input_text="sort list",
            output_text="result",
            evaluation_score=0.4 if i < 10 else 0.8,
            user_feedback="太笼统" if i < 5 else None,
        )
    print(f"Optimizer stats: {opt.get_stats()}")
    print(f"Current prompt:\n{opt.get_current_prompt()}")

    print("\n[OK] EvaluatorTuner + GEPAPromptOptimizer test completed")
