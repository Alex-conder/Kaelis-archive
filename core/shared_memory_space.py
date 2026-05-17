"""
Shared Memory Space Module
============================
提供跨 Agent 协作的共享记忆空间。

与 FourLayerMemoryManager (L0–L3) 完全独立，不互相干扰。

功能:
    - 创建/删除共享空间
    - 成员与权限管理 (owner/admin/writer/reader)
    - 共享记忆的 CRUD + 搜索 (FTS5)
    - 乐观锁版本控制 (预留冲突检测)
    - 语义标签支持

用法:
    from core.shared_memory_space import get_shared_memory_space
    sms = get_shared_memory_space()
    space = sms.create_space("team-project-x", "Team collaboration space", owner_id="u123")
    sms.write_memory(space["space_id"], key="goal", value={"target": "v1.0"}, user_id="u123")
    results = sms.search_memory(space["space_id"], query="goal")
"""

import json
import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ==============================================================================
# Constants
# ==============================================================================

DEFAULT_DB_DIR = os.environ.get("KAELIS_DATA_DIR", "data")
VALID_ROLES = {"owner", "admin", "writer", "reader"}
ROLE_HIERARCHY = {"owner": 4, "admin": 3, "writer": 2, "reader": 1}

# ==============================================================================
# Data Models (lightweight dicts for extensibility)
# ==============================================================================

class PermissionError(Exception):
    """权限不足"""
    pass


class SpaceNotFoundError(Exception):
    """空间不存在"""
    pass


class MemoryNotFoundError(Exception):
    """记忆不存在"""
    pass


# ==============================================================================
# SharedMemorySpace
# ==============================================================================

class SharedMemorySpace:
    """
    共享记忆空间管理器。

    每张 SQLite DB 包含:
        - shared_spaces: 空间元数据
        - shared_space_members: 成员与角色
        - shared_memories: 共享记忆内容
        - shared_memories_fts: FTS5 全文索引 (虚拟表)
    """

    def __init__(self, db_dir: str = DEFAULT_DB_DIR):
        self.db_path = Path(db_dir) / "shared_memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------ #
    # DB Initialization
    # ------------------------------------------------------------------ #

    def _init_db(self):
        with sqlite3.connect(str(self.db_path), check_same_thread=False) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS shared_spaces (
                    space_id    TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    description TEXT,
                    owner_id    TEXT NOT NULL,
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL,
                    config      TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS shared_space_members (
                    space_id   TEXT NOT NULL,
                    user_id    TEXT NOT NULL,
                    role       TEXT NOT NULL CHECK(role IN ('owner','admin','writer','reader')),
                    added_at   REAL NOT NULL,
                    added_by   TEXT NOT NULL,
                    last_seen  REAL,
                    PRIMARY KEY (space_id, user_id),
                    FOREIGN KEY (space_id) REFERENCES shared_spaces(space_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS shared_memories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    space_id    TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    metadata    TEXT DEFAULT '{}',
                    tags        TEXT DEFAULT '[]',
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL,
                    version     INTEGER DEFAULT 1,
                    UNIQUE(space_id, key),
                    FOREIGN KEY (space_id) REFERENCES shared_spaces(space_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_sm_space ON shared_memories(space_id);
                CREATE INDEX IF NOT EXISTS idx_sm_key ON shared_memories(key);

                -- Audit log for memory deletions
                CREATE TABLE IF NOT EXISTS shared_memory_audit (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    space_id    TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    action      TEXT NOT NULL,
                    old_value   TEXT,
                    user_id     TEXT NOT NULL,
                    reason      TEXT,
                    created_at  REAL NOT NULL
                );
            """)

            # Migrate: add last_seen column if missing (backward compat)
            try:
                conn.execute("SELECT last_seen FROM shared_space_members LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE shared_space_members ADD COLUMN last_seen REAL")
                logger.info("Migrated shared_space_members: added last_seen column")

            # Try to create FTS5 virtual table; gracefully degrade if unavailable
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS shared_memories_fts USING fts5(
                        key, value, tags,
                        content='shared_memories', content_rowid='id'
                    );
                """)
                # Triggers to keep FTS index in sync
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS sm_fts_insert AFTER INSERT ON shared_memories BEGIN
                        INSERT INTO shared_memories_fts(rowid, key, value, tags)
                        VALUES (new.id, new.key, new.value, new.tags);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS sm_fts_update AFTER UPDATE ON shared_memories BEGIN
                        INSERT INTO shared_memories_fts(shared_memories_fts, rowid, key, value, tags)
                        VALUES ('delete', old.id, old.key, old.value, old.tags);
                        INSERT INTO shared_memories_fts(rowid, key, value, tags)
                        VALUES (new.id, new.key, new.value, new.tags);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS sm_fts_delete AFTER DELETE ON shared_memories BEGIN
                        INSERT INTO shared_memories_fts(shared_memories_fts, rowid, key, value, tags)
                        VALUES ('delete', old.id, old.key, old.value, old.tags);
                    END;
                """)
                self._fts_available = True
            except sqlite3.OperationalError:
                self._fts_available = False
                logger.warning("FTS5 not available for shared memory; search will use LIKE fallback.")

    # ------------------------------------------------------------------ #
    # Internal Helpers
    # ------------------------------------------------------------------ #

    def _now(self) -> float:
        return time.time()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _check_permission(self, space_id: str, user_id: str, min_role: str) -> bool:
        """检查 user_id 在 space_id 中是否拥有至少 min_role 的权限。"""
        if min_role not in VALID_ROLES:
            return False
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT role FROM shared_space_members WHERE space_id = ? AND user_id = ?",
                (space_id, user_id),
            ).fetchone()
            if not row:
                return False
            return ROLE_HIERARCHY.get(row[0], 0) >= ROLE_HIERARCHY.get(min_role, 0)

    def _get_user_role(self, space_id: str, user_id: str) -> Optional[str]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT role FROM shared_space_members WHERE space_id = ? AND user_id = ?",
                (space_id, user_id),
            ).fetchone()
            return row[0] if row else None

    def _space_exists(self, space_id: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute("SELECT 1 FROM shared_spaces WHERE space_id = ?", (space_id,)).fetchone()
            return row is not None

    def _serialize(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value

    def _deserialize(self, raw: str) -> Any:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    # ------------------------------------------------------------------ #
    # Space Management
    # ------------------------------------------------------------------ #

    def create_space(
        self,
        name: str,
        description: str = "",
        owner_id: str = "anonymous",
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建共享记忆空间。创建者自动成为 owner。"""
        space_id = str(uuid.uuid4())
        now = self._now()
        config_json = json.dumps(config or {}, ensure_ascii=False)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO shared_spaces (space_id, name, description, owner_id, created_at, updated_at, config) VALUES (?,?,?,?,?,?,?)",
                (space_id, name, description, owner_id, now, now, config_json),
            )
            conn.execute(
                "INSERT INTO shared_space_members (space_id, user_id, role, added_at, added_by) VALUES (?,?,?,?,?)",
                (space_id, owner_id, "owner", now, owner_id),
            )
        logger.info("Created shared space %s (%s) by %s", space_id, name, owner_id)
        return {
            "space_id": space_id,
            "name": name,
            "description": description,
            "owner_id": owner_id,
            "created_at": now,
            "updated_at": now,
            "config": config or {},
        }

    def get_space(self, space_id: str, user_id: str = "anonymous") -> Dict[str, Any]:
        """获取空间详情（含成员列表）。需要 reader 权限。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "reader"):
            raise PermissionError("Insufficient permission to view this space")

        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT space_id, name, description, owner_id, created_at, updated_at, config FROM shared_spaces WHERE space_id = ?",
                (space_id,),
            ).fetchone()
            members = conn.execute(
                "SELECT user_id, role, added_at, added_by, last_seen FROM shared_space_members WHERE space_id = ?",
                (space_id,),
            ).fetchall()

        return {
            "space_id": row[0],
            "name": row[1],
            "description": row[2],
            "owner_id": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "config": self._deserialize(row[6]),
            "members": [
                {"user_id": m[0], "role": m[1], "added_at": m[2], "added_by": m[3], "last_seen": m[4]}
                for m in members
            ],
        }

    def list_spaces(self, user_id: str = "anonymous") -> List[Dict[str, Any]]:
        """列出用户有权限的所有空间。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT s.space_id, s.name, s.description, s.owner_id, s.created_at, s.updated_at, s.config, m.role
                FROM shared_spaces s
                JOIN shared_space_members m ON s.space_id = m.space_id
                WHERE m.user_id = ?
                ORDER BY s.updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "space_id": r[0],
                "name": r[1],
                "description": r[2],
                "owner_id": r[3],
                "created_at": r[4],
                "updated_at": r[5],
                "config": self._deserialize(r[6]),
                "my_role": r[7],
            }
            for r in rows
        ]

    def delete_space(self, space_id: str, user_id: str = "anonymous") -> bool:
        """删除空间。需要 owner 权限。级联删除成员和记忆。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "owner"):
            raise PermissionError("Only owner can delete a space")
        with self._get_conn() as conn:
            conn.execute("DELETE FROM shared_spaces WHERE space_id = ?", (space_id,))
        logger.info("Deleted shared space %s by %s", space_id, user_id)
        return True

    # ------------------------------------------------------------------ #
    # Member & Permission Management
    # ------------------------------------------------------------------ #

    def add_member(
        self,
        space_id: str,
        target_user_id: str,
        role: str,
        added_by: str = "anonymous",
    ) -> Dict[str, Any]:
        """添加成员。需要 admin 权限。不能添加 owner。"""
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")
        if role == "owner":
            raise PermissionError("Cannot assign owner role via add_member")
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, added_by, "admin"):
            raise PermissionError("Only admin or owner can add members")

        now = self._now()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO shared_space_members (space_id, user_id, role, added_at, added_by) VALUES (?,?,?,?,?)",
                (space_id, target_user_id, role, now, added_by),
            )
        logger.info("Added member %s as %s to space %s by %s", target_user_id, role, space_id, added_by)
        return {"space_id": space_id, "user_id": target_user_id, "role": role, "added_at": now}

    def remove_member(
        self,
        space_id: str,
        target_user_id: str,
        removed_by: str = "anonymous",
    ) -> bool:
        """移除成员。需要 admin 权限。不能移除 owner。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, removed_by, "admin"):
            raise PermissionError("Only admin or owner can remove members")
        target_role = self._get_user_role(space_id, target_user_id)
        if target_role == "owner":
            raise PermissionError("Cannot remove owner")
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM shared_space_members WHERE space_id = ? AND user_id = ?",
                (space_id, target_user_id),
            )
        logger.info("Removed member %s from space %s by %s", target_user_id, space_id, removed_by)
        return True

    def update_member_role(
        self,
        space_id: str,
        target_user_id: str,
        new_role: str,
        updated_by: str = "anonymous",
    ) -> Dict[str, Any]:
        """更新成员角色。需要 admin 权限。"""
        if new_role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {new_role}")
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, updated_by, "admin"):
            raise PermissionError("Only admin or owner can update roles")
        if new_role == "owner":
            raise PermissionError("Cannot promote to owner via this API")
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE shared_space_members SET role = ? WHERE space_id = ? AND user_id = ?",
                (new_role, space_id, target_user_id),
            )
        return {"space_id": space_id, "user_id": target_user_id, "role": new_role}

    def heartbeat(self, space_id: str, user_id: str) -> Dict[str, Any]:
        """更新成员心跳时间。需要 reader 权限。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "reader"):
            raise PermissionError("Not a member of this space")
        now = self._now()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE shared_space_members SET last_seen = ? WHERE space_id = ? AND user_id = ?",
                (now, space_id, user_id),
            )
        return {"space_id": space_id, "user_id": user_id, "last_seen": now}

    def get_member_status(self, space_id: str, user_id: str = "anonymous") -> List[Dict[str, Any]]:
        """获取空间成员在线状态。需要 reader 权限。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "reader"):
            raise PermissionError("Insufficient permission to view this space")
        now = self._now()
        stale_threshold = 5 * 60  # 5 minutes
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT user_id, role, last_seen FROM shared_space_members WHERE space_id = ?",
                (space_id,),
            ).fetchall()
        return [
            {
                "user_id": r[0],
                "role": r[1],
                "last_seen": r[2],
                "online": r[2] is not None and (now - r[2]) < stale_threshold,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Memory CRUD
    # ------------------------------------------------------------------ #

    def write_memory(
        self,
        space_id: str,
        key: str,
        value: Any,
        user_id: str = "anonymous",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
        expected_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        写入共享记忆。

        Args:
            expected_version: 如果提供，仅在当前版本匹配时才写入（乐观锁）。
        """
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "writer"):
            raise PermissionError("Writer permission required")

        now = self._now()
        value_str = self._serialize(value)
        meta = metadata or {}
        meta["author"] = user_id
        meta["ttl_seconds"] = ttl_seconds
        meta_str = json.dumps(meta, ensure_ascii=False)
        tags_str = json.dumps(tags or [], ensure_ascii=False)

        with self._get_conn() as conn:
            # Check existing version for optimistic locking
            if expected_version is not None:
                row = conn.execute(
                    "SELECT version FROM shared_memories WHERE space_id = ? AND key = ?",
                    (space_id, key),
                ).fetchone()
                current_version = row[0] if row else 0
                if current_version != expected_version:
                    raise PermissionError(
                        f"Version conflict: expected {expected_version}, found {current_version}"
                    )

            conn.execute(
                """
                INSERT INTO shared_memories (space_id, key, value, metadata, tags, created_at, updated_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(space_id, key) DO UPDATE SET
                    value = excluded.value,
                    metadata = excluded.metadata,
                    tags = excluded.tags,
                    updated_at = excluded.updated_at,
                    version = shared_memories.version + 1
                """,
                (space_id, key, value_str, meta_str, tags_str, now, now),
            )
            # Get final version
            row = conn.execute(
                "SELECT version FROM shared_memories WHERE space_id = ? AND key = ?",
                (space_id, key),
            ).fetchone()
            final_version = row[0] if row else 1

        logger.debug("Wrote memory %s/%s by %s (v%d)", space_id, key, user_id, final_version)

        # Publish semantic pubsub event (Sprint 7 D9)
        try:
            from core.semantic_pubsub import get_pubsub_engine
            pubsub = get_pubsub_engine()
            pubsub.publish(
                space_id=space_id,
                key=key,
                value=parsed_value,
                tags=tags,
                metadata={"author": user_id, "version": final_version},
            )
        except Exception as e:
            logger.debug("Pubsub publish failed (non-critical): %s", e)

        return {
            "space_id": space_id,
            "key": key,
            "version": final_version,
            "created_at": now,
            "updated_at": now,
        }

    def read_memory(self, space_id: str, key: str, user_id: str = "anonymous") -> Dict[str, Any]:
        """读取单条共享记忆。需要 reader 权限。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "reader"):
            raise PermissionError("Reader permission required")

        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT id, space_id, key, value, metadata, tags, created_at, updated_at, version
                FROM shared_memories WHERE space_id = ? AND key = ?
                """,
                (space_id, key),
            ).fetchone()
        if not row:
            raise MemoryNotFoundError(f"Memory {key} not found in space {space_id}")

        return {
            "id": row[0],
            "space_id": row[1],
            "key": row[2],
            "value": self._deserialize(row[3]),
            "metadata": self._deserialize(row[4]),
            "tags": self._deserialize(row[5]),
            "created_at": row[6],
            "updated_at": row[7],
            "version": row[8],
        }

    def delete_memory(
        self,
        space_id: str,
        key: str,
        user_id: str = "anonymous",
        reason: str = "",
    ) -> bool:
        """删除共享记忆。需要 writer 权限（只能删自己的）或 admin（可删任何）。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")

        # Determine if user can delete
        user_role = self._get_user_role(space_id, user_id)
        if user_role is None:
            raise PermissionError("Not a member of this space")

        with self._get_conn() as conn:
            # Get existing memory for audit
            row = conn.execute(
                "SELECT value, metadata FROM shared_memories WHERE space_id = ? AND key = ?",
                (space_id, key),
            ).fetchone()
            if not row:
                raise MemoryNotFoundError(f"Memory {key} not found in space {space_id}")

            meta = self._deserialize(row[1]) or {}
            author = meta.get("author", "")

            # Permission check: admin+ can delete anything; writer can delete own
            can_delete = (
                ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY["admin"]
                or (user_role == "writer" and author == user_id)
            )
            if not can_delete:
                raise PermissionError("Cannot delete this memory")

            # Audit log
            conn.execute(
                "INSERT INTO shared_memory_audit (space_id, key, action, old_value, user_id, reason, created_at) VALUES (?,?,?,?,?,?,?)",
                (space_id, key, "delete", row[0], user_id, reason, self._now()),
            )
            # Delete
            conn.execute(
                "DELETE FROM shared_memories WHERE space_id = ? AND key = ?",
                (space_id, key),
            )
        logger.info("Deleted memory %s/%s by %s (reason: %s)", space_id, key, user_id, reason)
        return True

    def list_memories(
        self,
        space_id: str,
        user_id: str = "anonymous",
        limit: int = 50,
        offset: int = 0,
        tag_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出空间内的记忆。需要 reader 权限。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "reader"):
            raise PermissionError("Reader permission required")

        with self._get_conn() as conn:
            if tag_filter:
                # JSON contains search via LIKE on tags column
                rows = conn.execute(
                    """
                    SELECT id, space_id, key, value, metadata, tags, created_at, updated_at, version
                    FROM shared_memories
                    WHERE space_id = ? AND tags LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (space_id, f'%"{tag_filter}"%', limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, space_id, key, value, metadata, tags, created_at, updated_at, version
                    FROM shared_memories
                    WHERE space_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (space_id, limit, offset),
                ).fetchall()

        return [
            {
                "id": r[0],
                "space_id": r[1],
                "key": r[2],
                "value": self._deserialize(r[3]),
                "metadata": self._deserialize(r[4]),
                "tags": self._deserialize(r[5]),
                "created_at": r[6],
                "updated_at": r[7],
                "version": r[8],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search_memory(
        self,
        space_id: str,
        query: str,
        user_id: str = "anonymous",
        top_k: int = 10,
        exact_key: bool = False,
    ) -> List[Dict[str, Any]]:
        """搜索共享记忆。先 FTS5，后 LIKE 回退。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "reader"):
            raise PermissionError("Reader permission required")

        results: List[Dict[str, Any]] = []
        with self._get_conn() as conn:
            if exact_key:
                row = conn.execute(
                    """
                    SELECT id, space_id, key, value, metadata, tags, created_at, updated_at, version
                    FROM shared_memories WHERE space_id = ? AND key = ?
                    """,
                    (space_id, query),
                ).fetchone()
                if row:
                    results.append({
                        "id": row[0], "space_id": row[1], "key": row[2],
                        "value": self._deserialize(row[3]),
                        "metadata": self._deserialize(row[4]),
                        "tags": self._deserialize(row[5]),
                        "created_at": row[6], "updated_at": row[7], "version": row[8],
                    })
                return results

            # Try FTS5
            if self._fts_available:
                try:
                    fts_rows = conn.execute(
                        """
                        SELECT sm.id, sm.space_id, sm.key, sm.value, sm.metadata, sm.tags, sm.created_at, sm.updated_at, sm.version
                        FROM shared_memories_fts fts
                        JOIN shared_memories sm ON sm.id = fts.rowid
                        WHERE shared_memories_fts MATCH ? AND sm.space_id = ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (query, space_id, top_k),
                    ).fetchall()
                    if fts_rows:
                        results = [
                            {
                                "id": r[0], "space_id": r[1], "key": r[2],
                                "value": self._deserialize(r[3]),
                                "metadata": self._deserialize(r[4]),
                                "tags": self._deserialize(r[5]),
                                "created_at": r[6], "updated_at": r[7], "version": r[8],
                            }
                            for r in fts_rows
                        ]
                except sqlite3.OperationalError:
                    pass

            # Fallback to LIKE
            if not results:
                pattern = f"%{query}%"
                like_rows = conn.execute(
                    """
                    SELECT id, space_id, key, value, metadata, tags, created_at, updated_at, version
                    FROM shared_memories
                    WHERE space_id = ? AND (key LIKE ? OR value LIKE ? OR tags LIKE ?)
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (space_id, pattern, pattern, pattern, top_k),
                ).fetchall()
                results = [
                    {
                        "id": r[0], "space_id": r[1], "key": r[2],
                        "value": self._deserialize(r[3]),
                        "metadata": self._deserialize(r[4]),
                        "tags": self._deserialize(r[5]),
                        "created_at": r[6], "updated_at": r[7], "version": r[8],
                    }
                    for r in like_rows
                ]

        return results

    # ------------------------------------------------------------------ #
    # Statistics & Audit
    # ------------------------------------------------------------------ #

    def stats(self, space_id: Optional[str] = None) -> Dict[str, Any]:
        """返回统计信息。"""
        with self._get_conn() as conn:
            if space_id:
                count = conn.execute(
                    "SELECT COUNT(*) FROM shared_memories WHERE space_id = ?", (space_id,)
                ).fetchone()[0]
                member_count = conn.execute(
                    "SELECT COUNT(*) FROM shared_space_members WHERE space_id = ?", (space_id,)
                ).fetchone()[0]
                return {"space_id": space_id, "memory_count": count, "member_count": member_count}
            else:
                space_count = conn.execute("SELECT COUNT(*) FROM shared_spaces").fetchone()[0]
                mem_count = conn.execute("SELECT COUNT(*) FROM shared_memories").fetchone()[0]
                return {"total_spaces": space_count, "total_memories": mem_count}

    def get_audit_log(
        self,
        space_id: str,
        user_id: str = "anonymous",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取审计日志。需要 admin 权限。"""
        if not self._check_permission(space_id, user_id, "admin"):
            raise PermissionError("Admin permission required")
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, space_id, key, action, old_value, user_id, reason, created_at FROM shared_memory_audit WHERE space_id = ? ORDER BY created_at DESC LIMIT ?",
                (space_id, limit),
            ).fetchall()
        return [
            {
                "id": r[0], "space_id": r[1], "key": r[2], "action": r[3],
                "old_value": self._deserialize(r[4]), "user_id": r[5],
                "reason": r[6], "created_at": r[7],
            }
            for r in rows
        ]

    def get_conflicts(
        self,
        space_id: str,
        user_id: str = "anonymous",
        include_resolved: bool = False,
    ) -> List[Dict[str, Any]]:
        """获取记忆冲突列表。需要 reader 权限。"""
        if not self._space_exists(space_id):
            raise SpaceNotFoundError(f"Space {space_id} not found")
        if not self._check_permission(space_id, user_id, "reader"):
            raise PermissionError("Reader permission required")
        with self._get_conn() as conn:
            # Check if conflicts table exists
            table_exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_conflicts'"
            ).fetchone()
            if not table_exists:
                return []
            if include_resolved:
                rows = conn.execute(
                    "SELECT id, space_id, key_a, key_b, similarity, reason, resolved, detected_at FROM memory_conflicts WHERE space_id = ? ORDER BY detected_at DESC",
                    (space_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, space_id, key_a, key_b, similarity, reason, resolved, detected_at FROM memory_conflicts WHERE space_id = ? AND resolved = 0 ORDER BY detected_at DESC",
                    (space_id,),
                ).fetchall()
        return [
            {
                "id": r[0], "space_id": r[1], "key_a": r[2], "key_b": r[3],
                "similarity": r[4], "reason": r[5], "resolved": bool(r[6]), "detected_at": r[7],
            }
            for r in rows
        ]

    def resolve_conflict(self, space_id: str, conflict_id: int, user_id: str = "anonymous") -> bool:
        """标记冲突为已解决。需要 admin 权限。"""
        if not self._check_permission(space_id, user_id, "admin"):
            raise PermissionError("Admin permission required")
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE memory_conflicts SET resolved = 1 WHERE id = ? AND space_id = ?",
                (conflict_id, space_id),
            )
        return True


# ==============================================================================
# Singleton
# ==============================================================================

_SHARED_MEMORY_SPACE_INSTANCE: Optional[SharedMemorySpace] = None


def get_shared_memory_space(db_dir: str = DEFAULT_DB_DIR) -> SharedMemorySpace:
    global _SHARED_MEMORY_SPACE_INSTANCE
    if _SHARED_MEMORY_SPACE_INSTANCE is None:
        _SHARED_MEMORY_SPACE_INSTANCE = SharedMemorySpace(db_dir=db_dir)
    return _SHARED_MEMORY_SPACE_INSTANCE


def reset_shared_memory_space():
    """测试用：重置单例"""
    global _SHARED_MEMORY_SPACE_INSTANCE
    _SHARED_MEMORY_SPACE_INSTANCE = None
