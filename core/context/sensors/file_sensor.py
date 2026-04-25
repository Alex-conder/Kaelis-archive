"""
File Change Sensor (Prompt 3)

Monitors a directory for recently modified files.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.context.sensor_base import BaseContextSensor

logger = logging.getLogger(__name__)

WATCHDOG_AVAILABLE = False
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    logger.warning("watchdog not installed. FileChangeSensor will use os.stat polling.")


SENSITIVE_PATTERNS = (".env", "secret", "password", "credential", "token", ".key")
MONITORED_EXTENSIONS = (".py", ".md", ".csv")


class _ChangeHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """Watchdog event handler (only defined if watchdog is available)."""

    def __init__(self):
        self.recent_changes: List[str] = []

    def on_modified(self, event):
        if not event.is_directory:
            self.recent_changes.append(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self.recent_changes.append(event.src_path)


class FileChangeSensor(BaseContextSensor):
    """
    Detects files modified in the last 5 minutes within a monitored directory.
    Filters sensitive file paths.
    """

    def __init__(self, sensor_id: str = "file_change", privacy_level: str = "internal", watch_dir: Optional[str] = None):
        super().__init__(sensor_id, privacy_level)
        self.watch_dir = Path(watch_dir) if watch_dir else Path(".")
        self._observer: Any = None
        self._handler: Any = None
        if WATCHDOG_AVAILABLE:
            self._handler = _ChangeHandler()
            self._observer = Observer()
            try:
                self._observer.schedule(self._handler, str(self.watch_dir), recursive=True)
                self._observer.start()
                logger.info(f"FileChangeSensor watching {self.watch_dir}")
            except Exception as e:
                logger.warning(f"Failed to start watchdog observer: {e}")
                self._observer = None

    def collect(self) -> Dict[str, Any]:
        """Collect recently modified files (last 5 minutes)."""
        cutoff = time.time() - 300  # 5 minutes
        changed_files = []

        if WATCHDOG_AVAILABLE and self._observer and self._handler:
            # Use watchdog recent changes + validate they are within cutoff
            for path in self._handler.recent_changes:
                try:
                    mtime = os.path.getmtime(path)
                    if mtime >= cutoff:
                        changed_files.append(Path(path))
                except OSError:
                    continue
            self._handler.recent_changes.clear()
        else:
            # Fallback: os.stat walk
            for root, _dirs, files in os.walk(self.watch_dir):
                for fname in files:
                    if not fname.endswith(MONITORED_EXTENSIONS):
                        continue
                    fpath = Path(root) / fname
                    try:
                        mtime = fpath.stat().st_mtime
                        if mtime >= cutoff:
                            changed_files.append(fpath)
                    except OSError:
                        continue

        # Deduplicate and sort by mtime desc
        seen = set()
        unique = []
        for fpath in sorted(changed_files, key=lambda p: p.stat().st_mtime, reverse=True):
            rp = str(fpath.resolve())
            if rp not in seen:
                seen.add(rp)
                unique.append(fpath)

        return {
            "watch_dir": str(self.watch_dir),
            "changed_files": [str(f) for f in unique[:50]],
            "total_changed": len(unique),
        }

    def filter_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive file paths from results."""
        filtered = []
        for path in data.get("changed_files", []):
            lower = path.lower()
            if any(pat in lower for pat in SENSITIVE_PATTERNS):
                continue
            filtered.append(path)
        return {
            "watch_dir": data.get("watch_dir"),
            "changed_files": filtered,
            "total_changed": len(filtered),
        }

    def stop(self):
        """Stop the watchdog observer if running."""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join()
            except Exception as e:
                logger.warning(f"Error stopping observer: {e}")
