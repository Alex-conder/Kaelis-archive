"""
技能 Patch 工具 (P13-003)

检测技能过时/不匹配，自动生成并应用 patch：
1. 检测技能与当前系统版本的兼容性
2. 对比参数 Schema 差异
3. 使用 LLM 生成 patch（参数映射、新增字段处理）
4. 应用 patch 并验证

成功率目标: > 80%
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PatchResult:
    """Patch 执行结果"""
    success: bool
    skill_id: str
    patch_version: str
    changes: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    backup_path: Optional[str] = None


class SkillPatcher:
    """
    技能 Patch 生成器与应用器
    
    支持以下 patch 类型：
    - rename: 参数重命名
    - add_default: 新增必填参数补充默认值
    - remove: 删除废弃参数
    - transform: 参数值转换
    - schema_upgrade: 整体 schema 升级
    """
    
    def __init__(self, llm_client=None, backup_dir: str = "data/skills/backups"):
        self.llm_client = llm_client
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.patch_count = 0
        self.success_count = 0
    
    def detect_incompatibility(
        self,
        skill: Dict[str, Any],
        current_schema: Dict[str, Any]
    ) -> List[Dict]:
        """
        检测技能与当前 schema 的不兼容之处
        
        Args:
            skill: 技能数据
            current_schema: 当前系统期望的 schema
            
        Returns:
            List[Dict]: 不兼容项列表
        """
        issues = []
        skill_params = skill.get("parameters", {})
        expected_params = current_schema.get("required_params", [])
        param_types = current_schema.get("param_types", {})
        
        # 1. 检查缺少的必填参数
        for param in expected_params:
            if param not in skill_params:
                issues.append({
                    "type": "missing_required",
                    "param": param,
                    "severity": "high",
                    "message": f"缺少必填参数: {param}"
                })
        
        # 2. 检查类型不匹配
        for param, value in skill_params.items():
            if param in param_types:
                expected_type = param_types[param]
                actual_type = type(value).__name__
                if expected_type != actual_type and not self._type_compatible(expected_type, actual_type):
                    issues.append({
                        "type": "type_mismatch",
                        "param": param,
                        "expected": expected_type,
                        "actual": actual_type,
                        "severity": "medium",
                        "message": f"参数 {param} 类型不匹配: 期望 {expected_type}, 实际 {actual_type}"
                    })
        
        # 3. 检查废弃参数
        deprecated = current_schema.get("deprecated_params", [])
        for param in deprecated:
            if param in skill_params:
                issues.append({
                    "type": "deprecated",
                    "param": param,
                    "severity": "low",
                    "message": f"使用了废弃参数: {param}"
                })
        
        # 4. 检查版本兼容性
        skill_version = skill.get("metadata", {}).get("version", "1.0.0")
        min_version = current_schema.get("min_skill_version", "1.0.0")
        if self._version_lt(skill_version, min_version):
            issues.append({
                "type": "version_incompatible",
                "severity": "high",
                "message": f"技能版本 {skill_version} 低于最低要求 {min_version}"
            })
        
        return issues
    
    def generate_patch(
        self,
        skill: Dict[str, Any],
        issues: List[Dict],
        current_schema: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        生成 patch（规则优先，LLM 辅助复杂场景）
        
        Args:
            skill: 原始技能
            issues: 不兼容项列表
            current_schema: 当前 schema
            
        Returns:
            Dict: patch 定义，失败返回 None
        """
        if not issues:
            return None
        
        patch = {
            "skill_id": skill.get("id"),
            "from_version": skill.get("metadata", {}).get("version", "1.0.0"),
            "to_version": current_schema.get("version", "1.0.0"),
            "operations": []
        }
        
        # 规则生成 patch 操作
        for issue in issues:
            op = self._issue_to_operation(issue, current_schema)
            if op:
                patch["operations"].append(op)
        
        # 复杂场景使用 LLM
        if self.llm_client and len([i for i in issues if i["severity"] == "high"]) > 1:
            try:
                llm_patch = self._llm_generate_patch(skill, issues, current_schema)
                if llm_patch:
                    patch["operations"].extend(llm_patch.get("operations", []))
            except Exception as e:
                logger.warning(f"LLM patch generation failed: {e}")
        
        if not patch["operations"]:
            return None
        
        return patch
    
    def apply_patch(
        self,
        skill: Dict[str, Any],
        patch: Dict[str, Any],
        create_backup: bool = True
    ) -> PatchResult:
        """
        应用 patch 到技能
        
        Args:
            skill: 原始技能
            patch: patch 定义
            create_backup: 是否创建备份
            
        Returns:
            PatchResult: 应用结果
        """
        self.patch_count += 1
        skill_id = skill.get("id", "unknown")
        
        # 备份
        backup_path = None
        if create_backup:
            backup_path = self._backup_skill(skill)
        
        patched_skill = json.loads(json.dumps(skill))  # 深拷贝
        changes = []
        errors = []
        
        for op in patch.get("operations", []):
            try:
                result = self._execute_operation(patched_skill, op)
                if result["success"]:
                    changes.append({
                        "op": op["type"],
                        "param": op.get("param"),
                        "old_value": result.get("old"),
                        "new_value": result.get("new")
                    })
                else:
                    errors.append(f"Operation {op['type']} failed: {result.get('error')}")
            except Exception as e:
                errors.append(f"Operation {op['type']} crashed: {e}")
        
        # 更新版本号
        if not errors:
            patched_skill.setdefault("metadata", {})["version"] = patch.get("to_version", "1.0.0")
            patched_skill["metadata"]["patched_at"] = __import__("datetime").datetime.now().isoformat()
        
        success = len(errors) == 0
        if success:
            self.success_count += 1
        
        return PatchResult(
            success=success,
            skill_id=skill_id,
            patch_version=patch.get("to_version", "1.0.0"),
            changes=changes,
            errors=errors,
            backup_path=backup_path
        )
    
    def _issue_to_operation(self, issue: Dict, schema: Dict) -> Optional[Dict]:
        """将不兼容项转换为 patch 操作"""
        issue_type = issue["type"]
        param = issue.get("param")
        
        if issue_type == "missing_required":
            default_value = schema.get("defaults", {}).get(param)
            return {
                "type": "add_default",
                "param": param,
                "value": default_value
            }
        
        elif issue_type == "deprecated":
            return {
                "type": "remove",
                "param": param
            }
        
        elif issue_type == "type_mismatch":
            return {
                "type": "transform",
                "param": param,
                "target_type": issue["expected"]
            }
        
        elif issue_type == "version_incompatible":
            return {
                "type": "schema_upgrade",
                "target_version": schema.get("version", "1.0.0")
            }
        
        return None
    
    def _execute_operation(self, skill: Dict, op: Dict) -> Dict:
        """执行单条 patch 操作"""
        op_type = op["type"]
        params = skill.setdefault("parameters", {})
        
        if op_type == "add_default":
            param = op["param"]
            if param not in params:
                old = params.get(param)
                params[param] = op.get("value")
                return {"success": True, "old": old, "new": params[param]}
            return {"success": True, "old": params[param], "new": params[param]}
        
        elif op_type == "remove":
            param = op["param"]
            old = params.pop(param, None)
            return {"success": True, "old": old, "new": None}
        
        elif op_type == "transform":
            param = op["param"]
            target_type = op["target_type"]
            old = params.get(param)
            
            type_map = {
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "list": list,
                "dict": dict
            }
            
            if target_type in type_map and old is not None:
                try:
                    params[param] = type_map[target_type](old)
                    return {"success": True, "old": old, "new": params[param]}
                except:
                    return {"success": False, "error": f"Cannot convert {old} to {target_type}"}
            return {"success": True, "old": old, "new": old}
        
        elif op_type == "rename":
            old_name = op["param"]
            new_name = op["new_name"]
            if old_name in params:
                params[new_name] = params.pop(old_name)
                return {"success": True, "old": old_name, "new": new_name}
            return {"success": False, "error": f"Param {old_name} not found"}
        
        elif op_type == "schema_upgrade":
            # 仅更新版本标记
            return {"success": True, "old": skill.get("metadata", {}).get("version"), "new": op.get("target_version")}
        
        return {"success": False, "error": f"Unknown operation: {op_type}"}
    
    def _llm_generate_patch(
        self,
        skill: Dict,
        issues: List[Dict],
        schema: Dict
    ) -> Optional[Dict]:
        """使用 LLM 生成复杂 patch"""
        prompt = f"""你是一个技能迁移专家。请根据以下不兼容项，生成 patch 操作列表（JSON 格式）。

技能参数: {json.dumps(skill.get("parameters", {}), ensure_ascii=False)}
不兼容项: {json.dumps(issues, ensure_ascii=False)}
目标 Schema: {json.dumps(schema, ensure_ascii=False)}

请输出以下格式的 JSON：
{{
  "operations": [
    {{"type": "add_default", "param": "xxx", "value": 123}},
    {{"type": "transform", "param": "yyy", "target_type": "float"}},
    {{"type": "rename", "param": "old_name", "new_name": "new_name"}}
  ]
}}

支持的 type: add_default, remove, transform, rename, schema_upgrade
只输出 JSON，不要其他解释："""
        
        response = self.llm_client.chat(prompt, temperature=0.2)
        try:
            return json.loads(str(response))
        except:
            return None
    
    def _backup_skill(self, skill: Dict) -> str:
        """备份技能"""
        skill_id = skill.get("id", "unknown")
        import time
        backup_file = self.backup_dir / f"{skill_id}_{int(time.time())}.json"
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(skill, f, ensure_ascii=False, indent=2)
        return str(backup_file)
    
    def _type_compatible(self, expected: str, actual: str) -> bool:
        """检查类型是否兼容（允许数字互转）"""
        if expected == actual:
            return True
        numeric_types = {"int", "float"}
        return expected in numeric_types and actual in numeric_types
    
    def _version_lt(self, v1: str, v2: str) -> bool:
        """比较版本号 v1 < v2"""
        def parse(v):
            return [int(x) for x in v.split(".")]
        return parse(v1) < parse(v2)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取 patch 统计"""
        return {
            "total_patches": self.patch_count,
            "successful": self.success_count,
            "success_rate": self.success_count / self.patch_count if self.patch_count > 0 else 0.0,
            "backup_dir": str(self.backup_dir)
        }


# 全局实例
_patcher_instance: Optional[SkillPatcher] = None


def get_skill_patcher(llm_client=None) -> SkillPatcher:
    """获取全局技能 patch 工具"""
    global _patcher_instance
    if _patcher_instance is None:
        _patcher_instance = SkillPatcher(llm_client=llm_client)
    return _patcher_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试技能 Patch 工具 ===")
    patcher = SkillPatcher()
    
    old_skill = {
        "id": "test_skill",
        "parameters": {"n_components": 2, "scale": "yes", "old_param": 123},
        "metadata": {"version": "1.0.0"}
    }
    
    current_schema = {
        "version": "2.0.0",
        "required_params": ["n_components", "scale", "new_param"],
        "param_types": {"n_components": "int", "scale": "bool", "new_param": "float"},
        "deprecated_params": ["old_param"],
        "defaults": {"new_param": 0.5}
    }
    
    # 检测不兼容
    issues = patcher.detect_incompatibility(old_skill, current_schema)
    print(f"Detected {len(issues)} issues:")
    for i in issues:
        print(f"  - [{i['severity']}] {i['message']}")
    
    # 生成 patch
    patch = patcher.generate_patch(old_skill, issues, current_schema)
    print(f"\nGenerated patch: {json.dumps(patch, indent=2, ensure_ascii=False)}")
    
    # 应用 patch
    result = patcher.apply_patch(old_skill, patch)
    print(f"\nPatch result: success={result.success}, changes={len(result.changes)}, errors={result.errors}")
    
    print(f"\nStats: {patcher.get_stats()}")
    print("\n[OK] SkillPatcher test completed")
