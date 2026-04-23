"""
RL 轨迹导出器 (P15-001)

将自进化引擎的评估历史导出为强化学习轨迹格式：
    (state, action, reward, next_state, done)

输出格式：JSONL (每行一个 JSON 对象)
存储路径：data/rl_trajectories/

集成点：
- SelfEvolvingEngine: 每次迭代后自动追加轨迹
- RLOptimizer: 读取轨迹进行策略优化
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RLTrajectoryExporter:
    """
    RL 轨迹导出器
    
    将评估记录转换为 RL 标准轨迹格式，支持：
    - 实时追加（低延迟）
    - 批量导出（历史数据迁移）
    - 按任务类型分文件存储
    """
    
    def __init__(self, output_dir: str = "data/rl_trajectories"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def append_trajectory(
        self,
        execution_id: str,
        task_type: str,
        iteration: int,
        state: Dict[str, Any],
        action: Dict[str, Any],
        reward: float,
        next_state: Dict[str, Any],
        done: bool = False,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        追加单条轨迹到 JSONL 文件
        
        Args:
            execution_id: 执行ID
            task_type: 任务类型（用于分文件）
            iteration: 迭代序号
            state: 当前状态（参数 + 上下文）
            action: 执行的动作（策略选择）
            reward: 奖励值（通常 = evaluation.confidence）
            next_state: 执行后的状态
            done: 是否结束
            metadata: 额外元数据
            
        Returns:
            bool: 是否成功写入
        """
        trajectory = {
            "timestamp": datetime.now().isoformat(),
            "execution_id": execution_id,
            "task_type": task_type,
            "iteration": iteration,
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state,
            "done": done,
            "metadata": metadata or {}
        }
        
        # 按任务类型分文件，按日期滚动
        date_str = datetime.now().strftime("%Y%m%d")
        safe_task = "".join(c if c.isalnum() or c in "_-" else "_" for c in task_type)[:32]
        file_path = self.output_dir / f"{safe_task}_{date_str}.jsonl"
        
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trajectory, ensure_ascii=False) + "\n")
            return True
        except Exception as e:
            logger.error(f"Failed to append trajectory: {e}")
            return False
    
    def export_from_execution_record(
        self,
        record: Dict[str, Any]
    ) -> int:
        """
        从 ExecutionRecord 导出完整轨迹
        
        Args:
            record: 执行记录字典
            
        Returns:
            int: 导出的轨迹数量
        """
        execution_id = record.get("execution_id", "unknown")
        task_type = record.get("task_type", "unknown")
        iterations = record.get("iterations", [])
        
        count = 0
        for i, itr in enumerate(iterations):
            params = itr.get("params", {})
            eval_info = itr.get("evaluation", {})
            reward = eval_info.get("confidence", 0.0)
            
            # 构建状态（当前参数 + 评估历史）
            state = {
                "params": params,
                "iteration": i + 1,
                "history_confidences": [
                    it.get("evaluation", {}).get("confidence", 0)
                    for it in iterations[:i]
                ]
            }
            
            # 动作（策略改进）
            # 如果有多轮迭代，action 是参数的变化量
            action = {"param_delta": {}}
            if i > 0:
                prev_params = iterations[i - 1].get("params", {})
                for k, v in params.items():
                    pv = prev_params.get(k)
                    if pv != v:
                        action["param_delta"][k] = {"from": pv, "to": v}
            
            # 下一状态（下一轮参数，如果是最后一轮则保持当前）
            if i + 1 < len(iterations):
                next_state = {
                    "params": iterations[i + 1].get("params", {}),
                    "iteration": i + 2
                }
            else:
                next_state = state
            
            done = (i == len(iterations) - 1) or eval_info.get("passed", False)
            
            ok = self.append_trajectory(
                execution_id=execution_id,
                task_type=task_type,
                iteration=i + 1,
                state=state,
                action=action,
                reward=reward,
                next_state=next_state,
                done=done,
                metadata={
                    "evaluation_method": record.get("evaluation_method", "unknown"),
                    "target_confidence": record.get("target_confidence", 0.8)
                }
            )
            if ok:
                count += 1
        
        logger.info(f"Exported {count}/{len(iterations)} trajectories for {execution_id}")
        return count
    
    def read_trajectories(
        self,
        task_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        读取轨迹数据（供 RLOptimizer 使用）
        
        Args:
            task_type: 任务类型过滤（None 表示全部）
            limit: 返回数量上限
            
        Returns:
            List[Dict]: 轨迹列表
        """
        results = []
        
        pattern = f"{task_type or '*'}_*.jsonl"
        files = sorted(self.output_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        results.append(json.loads(line))
                        if len(results) >= limit:
                            return results
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取轨迹存储统计"""
        files = list(self.output_dir.glob("*.jsonl"))
        total_lines = 0
        task_types = set()
        
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    lines = sum(1 for _ in file)
                    total_lines += lines
                    # 从文件名提取 task_type
                    parts = f.stem.split("_")
                    if len(parts) >= 2:
                        task_types.add("_".join(parts[:-1]))
            except Exception as e:
                logger.warning(f"Failed to count {f}: {e}")
        
        return {
            "total_trajectories": total_lines,
            "file_count": len(files),
            "task_types": sorted(task_types),
            "output_dir": str(self.output_dir)
        }


# 全局实例
_exporter_instance: Optional[RLTrajectoryExporter] = None


def get_rl_exporter() -> RLTrajectoryExporter:
    """获取全局轨迹导出器"""
    global _exporter_instance
    if _exporter_instance is None:
        _exporter_instance = RLTrajectoryExporter()
    return _exporter_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试 RL 轨迹导出器 ===")
    
    exporter = RLTrajectoryExporter()
    
    # 模拟轨迹
    ok = exporter.append_trajectory(
        execution_id="test_001",
        task_type="pls_da",
        iteration=1,
        state={"params": {"n_components": 2}, "iteration": 1},
        action={"param_delta": {"n_components": {"from": 2, "to": 3}}},
        reward=0.65,
        next_state={"params": {"n_components": 3}, "iteration": 2},
        done=False
    )
    print(f"Append trajectory: {'OK' if ok else 'NG'}")
    
    # 从记录导出
    mock_record = {
        "execution_id": "test_002",
        "task_type": "pls_da",
        "iterations": [
            {"params": {"n": 1}, "evaluation": {"confidence": 0.5}},
            {"params": {"n": 2}, "evaluation": {"confidence": 0.7}},
            {"params": {"n": 3}, "evaluation": {"confidence": 0.9}},
        ]
    }
    count = exporter.export_from_execution_record(mock_record)
    print(f"Exported from record: {count} trajectories")
    
    # 读取
    traj = exporter.read_trajectories(task_type="pls_da", limit=5)
    print(f"Read back: {len(traj)} trajectories")
    
    # 统计
    stats = exporter.get_stats()
    print(f"Stats: {stats}")
    
    print("\n[OK] RLTrajectoryExporter test completed")
