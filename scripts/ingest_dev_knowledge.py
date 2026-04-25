"""
Kaelis Developer Knowledge Ingestion Pipeline
===============================================
将项目文档（docs/、dev-status/、.kaelis/）导入 L3 Semantic 记忆空间。

用法:
    python scripts/ingest_dev_knowledge.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.memory_manager_v2 import get_memory_manager
from core.memory_consolidator import MemoryConsolidator

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ============================================================================
# Config
# ============================================================================

SOURCE_DIRS = [
    (PROJECT_ROOT / "docs", "design_doc"),
    (PROJECT_ROOT / "dev-status", "status_report"),
    (PROJECT_ROOT / ".kaelis", "project_meta"),
]

AGENT_ID = "kaelis_dev"
USER_ID = "master_architect"
BATCH_SIZE = 50

# 代码文件也纳入知识库
CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".yaml", ".yml", ".json"}
DOC_EXTENSIONS = {".md", ".markdown"}
ALL_EXTENSIONS = DOC_EXTENSIONS | CODE_EXTENSIONS

MAX_FILE_SIZE = 500 * 1024  # 500KB


# ============================================================================
# File Scanner
# ============================================================================

def scan_source_files() -> List[Tuple[Path, str]]:
    """扫描所有源文件，返回 (文件路径, 类型) 列表。"""
    files: List[Tuple[Path, str]] = []

    for base_dir, doc_type in SOURCE_DIRS:
        if not base_dir.exists():
            logger.warning("Directory not found: %s", base_dir)
            continue

        for path in base_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.stat().st_size > MAX_FILE_SIZE:
                logger.debug("Skipping large file: %s", path.relative_to(PROJECT_ROOT))
                continue

            ext = path.suffix.lower()
            if ext in DOC_EXTENSIONS:
                files.append((path, doc_type))
            elif ext in CODE_EXTENSIONS:
                # 代码文件标记为 api_spec / config / implementation
                if "contracts" in path.parts or "openapi" in path.name.lower():
                    files.append((path, "api_spec"))
                elif path.name in {"requirements.txt", "package.json"}:
                    files.append((path, "config"))
                else:
                    files.append((path, "implementation"))

    # 额外纳入关键配置文件
    extra_files = [
        (PROJECT_ROOT / "README.md", "design_doc"),
        (PROJECT_ROOT / "AGENTS.md", "design_doc"),
        (PROJECT_ROOT / "requirements.txt", "config"),
        (PROJECT_ROOT / "prod_server.py", "implementation"),
    ]
    for path, doc_type in extra_files:
        if path.exists() and path not in [f[0] for f in files]:
            files.append((path, doc_type))

    return sorted(files, key=lambda x: str(x[0]))


# ============================================================================
# Content Processor
# ============================================================================

def read_file_content(path: Path) -> str:
    """读取文件内容，自动检测编码。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="gbk")
        except Exception:
            return "[Binary or unreadable content]"


def chunk_content(content: str, max_chars: int = 4000) -> List[str]:
    """将长文本切分为多个 chunk，保持段落边界。"""
    if len(content) <= max_chars:
        return [content]

    chunks = []
    current = ""
    for paragraph in content.split("\n\n"):
        if len(current) + len(paragraph) + 2 > max_chars:
            if current:
                chunks.append(current.strip())
            current = paragraph
        else:
            current += "\n\n" + paragraph if current else paragraph
    if current:
        chunks.append(current.strip())
    return chunks


# ============================================================================
# Memory Writer
# ============================================================================

def ingest_file(mm, file_path: Path, doc_type: str) -> int:
    """将单个文件写入 L3 记忆，返回写入的条数。"""
    rel_path = str(file_path.relative_to(PROJECT_ROOT))
    content = read_file_content(file_path)

    if not content.strip():
        return 0

    chunks = chunk_content(content)
    count = 0

    for idx, chunk in enumerate(chunks):
        key = f"{rel_path}#chunk{idx}" if len(chunks) > 1 else rel_path
        metadata = {
            "source": rel_path,
            "type": doc_type,
            "chunk_index": idx,
            "total_chunks": len(chunks),
            "size": len(chunk),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        success = mm.write(
            layer="L3",
            key=key,
            value=chunk,
            metadata=metadata,
            user_id=USER_ID,
            agent_id=AGENT_ID,
        )
        if success:
            count += 1
        else:
            logger.warning("Failed to write: %s", key)

    return count


# ============================================================================
# Report
# ============================================================================

def print_report(report: Dict) -> None:
    """打印导入报告。"""
    print("\n" + "=" * 60)
    print("  Kaelis Dev Knowledge Ingestion Report")
    print("=" * 60)
    print(f"  Files scanned      : {report['files_scanned']}")
    print(f"  Files ingested     : {report['files_ingested']}")
    print(f"  Total memories     : {report['memories_written']}")
    print(f"  Failed writes      : {report['failed_writes']}")
    print(f"  Consolidation      : {report['consolidation']}")
    print(f"  Duration           : {report['duration_sec']:.2f}s")
    print("=" * 60 + "\n")


# ============================================================================
# Main
# ============================================================================

def main():
    start_time = time.time()
    logger.info("Starting knowledge ingestion...")

    mm = get_memory_manager()
    files = scan_source_files()
    logger.info("Found %d source files", len(files))

    memories_written = 0
    files_ingested = 0
    failed_writes = 0

    for idx, (file_path, doc_type) in enumerate(files, 1):
        try:
            count = ingest_file(mm, file_path, doc_type)
            if count > 0:
                files_ingested += 1
                memories_written += count
                logger.info("[%d/%d] Ingested %s (%d chunks)", idx, len(files), file_path.name, count)
            else:
                logger.debug("[%d/%d] Skipped empty: %s", idx, len(files), file_path.name)
        except Exception as e:
            failed_writes += 1
            logger.error("Failed to ingest %s: %s", file_path, e)

    # Consolidation
    logger.info("Running memory consolidation...")
    try:
        consolidator = MemoryConsolidator()
        result = consolidator.consolidate(dry_run=False)
        consolidation = f"dedup={result.get('deduplicated', 0)}, merged={result.get('merged', 0)}"
        logger.info("Consolidation complete: %s", consolidation)
    except Exception as e:
        consolidation = f"error: {e}"
        logger.error("Consolidation failed: %s", e)

    duration = time.time() - start_time

    report = {
        "files_scanned": len(files),
        "files_ingested": files_ingested,
        "memories_written": memories_written,
        "failed_writes": failed_writes,
        "consolidation": consolidation,
        "duration_sec": duration,
    }

    print_report(report)

    # Save report to L3 as well
    try:
        mm.write(
            layer="L3",
            key="dev_knowledge_ingestion_report",
            value=json.dumps(report, indent=2, ensure_ascii=False),
            metadata={
                "source": "scripts/ingest_dev_knowledge.py",
                "type": "system_report",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
            user_id=USER_ID,
            agent_id=AGENT_ID,
        )
    except Exception as e:
        logger.error("Failed to save report: %s", e)

    logger.info("Knowledge ingestion pipeline complete.")


if __name__ == "__main__":
    main()
