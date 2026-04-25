"""
Kaelis Workflow Nodes - 可复用的工作流节点执行库

每个节点是一个独立的执行单元，支持：
- 标准化输入/输出接口
- 配置参数验证
- 错误降级处理
- 执行时间追踪
"""

from typing import Any, Dict, List, Optional


class WorkflowNodeError(Exception):
    """工作流节点执行错误"""
    pass


class NodeExecutor:
    """节点执行器基类"""
    
    node_id: str = ""
    name: str = ""
    description: str = ""
    
    def execute(self, inputs: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行节点逻辑，子类必须实现"""
        raise NotImplementedError
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> List[str]:
        """验证输入参数，返回错误列表"""
        return []
