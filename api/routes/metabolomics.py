"""
代谢组学 API 路由

提供代谢组学分析的 HTTP 接口。
"""

import logging
import os
from flask import Blueprint, request, jsonify, current_app
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# 创建 Blueprint
metabolomics_bp = Blueprint('metabolomics', __name__, url_prefix='/api/metabolomics')

# 上传目录
UPLOAD_DIR = Path("data/uploads/metabolomics")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _is_safe_path(filepath: str) -> bool:
    """安全检查：只允许访问 UPLOAD_DIR 下的文件"""
    if not filepath:
        return False
    try:
        requested = Path(filepath).resolve()
        allowed = UPLOAD_DIR.resolve()
        return str(requested).startswith(str(allowed))
    except (OSError, ValueError):
        return False

# 惰性导入代谢组学模块，避免 scipy/matplotlib 等重型库在启动时阻塞
_metabolomics_loaded = False
_metabolomics_available = False
_MetabolomicsWorkflow = None
_quick_analyze = None
_get_file_summary = None


def _ensure_metabolomics():
    """延迟导入代谢组学模块"""
    global _metabolomics_loaded, _metabolomics_available
    global _MetabolomicsWorkflow, _quick_analyze, _get_file_summary
    if _metabolomics_loaded:
        return _metabolomics_available
    _metabolomics_loaded = True
    try:
        from core.metabolomics.workflow import MetabolomicsWorkflow, quick_analyze
        from core.metabolomics.mzml_parser import get_file_summary
        _MetabolomicsWorkflow = MetabolomicsWorkflow
        _quick_analyze = quick_analyze
        _get_file_summary = get_file_summary
        _metabolomics_available = True
    except Exception as e:
        logger.warning(f"Metabolomics module not available: {e}")
        _metabolomics_available = False
    return _metabolomics_available


@metabolomics_bp.route('/status', methods=['GET'])
def get_status():
    """获取代谢组学模块状态"""
    return jsonify({
        "success": True,
        "data": {
            "available": _ensure_metabolomics(),
            "upload_dir": str(UPLOAD_DIR),
            "supported_formats": [".mzML", ".mzml", ".mzXML"]
        }
    })


@metabolomics_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    上传mzML文件
    
    Returns:
        上传的文件信息
    """
    if not _ensure_metabolomics():
        return jsonify({
            "success": False,
            "error": "Metabolomics module not available"
        }), 503
    
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file provided"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "Empty filename"
            }), 400
        
        # 保存文件
        filepath = UPLOAD_DIR / file.filename
        file.save(str(filepath))
        
        # 获取文件摘要
        summary = _get_file_summary(str(filepath))
        
        return jsonify({
            "success": True,
            "data": {
                "filename": file.filename,
                "filepath": str(filepath),
                "summary": summary
            }
        })
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@metabolomics_bp.route('/files', methods=['GET'])
def list_files():
    """获取上传目录中的文件列表"""
    if not _ensure_metabolomics():
        return jsonify({
            "success": False,
            "error": "Metabolomics module not available"
        }), 503
    
    try:
        files = []
        for f in UPLOAD_DIR.iterdir():
            if f.is_file():
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime
                })
        return jsonify({
            "success": True,
            "data": {"files": files}
        })
    except Exception as e:
        logger.error(f"List files failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@metabolomics_bp.route('/analyze', methods=['POST'])
def analyze_file():
    """
    分析mzML文件
    
    Request Body:
        {
            "filepath": "文件路径",
            "sample_name": "样本名称（可选）",
            "detect_peaks": true,
            "max_spectra": 1000
        }
    
    Returns:
        分析结果
    """
    if not _ensure_metabolomics():
        return jsonify({
            "success": False,
            "error": "Metabolomics module not available"
        }), 503
    
    try:
        data = request.get_json() or {}
        filepath = data.get('filepath')
        
        # 路径安全检查
        if not _is_safe_path(filepath):
            return jsonify({
                "success": False,
                "error": "Invalid or unsafe file path"
            }), 403
        
        if not os.path.exists(filepath):
            return jsonify({
                "success": False,
                "error": "File not found"
            }), 404
        
        # 创建分析工作流
        workflow = _MetabolomicsWorkflow()
        
        # 分析文件
        result = workflow.analyze_file(
            filepath=filepath,
            sample_name=data.get('sample_name'),
            detect_peaks=data.get('detect_peaks', True),
            max_spectra=data.get('max_spectra')
        )
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@metabolomics_bp.route('/quick', methods=['POST'])
def quick_analyze_endpoint():
    """
    快速分析（简化版）
    
    Request Body:
        {
            "filepath": "文件路径"
        }
    
    Returns:
        简化分析结果
    """
    if not _ensure_metabolomics():
        return jsonify({
            "success": False,
            "error": "Metabolomics module not available"
        }), 503
    
    try:
        data = request.get_json() or {}
        filepath = data.get('filepath')
        
        # 路径安全检查
        if not _is_safe_path(filepath):
            return jsonify({
                "success": False,
                "error": "Invalid or unsafe file path"
            }), 403
        
        if not os.path.exists(filepath):
            return jsonify({
                "success": False,
                "error": "File not found"
            }), 404
        
        result = _quick_analyze(filepath)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Quick analysis failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@metabolomics_bp.route('/compare', methods=['POST'])
def compare_groups():
    """
    比较两组样本
    
    Request Body:
        {
            "feature_matrix": [...],
            "feature_ids": [...],
            "group_labels": [...],
            "group_names": ["Group A", "Group B"],
            "mz_values": [...],
            "rt_values": [...]
        }
    
    Returns:
        比较分析结果
    """
    if not _ensure_metabolomics():
        return jsonify({
            "success": False,
            "error": "Metabolomics module not available"
        }), 503
    
    try:
        data = request.get_json() or {}
        
        # 创建分析工作流
        workflow = _MetabolomicsWorkflow(use_evolution=False)
        
        result = workflow.compare_groups(
            feature_matrix=data.get('feature_matrix'),
            feature_ids=data.get('feature_ids'),
            group_labels=data.get('group_labels'),
            group_names=data.get('group_names', ['Group A', 'Group B']),
            mz_values=data.get('mz_values'),
            rt_values=data.get('rt_values')
        )
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
