"""
文件管理 API

为前端 FilePage 提供目录浏览、文件操作和语义搜索接口。
"""

import json
import os
import subprocess
from pathlib import Path

from flask import Blueprint, jsonify, request

from core.context.sensors.file_sensor import FileIndexer
from core.security.file_gateway import FileGateway, FileOperationRequest, FileOperationType

files_bp = Blueprint("files", __name__, url_prefix="/api/files")

_file_gateway = FileGateway()
_file_indexer = FileIndexer()


@files_bp.route("/browse", methods=["GET"])
def browse():
    """获取目录结构"""
    path = request.args.get("path", ".")
    try:
        target = Path(path).resolve()
        if not target.exists():
            return jsonify({"error": "Path not found"}), 404
        if not target.is_dir():
            return jsonify({"error": "Not a directory"}), 400

        items = []
        for child in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = child.stat()
                items.append({
                    "name": child.name,
                    "path": child.as_posix(),
                    "is_dir": child.is_dir(),
                    "size": stat.st_size if child.is_file() else 0,
                    "modified": stat.st_mtime,
                })
            except Exception:
                continue

        return jsonify({
            "path": target.as_posix(),
            "parent": target.parent.as_posix() if target.parent != target else None,
            "items": items,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/read", methods=["GET"])
def read_file():
    """读取文件内容"""
    path = request.args.get("path", "")
    try:
        target = Path(path).resolve()
        if not target.exists() or not target.is_file():
            return jsonify({"error": "File not found"}), 404
        if target.stat().st_size > 5 * 1024 * 1024:
            return jsonify({"error": "File too large (>5MB)"}), 413

        content = target.read_text(encoding="utf-8", errors="ignore")
        return jsonify({
            "path": target.as_posix(),
            "name": target.name,
            "content": content,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/rename", methods=["POST"])
def rename_file():
    """重命名文件/目录"""
    data = request.get_json() or {}
    old_path = data.get("old_path", "")
    new_name = data.get("new_name", "")
    try:
        target = Path(old_path).resolve()
        if not target.exists():
            return jsonify({"error": "Path not found"}), 404

        new_path = target.parent / new_name
        if new_path.exists():
            return jsonify({"error": "Target already exists"}), 409

        target.rename(new_path)
        return jsonify({"success": True, "new_path": new_path.as_posix()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/delete", methods=["POST"])
def delete_file():
    """删除文件/目录"""
    data = request.get_json() or {}
    path = data.get("path", "")
    try:
        target = Path(path).resolve()
        if not target.exists():
            return jsonify({"error": "Path not found"}), 404

        # 通过安全网关审批
        req = FileOperationRequest(
            source="web_ui",
            operation=FileOperationType.DELETE,
            file_path=str(target),
        )
        result = _file_gateway.evaluate(req)
        if not result.approved:
            return jsonify({
                "success": False,
                "requires_approval": True,
                "reason": result.reason,
                "approval_id": result.approval_id,
            }), 403

        if target.is_dir():
            import shutil
            shutil.rmtree(target)
        else:
            target.unlink()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/search", methods=["GET"])
def search_files():
    """语义搜索文件"""
    query = request.args.get("q", "")
    top_k = int(request.args.get("top_k", 5))
    try:
        results = _file_indexer.semantic_search(query, top_k=top_k)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/index", methods=["POST"])
def index_directory():
    """为目录建立语义索引"""
    data = request.get_json() or {}
    root = data.get("path", ".")
    recursive = data.get("recursive", True)
    try:
        stats = _file_indexer.index_directory(root, recursive=recursive)
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
