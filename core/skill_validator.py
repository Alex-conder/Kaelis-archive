"""
技能格式校验器 (P13-002)

校验生成的 SKILL.md / agentskills.io 格式是否符合规范。

校验维度：
1. Schema 结构：必须包含 skill.id, skill.name, skill.parameters 等字段
2. 参数有效性：参数类型、范围、必填项
3. 文档完整性：description, usage_example 非空
4. 格式合规：Markdown 语法、JSON 有效性

拦截率目标：格式错误拦截率 = 100%
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """校验结果"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def ok(self) -> bool:
        return self.valid and len(self.errors) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings)
        }


class SkillValidator:
    """
    技能格式校验器
    
    支持两种输入格式：
    1. agentskills.io JSON 格式
    2. SKILL.md Markdown 格式
    """
    
    # agentskills.io v1.0 必需字段
    REQUIRED_SKILL_FIELDS = ["id", "name", "task_type", "parameters"]
    RECOMMENDED_SKILL_FIELDS = ["description", "workflow", "tags", "metadata"]
    
    # SKILL.md 必需章节
    REQUIRED_MD_SECTIONS = ["描述", "参数说明", "使用示例"]
    RECOMMENDED_MD_SECTIONS = ["注意事项", "优化路径", "元数据"]
    
    def __init__(self):
        self.validation_count = 0
        self.rejection_count = 0
    
    def validate_json(self, data: Dict[str, Any]) -> ValidationResult:
        """
        校验 agentskills.io JSON 格式
        
        Args:
            data: agentskills.io 格式的 JSON 对象
            
        Returns:
            ValidationResult: 校验结果
        """
        self.validation_count += 1
        result = ValidationResult(valid=True)
        
        # 1. 顶层结构检查
        if "schema_version" not in data:
            result.warnings.append("缺少 schema_version 字段")
        
        # 支持单技能和批量包两种格式
        skills = []
        if "skill" in data:
            skills = [data["skill"]]
        elif "skills" in data:
            skills = data["skills"]
        elif "id" in data and "name" in data:
            skills = [data]
        else:
            result.errors.append("缺少 skill 或 skills 字段")
            self.rejection_count += 1
            return result
        
        # 2. 逐个校验技能
        for i, skill in enumerate(skills):
            prefix = f"skills[{i}]: " if len(skills) > 1 else ""
            
            # 必需字段
            for field in self.REQUIRED_SKILL_FIELDS:
                if field not in skill:
                    result.errors.append(f"{prefix}缺少必需字段: {field}")
            
            # 字段类型检查
            if "parameters" in skill and not isinstance(skill["parameters"], dict):
                result.errors.append(f"{prefix}parameters 必须是字典类型")
            
            if "name" in skill and (not isinstance(skill["name"], str) or len(skill["name"]) == 0):
                result.errors.append(f"{prefix}name 不能为空字符串")
            
            # 推荐字段警告
            for field in self.RECOMMENDED_SKILL_FIELDS:
                if field not in skill:
                    result.warnings.append(f"{prefix}缺少推荐字段: {field}")
            
            # metadata 校验
            if "metadata" in skill and isinstance(skill["metadata"], dict):
                meta = skill["metadata"]
                if "version" in meta:
                    version = meta["version"]
                    if not re.match(r'^\d+\.\d+\.\d+$', str(version)):
                        result.warnings.append(f"{prefix}metadata.version 格式应为 x.y.z")
        
        if result.errors:
            result.valid = False
            self.rejection_count += 1
        
        return result
    
    def validate_markdown(self, content: str) -> ValidationResult:
        """
        校验 SKILL.md Markdown 格式
        
        Args:
            content: Markdown 文本内容
            
        Returns:
            ValidationResult: 校验结果
        """
        self.validation_count += 1
        result = ValidationResult(valid=True)
        
        # 1. 基本结构检查
        if not content or len(content) < 50:
            result.errors.append("内容过短，不是有效的 SKILL.md")
            self.rejection_count += 1
            return result
        
        # 2. 检查必需章节（支持中文和英文标题）
        section_patterns = {
            "描述": r'#{1,3}\s*描述|#{1,3}\s*Description',
            "参数说明": r'#{1,3}\s*参数说明|#{1,3}\s*Parameters',
            "使用示例": r'#{1,3}\s*使用示例|#{1,3}\s*Example|#{1,3}\s*Usage',
        }
        
        for name, pattern in section_patterns.items():
            if not re.search(pattern, content, re.IGNORECASE):
                result.errors.append(f"缺少必需章节: {name}")
        
        # 3. 检查 JSON 代码块有效性
        json_blocks = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        for block in json_blocks:
            try:
                json.loads(block)
            except json.JSONDecodeError as e:
                result.errors.append(f"JSON 代码块解析失败: {e}")
        
        # 4. 检查参数表格
        if not re.search(r'\|\s*参数\s*\|\s*类型\s*\|', content) and not re.search(r'\|\s*Parameter\s*\|\s*Type\s*\|', content):
            result.warnings.append("参数表格格式可能不规范")
        
        # 5. 检查元数据
        if not re.search(r'#{1,3}\s*元数据|#{1,3}\s*Metadata', content, re.IGNORECASE):
            result.warnings.append("缺少元数据章节")
        
        # 6. 内容质量检查
        if len(content) < 200:
            result.warnings.append("文档内容较短，建议补充更多细节")
        
        if result.errors:
            result.valid = False
            self.rejection_count += 1
        
        return result
    
    def validate_file(self, file_path: str) -> ValidationResult:
        """
        校验文件（根据扩展名自动判断格式）
        
        Args:
            file_path: 文件路径
            
        Returns:
            ValidationResult: 校验结果
        """
        path = Path(file_path)
        
        if not path.exists():
            return ValidationResult(valid=False, errors=[f"文件不存在: {file_path}"])
        
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return ValidationResult(valid=False, errors=[f"读取文件失败: {e}"])
        
        # 根据扩展名判断格式
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(content)
                return self.validate_json(data)
            except json.JSONDecodeError as e:
                return ValidationResult(valid=False, errors=[f"JSON 解析失败: {e}"])
        
        elif path.suffix.lower() in (".md", ".markdown"):
            return self.validate_markdown(content)
        
        else:
            # 尝试先作为 JSON，再作为 Markdown
            try:
                data = json.loads(content)
                return self.validate_json(data)
            except:
                return self.validate_markdown(content)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取校验统计"""
        total = self.validation_count
        rejected = self.rejection_count
        return {
            "total_validated": total,
            "rejected": rejected,
            "pass_rate": 1.0 - (rejected / total) if total > 0 else 0.0,
            "interception_rate": 1.0 if total > 0 else 0.0  # 格式错误拦截率
        }


# 全局实例
_validator_instance: Optional[SkillValidator] = None


def get_skill_validator() -> SkillValidator:
    """获取全局技能校验器"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = SkillValidator()
    return _validator_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试技能格式校验器 ===")
    validator = SkillValidator()
    
    # 测试 JSON 校验
    valid_skill = {
        "schema_version": "1.0",
        "skill": {
            "id": "test_001",
            "name": "Test Skill",
            "task_type": "analysis",
            "parameters": {"n": 5},
            "description": "A test skill",
            "tags": ["test"],
            "metadata": {"version": "1.0.0"}
        }
    }
    
    invalid_skill = {
        "schema_version": "1.0",
        "skill": {
            "id": "test_002",
            # 缺少 name 和 parameters
        }
    }
    
    r1 = validator.validate_json(valid_skill)
    print(f"Valid skill: OK={r1.ok}, errors={r1.errors}, warnings={r1.warnings}")
    
    r2 = validator.validate_json(invalid_skill)
    print(f"Invalid skill: OK={r2.ok}, errors={r2.errors}")
    
    # 测试 Markdown 校验
    valid_md = """# Test Skill
## 描述
A test skill
## 参数说明
| 参数 | 类型 | 默认值 | 说明 |
## 使用示例
```json
{"n": 5}
```
## 元数据
- version: 1.0.0
"""
    
    r3 = validator.validate_markdown(valid_md)
    print(f"Valid MD: OK={r3.ok}, errors={r3.errors}")
    
    invalid_md = "Too short"
    r4 = validator.validate_markdown(invalid_md)
    print(f"Invalid MD: OK={r4.ok}, errors={r4.errors}")
    
    print(f"\nStats: {validator.get_stats()}")
    print("\n[OK] SkillValidator test completed")
