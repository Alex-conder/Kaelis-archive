"""
迁移脚本：旧记忆数据 -> 四层记忆架构 (P10-006)

功能：
1. 扫描旧版记忆存储（JSON文件、旧SQLite表）
2. 按规则分发到 L0/L1/L2/L3
3. 支持断点续传（记录迁移进度到 JSON 文件）
4. 支持回滚（备份旧数据）
5. 幂等执行（重复运行安全）

执行方式：
    python scripts/migrate_to_four_layer.py [--dry-run] [--resume]

分发规则：
    - system_* / config_* / identity_* -> L0
    - user_pref_* / session_* / active_* -> L1 (TTL 7d)
    - event_* / task_* / log_* -> L2
    - entity_* / kg_* / concept_* -> L3
"""

import argparse
import json
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保能导入核心模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class MigrationEngine:
    """
    四层记忆迁移引擎
    
    状态文件：data/migration_state.json
    备份目录：data/migration_backup/
    """
    
    LAYER_RULES = [
        ("L0", ["system_", "config_", "identity_", "version_", "schema_"]),
        ("L1", ["user_pref_", "session_", "active_", "cache_", "temp_"]),
        ("L2", ["event_", "task_", "log_", "record_", "history_"]),
        ("L3", ["entity_", "kg_", "concept_", "knowledge_", "semantic_"]),
    ]
    
    def __init__(self, db_dir: str = "data", dry_run: bool = False):
        self.db_dir = Path(db_dir)
        self.dry_run = dry_run
        self.backup_dir = self.db_dir / "migration_backup"
        self.state_file = self.db_dir / "migration_state.json"
        self.state = self._load_state()
        
        # 统计
        self.stats = {"scanned": 0, "migrated": 0, "skipped": 0, "errors": 0}
    
    def _load_state(self) -> Dict[str, Any]:
        """加载迁移状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        return {"completed_steps": [], "last_run": None, "version": "1.0"}
    
    def _save_state(self):
        """保存迁移状态"""
        self.state["last_run"] = datetime.now().isoformat()
        if not self.dry_run:
            try:
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to save state: {e}")
    
    def _is_step_completed(self, step: str) -> bool:
        """检查步骤是否已完成"""
        return step in self.state.get("completed_steps", [])
    
    def _mark_step_completed(self, step: str):
        """标记步骤完成"""
        if step not in self.state.get("completed_steps", []):
            self.state.setdefault("completed_steps", []).append(step)
    
    def _classify_layer(self, key: str) -> str:
        """根据 key 前缀分类到对应层"""
        key_lower = key.lower()
        for layer, prefixes in self.LAYER_RULES:
            for prefix in prefixes:
                if key_lower.startswith(prefix):
                    return layer
        # 默认按内容推断
        if any(w in key_lower for w in ["pref", "setting", "theme", "ui"]):
            return "L1"
        if any(w in key_lower for w in ["event", "action", "run", "exec"]):
            return "L2"
        if any(w in key_lower for w in ["entity", "node", "rel", "triple"]):
            return "L3"
        return "L2"  # 默认 L2（永久事件）
    
    def _backup_database(self, db_name: str) -> bool:
        """备份数据库文件"""
        src = self.db_dir / db_name
        if not src.exists():
            return True
        
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        dst = self.backup_dir / f"{db_name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        
        try:
            shutil.copy2(str(src), str(dst))
            logger.info(f"Backup created: {dst}")
            return True
        except Exception as e:
            logger.error(f"Backup failed for {db_name}: {e}")
            return False
    
    def migrate_json_files(self):
        """迁移 JSON 文件中的记忆数据"""
        step = "json_files"
        if self._is_step_completed(step):
            logger.info(f"Step '{step}' already completed, skipping")
            return
        
        logger.info("=== Step: Migrate JSON files ===")
        
        # 查找可能的旧记忆 JSON 文件
        patterns = ["*memory*.json", "*cache*.json", "*session*.json", "*events*.json"]
        files = []
        for pattern in patterns:
            files.extend(self.db_dir.glob(pattern))
        
        # 去重
        files = list(set(files))
        
        for file_path in files:
            logger.info(f"Processing: {file_path.name}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    # 可能是 key-value 存储
                    for key, value in data.items():
                        self._migrate_item(key, value, source=f"json:{file_path.name}")
                elif isinstance(data, list):
                    # 可能是事件列表
                    for i, item in enumerate(data):
                        item_key = item.get("key", item.get("id", f"item_{i}"))
                        self._migrate_item(item_key, item, source=f"json:{file_path.name}")
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                self.stats["errors"] += 1
        
        self._mark_step_completed(step)
        self._save_state()
    
    def migrate_sqlite_legacy_tables(self):
        """迁移旧版 SQLite 表中的记忆数据"""
        step = "sqlite_legacy"
        if self._is_step_completed(step):
            logger.info(f"Step '{step}' already completed, skipping")
            return
        
        logger.info("=== Step: Migrate SQLite legacy tables ===")
        
        db_path = self.db_dir / "kaelis_dev.db"
        if not db_path.exists():
            logger.info("kaelis_dev.db not found, skipping")
            self._mark_step_completed(step)
            self._save_state()
            return
        
        # 备份
        if not self.dry_run:
            self._backup_database("kaelis_dev.db")
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        # 旧表候选
        legacy_candidates = [
            "memories", "memory", "cache", "session_data", "events",
            "old_memory_l0", "old_memory_l1", "old_memory_l2"
        ]
        
        for table in legacy_candidates:
            if table not in tables:
                continue
            
            logger.info(f"Migrating legacy table: {table}")
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.execute(f"SELECT * FROM {table}")
                columns = [d[0] for d in cursor.description]
                rows = cursor.fetchall()
                conn.close()
                
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    key = row_dict.get("key") or row_dict.get("id") or row_dict.get("name", "unknown")
                    value = row_dict.get("value") or row_dict
                    self._migrate_item(key, value, source=f"sqlite:{table}")
                
                logger.info(f"  Migrated {len(rows)} rows from {table}")
                
            except Exception as e:
                logger.error(f"Failed to migrate table {table}: {e}")
                self.stats["errors"] += 1
        
        self._mark_step_completed(step)
        self._save_state()
    
    def _migrate_item(self, key: str, value: Any, source: str):
        """迁移单个记忆项到对应层"""
        self.stats["scanned"] += 1
        
        layer = self._classify_layer(key)
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would migrate '{key}' -> {layer} (from {source})")
            self.stats["migrated"] += 1
            return
        
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            
            # 序列化值
            if not isinstance(value, (str, int, float, bool, dict, list)):
                value = str(value)
            
            metadata = {"migrated_from": source, "migrated_at": datetime.now().isoformat()}
            ok = mm.write(layer, key, value, metadata)
            
            if ok:
                self.stats["migrated"] += 1
            else:
                self.stats["errors"] += 1
                
        except Exception as e:
            logger.error(f"Failed to migrate item '{key}': {e}")
            self.stats["errors"] += 1
    
    def run(self, resume: bool = False):
        """
        执行完整迁移流程
        
        Args:
            resume: 是否从上次断点续传
        """
        if not resume and self.state.get("completed_steps"):
            logger.warning("Previous migration state found. Use --resume to continue or delete data/migration_state.json to restart.")
            return False
        
        logger.info(f"=== Four-Layer Memory Migration ===")
        logger.info(f"  Dry run: {self.dry_run}")
        logger.info(f"  Resume: {resume}")
        logger.info(f"  DB dir: {self.db_dir}")
        
        # 确认 FourLayerMemoryManager 可用
        try:
            from core.memory_manager_v2 import get_memory_manager
            get_memory_manager()
            logger.info("FourLayerMemoryManager: available")
        except Exception as e:
            logger.error(f"FourLayerMemoryManager not available: {e}")
            return False
        
        # 执行各步骤
        self.migrate_json_files()
        self.migrate_sqlite_legacy_tables()
        
        # 最终统计
        logger.info("=== Migration Summary ===")
        logger.info(f"  Scanned:   {self.stats['scanned']}")
        logger.info(f"  Migrated:  {self.stats['migrated']}")
        logger.info(f"  Skipped:   {self.stats['skipped']}")
        logger.info(f"  Errors:    {self.stats['errors']}")
        
        if self.stats["errors"] == 0:
            logger.info("[OK] Migration completed successfully")
            return True
        else:
            logger.warning("[NG] Migration completed with errors")
            return False
    
    def rollback(self):
        """
        回滚迁移（从备份恢复数据库）
        
        注意：仅恢复数据库文件备份，不会删除已写入四层架构的数据。
        如需完全回滚，需手动清理 L0-L3 表。
        """
        logger.info("=== Rollback ===")
        
        if not self.backup_dir.exists():
            logger.warning("No backup directory found")
            return False
        
        backups = sorted(self.backup_dir.glob("*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups:
            logger.warning("No backup files found")
            return False
        
        # 恢复最新的备份
        for backup in backups:
            # 解析原始文件名: kaelis_dev.db.20240101_120000.bak -> kaelis_dev.db
            original_name = ".".join(backup.name.split(".")[:-2])
            dst = self.db_dir / original_name
            
            try:
                shutil.copy2(str(backup), str(dst))
                logger.info(f"Restored: {backup.name} -> {dst}")
            except Exception as e:
                logger.error(f"Failed to restore {backup.name}: {e}")
        
        # 清理状态文件
        if self.state_file.exists():
            self.state_file.unlink()
            logger.info("Migration state cleared")
        
        logger.info("[OK] Rollback completed. Note: Four-layer data not automatically deleted.")
        return True


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy memory data to four-layer architecture")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without writing")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--rollback", action="store_true", help="Rollback from backup")
    parser.add_argument("--db-dir", default="data", help="Database directory")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    engine = MigrationEngine(db_dir=args.db_dir, dry_run=args.dry_run)
    
    if args.rollback:
        success = engine.rollback()
    else:
        success = engine.run(resume=args.resume)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
