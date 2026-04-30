"""
本地文件语义索引 — FileIndexer / FileSensor

基于 memory_fts 为本地文件建立可检索的语义索引。
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.context.sensor_base import BaseContextSensor

logger = logging.getLogger(__name__)

# 支持的文件类型
SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".md", ".txt", ".csv", ".json", ".yaml", ".yml"}

# 最大文件大小（5MB）
MAX_FILE_SIZE = 5 * 1024 * 1024

# 索引元数据存储键
INDEX_META_KEY = "file_indexer_meta"


class FileIndexer:
    """
    文件语义索引器。

    功能：
    1. 扫描目录，为文件建立向量索引
    2. 为每个文件创建 L2 情景记忆
    3. 支持增量更新（新增、修改、删除同步）
    """

    def __init__(self, memory_manager=None, fts=None):
        self.memory_manager = memory_manager
        self.fts = fts
        self._indexed_paths: Dict[str, str] = {}  # path -> content_hash

    def _get_mm(self):
        if self.memory_manager is None:
            from core.memory_manager_v2 import get_memory_manager
            self.memory_manager = get_memory_manager()
        return self.memory_manager

    def _get_fts(self):
        if self.fts is None:
            from core.memory_fts import get_fts
            self.fts = get_fts()
        return self.fts

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希，用于检测变更"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _read_file(self, path: Path) -> Optional[str]:
        """安全读取文件内容"""
        try:
            if path.stat().st_size > MAX_FILE_SIZE:
                return None
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"无法读取文件 {path}: {e}")
            return None

    def _make_memory_key(self, path: Path) -> str:
        """生成记忆键"""
        return f"file:{path.resolve().as_posix()}"

    def _index_single(self, path: Path, content: str) -> bool:
        """索引单个文件到 L2 记忆和 FTS"""
        try:
            mm = self._get_mm()
            fts = self._get_fts()
            key = self._make_memory_key(path)

            # 构建文件摘要
            lines = content.splitlines()
            summary = f"文件: {path.name}\n路径: {path.parent.as_posix()}\n类型: {path.suffix}\n行数: {len(lines)}"
            if lines:
                preview = "\n".join(lines[:20])
                summary += f"\n预览:\n{preview}"

            # 写入 L2 情景记忆
            mm.write(
                layer="L2",
                key=key,
                value={
                    "path": path.as_posix(),
                    "name": path.name,
                    "extension": path.suffix,
                    "size": len(content),
                    "lines": len(lines),
                    "content_hash": self._compute_hash(content),
                    "indexed_at": datetime.now().isoformat(),
                },
                metadata={
                    "type": "file_index",
                    "source": "file_indexer",
                    "file_name": path.name,
                    "file_path": path.as_posix(),
                },
                user_id="file_indexer",
            )

            # 写入 FTS 全文索引（摘要用于语义搜索）
            fts.index_document(
                layer="L2",
                key=key,
                content=summary,
                metadata={"type": "file_index", "file_name": path.name},
            )

            self._indexed_paths[path.as_posix()] = self._compute_hash(content)
            return True
        except Exception as e:
            logger.error(f"索引文件失败 {path}: {e}")
            return False

    def _remove_index(self, path: Path) -> bool:
        """从索引中移除文件"""
        try:
            mm = self._get_mm()
            key = self._make_memory_key(path)
            mm.write(
                layer="L2",
                key=key,
                value={"deleted": True, "path": path.as_posix()},
                metadata={"type": "file_index", "source": "file_indexer", "status": "deleted"},
                user_id="file_indexer",
            )
            self._indexed_paths.pop(path.as_posix(), None)
            return True
        except Exception as e:
            logger.error(f"移除索引失败 {path}: {e}")
            return False

    # ------------------------------------------------------------------ #
    # 公开 API
    # ------------------------------------------------------------------ #

    def index_directory(self, root_path: str, recursive: bool = True) -> Dict:
        """
        扫描目录并建立/更新索引。
        返回统计信息。
        """
        root = Path(root_path).resolve()
        if not root.exists() or not root.is_dir():
            return {"error": f"目录不存在: {root_path}"}

        stats = {"added": 0, "updated": 0, "removed": 0, "skipped": 0, "errors": 0}
        current_paths: Set[str] = set()

        pattern = "**/*" if recursive else "*"
        for file_path in root.glob(pattern):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                stats["skipped"] += 1
                continue

            content = self._read_file(file_path)
            if content is None:
                stats["skipped"] += 1
                continue

            path_str = file_path.as_posix()
            current_paths.add(path_str)
            content_hash = self._compute_hash(content)

            # 检查是否已索引且未变更
            if path_str in self._indexed_paths and self._indexed_paths[path_str] == content_hash:
                continue

            # 检查 L2 中是否已有记录（通过 memory_manager 读取）
            try:
                mm = self._get_mm()
                existing = mm.read("L2", self._make_memory_key(file_path), agent_id="file_indexer")
                if existing and isinstance(existing, dict):
                    existing_hash = existing.get("content_hash")
                    if existing_hash == content_hash:
                        self._indexed_paths[path_str] = content_hash
                        continue
            except Exception:
                pass

            # 索引或更新
            if self._index_single(file_path, content):
                if path_str in self._indexed_paths and self._indexed_paths[path_str] != content_hash:
                    stats["updated"] += 1
                else:
                    stats["added"] += 1
            else:
                stats["errors"] += 1

        # 同步删除：移除已不在目录中的文件索引
        removed = []
        for indexed_path in list(self._indexed_paths.keys()):
            if indexed_path not in current_paths:
                if self._remove_index(Path(indexed_path)):
                    stats["removed"] += 1
                    removed.append(indexed_path)
                else:
                    stats["errors"] += 1

        for r in removed:
            self._indexed_paths.pop(r, None)

        # 保存索引元数据
        try:
            mm = self._get_mm()
            mm.write(
                layer="L0",
                key=INDEX_META_KEY,
                value={
                    "root": root.as_posix(),
                    "recursive": recursive,
                    "indexed_count": len(self._indexed_paths),
                    "last_scan": datetime.now().isoformat(),
                },
                metadata={"type": "index_meta", "source": "file_indexer"},
                user_id="file_indexer",
            )
        except Exception as e:
            logger.warning(f"保存索引元数据失败: {e}")

        return stats

    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        基于自然语言查询搜索已索引的文件。
        返回文件信息列表。
        """
        try:
            fts = self._get_fts()
            mm = self._get_mm()

            # 先尝试 FTS 搜索
            results = fts.search("L2", query, top_k=top_k)

            # 过滤只保留文件索引结果
            files = []
            for r in results:
                meta = r.get("metadata", {})
                if meta.get("type") == "file_index" or meta.get("source") == "file_indexer":
                    key = r.get("key", "")
                    # 尝试读取完整 L2 记录
                    full = mm.read("L2", key, agent_id="file_indexer")
                    if full and isinstance(full, dict) and not full.get("deleted"):
                        files.append({
                            "path": full.get("path", key.replace("file:", "")),
                            "name": full.get("name", "unknown"),
                            "extension": full.get("extension", ""),
                            "size": full.get("size", 0),
                            "lines": full.get("lines", 0),
                            "indexed_at": full.get("indexed_at"),
                            "score": r.get("score", 0),
                        })

            return files
        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            return []

    def get_indexed_files(self) -> List[Dict]:
        """获取所有已索引的文件列表"""
        return [
            {"path": p, "hash": h}
            for p, h in self._indexed_paths.items()
        ]

    def clear_index(self) -> bool:
        """清空所有文件索引"""
        try:
            for path_str in list(self._indexed_paths.keys()):
                self._remove_index(Path(path_str))
            self._indexed_paths.clear()
            return True
        except Exception as e:
            logger.error(f"清空索引失败: {e}")
            return False


class FileChangeSensor(BaseContextSensor):
    """
    文件变更传感器。

    扫描指定目录，收集最近修改的文件列表。
    不依赖 watchdog，基于文件 mtime 做简单扫描。
    """

    def __init__(self, watch_dir: str = ".", sensor_id: str = "file", privacy_level: str = "internal"):
        super().__init__(sensor_id, privacy_level)
        self.watch_dir = Path(watch_dir).resolve()
        self._stopped = False

    def collect(self) -> Dict[str, Any]:
        """收集最近 5 分钟内发生变更的文件列表"""
        if self._stopped:
            return {"changed_files": [], "watch_dir": str(self.watch_dir)}

        changed = []
        try:
            cutoff = datetime.now().timestamp() - 300  # 5 minutes
            for root, _dirs, files in os.walk(self.watch_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    try:
                        if fpath.stat().st_mtime > cutoff:
                            changed.append(str(fpath))
                    except (OSError, PermissionError):
                        continue
        except Exception as e:
            logger.warning(f"FileChangeSensor scan failed: {e}")

        return {"changed_files": changed, "watch_dir": str(self.watch_dir)}

    def filter_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """过滤敏感文件路径"""
        sensitive_names = {".env", "password", "secret", "key", "token", "credential"}
        filtered = []
        for p in data.get("changed_files", []):
            name = Path(p).name.lower()
            if any(s in name for s in sensitive_names):
                continue
            filtered.append(p)
        return {
            "changed_files": filtered,
            "watch_dir": data.get("watch_dir", "."),
        }

    def stop(self) -> None:
        """停止传感器"""
        self._stopped = True
