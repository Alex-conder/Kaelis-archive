"""
agentskills.io 双向同步脚本 (P16-001)

功能：
1. 导出本地技能到 agentskills.io 格式（批量/增量）
2. 从 agentskills.io 导入技能到本地
3. 同步冲突检测与解决（本地优先/远程优先/合并）
4. 生成同步报告

使用方式：
    python scripts/sync_agentskills.py --export --output skills_export.json
    python scripts/sync_agentskills.py --import --input skills_import.json
    python scripts/sync_agentskills.py --sync --remote https://api.agentskills.io/v1
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保能导入核心模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class AgentSkillsSync:
    """
    agentskills.io 双向同步引擎
    """
    
    def __init__(self, remote_url: Optional[str] = None, api_key: Optional[str] = None):
        self.remote_url = remote_url
        self.api_key = api_key
        self.stats = {"exported": 0, "imported": 0, "conflicts": 0, "skipped": 0}
    
    def export_local_skills(
        self,
        output_path: str,
        export_format: str = "agentskills"
    ) -> bool:
        """
        导出本地技能
        
        Args:
            output_path: 输出文件路径
            export_format: 输出格式 (agentskills/json)
            
        Returns:
            bool: 是否成功
        """
        try:
            from core.skill_manager import get_skill_manager
            manager = get_skill_manager()
            
            if export_format == "agentskills":
                data = manager.export_all_agentskills()
            else:
                skills = manager.list_skills()
                data = {
                    "skills": [s.to_dict() for s in skills],
                    "exported_at": datetime.now().isoformat()
                }
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.stats["exported"] = len(data.get("skills", []))
            logger.info(f"Exported {self.stats['exported']} skills to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False
    
    def import_to_local(
        self,
        input_path: str,
        conflict_strategy: str = "skip"  # skip, override, merge
    ) -> bool:
        """
        导入技能到本地
        
        Args:
            input_path: 输入文件路径
            conflict_strategy: 冲突处理策略
            
        Returns:
            bool: 是否成功
        """
        try:
            from core.skill_manager import get_skill_manager
            manager = get_skill_manager()
            
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            imported = 0
            skipped = 0
            conflicts = 0
            
            skills = data.get("skills", [])
            if not skills and "skill" in data:
                skills = [data["skill"]]
            
            for skill_data in skills:
                skill_id = skill_data.get("id")
                
                # 检查冲突
                existing = manager.storage.get(skill_id) if skill_id else None
                
                if existing and conflict_strategy == "skip":
                    skipped += 1
                    continue
                
                if existing and conflict_strategy == "override":
                    manager.delete_skill(skill_id)
                
                # 导入
                result = manager.import_from_agentskills({"skill": skill_data})
                if result:
                    imported += 1
                else:
                    conflicts += 1
            
            self.stats["imported"] = imported
            self.stats["skipped"] = skipped
            self.stats["conflicts"] = conflicts
            
            logger.info(f"Imported {imported}, skipped {skipped}, conflicts {conflicts}")
            return True
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return False
    
    def sync_with_remote(
        self,
        direction: str = "bidirectional"  # upload, download, bidirectional
    ) -> Dict[str, Any]:
        """
        与远程 agentskills.io 同步（骨架实现，需配置 API key）
        
        Args:
            direction: 同步方向
            
        Returns:
            Dict: 同步报告
        """
        if not self.remote_url or not self.api_key:
            return {"error": "Remote URL and API key required for sync"}
        
        # TODO: 实现 HTTP 同步逻辑
        # 当前返回骨架报告
        return {
            "direction": direction,
            "remote_url": self.remote_url,
            "status": "not_implemented",
            "message": "Remote sync requires agentskills.io API access. Use --export/--import for local operations."
        }
    
    def validate_export(self, file_path: str) -> Dict[str, Any]:
        """
        验证导出文件的格式合规性
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict: 验证报告
        """
        try:
            from core.skill_validator import get_skill_validator
            validator = get_skill_validator()
            result = validator.validate_file(file_path)
            
            return {
                "valid": result.ok,
                "errors": result.errors,
                "warnings": result.warnings,
                "file": file_path
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def get_report(self) -> Dict[str, Any]:
        """获取同步报告"""
        return {
            **self.stats,
            "timestamp": datetime.now().isoformat(),
            "remote_url": self.remote_url
        }


def main():
    parser = argparse.ArgumentParser(description="agentskills.io 双向同步工具")
    parser.add_argument("--export", action="store_true", help="导出本地技能")
    parser.add_argument("--import", dest="import_cmd", action="store_true", help="导入技能到本地")
    parser.add_argument("--validate", action="store_true", help="验证导出文件")
    parser.add_argument("--input", help="输入文件路径")
    parser.add_argument("--output", default="data/skills_export.json", help="输出文件路径")
    parser.add_argument("--remote", help="agentskills.io API URL")
    parser.add_argument("--api-key", help="API Key")
    parser.add_argument("--conflict", default="skip", choices=["skip", "override", "merge"])
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    sync = AgentSkillsSync(remote_url=args.remote, api_key=args.api_key)
    
    if args.export:
        success = sync.export_local_skills(args.output)
        if success:
            print(f"\n[OK] Exported to {args.output}")
            print(f"Report: {json.dumps(sync.get_report(), indent=2)}")
        sys.exit(0 if success else 1)
    
    elif args.import_cmd:
        if not args.input:
            print("[NG] --input required for import")
            sys.exit(1)
        success = sync.import_to_local(args.input, conflict_strategy=args.conflict)
        if success:
            print(f"\n[OK] Imported from {args.input}")
            print(f"Report: {json.dumps(sync.get_report(), indent=2)}")
        sys.exit(0 if success else 1)
    
    elif args.validate:
        if not args.input:
            print("[NG] --input required for validation")
            sys.exit(1)
        result = sync.validate_export(args.input)
        print(f"\nValidation: {'PASS' if result['valid'] else 'FAIL'}")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["valid"] else 1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
