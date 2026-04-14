"""
代谢组学 API 路由

提供代谢组学分析的 HTTP 接口。
"""

import logging
import os
from flask import Blueprint, request, jsonify, current_app
from pathlib import Path
import json

# 导入代谢组学模块
try:
    from core.metabolomics.workflow import MetabolomicsWorkflow, quick_analyze
    from core.metabolomics.mzml_parser import get_file_summary
    METABOLOMICS_AVAILABLE = True
except ImportError as e:
    METABOLOMICS_AVAILABLE = False
    logging.warning(f"Metabolomics module not available: {e}")

logger = logging.getLogger(__name__)

# 创建 Blueprint
metabolomics_bp = Blueprint('metabolomics', __name__, url_prefix='/api/metabolomics')

# 上传目录
UPLOAD_DIR = Path("data/uploads/metabolomics")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@metabolomics_bp.route('/status', methods=['GET'])
def get_status():
    """获取代谢组学模块状态"""
    return jsonify({
        "success": True,
        "data": {
            "available": METABOLOMICS_AVAILABLE,
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
    if not METABOLOMICS_AVAILABLE:
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
                "error": "No file selected"
            }), 400
        
        # 保存文件
        filename = file.filename
        filepath = UPLOAD_DIR / filename
        file.save(filepath)
        
        # 获取文件摘要
        try:
            summary = get_file_summary(str(filepath))
        except Exception as e:
            summary = {"error": str(e)}
        
        return jsonify({
            "success": True,
            "data": {
                "filename": filename,
                "filepath": str(filepath),
                "size_mb": round(filepath.stat().st_size / (1024*1024), 2),
                "summary": summary
            }
        })
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
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
            "sample_name": "样本名称",
            "detect_peaks": true,
            "max_spectra": 1000
        }
    """
    if not METABOLOMICS_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Metabolomics module not available"
        }), 503
    
    try:
        data = request.get_json()
        
        if not data or 'filepath' not in data:
            return jsonify({
                "success": False,
                "error": "filepath is required"
            }), 400
        
        filepath = data['filepath']
        
        # 安全检查：确保文件在允许目录内
        if not str(filepath).startswith(str(UPLOAD_DIR)):
            return jsonify({
                "success": False,
                "error": "Invalid filepath"
            }), 403
        
        if not Path(filepath).exists():
            return jsonify({
                "success": False,
                "error": "File not found"
            }), 404
        
        # 执行分析
        workflow = MetabolomicsWorkflow()
        
        result = workflow.analyze_file(
            filepath=filepath,
            sample_name=data.get('sample_name'),
            detect_peaks=data.get('detect_peaks', True),
            max_spectra=data.get('max_spectra')
        )
        
        # 转换numpy数组为列表
        if hasattr(result.get('tic'), 'time'):
            result['tic'] = {
                'time': result['tic'].time.tolist()[:1000],  # 限制数据量
                'intensity': result['tic'].intensity.tolist()[:1000]
            }
        
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


@metabolomics_bp.route('/files', methods=['GET'])
def list_files():
    """列出已上传的文件"""
    try:
        files = []
        
        for filepath in UPLOAD_DIR.glob("*.mzML"):
            files.append({
                "filename": filepath.name,
                "size_mb": round(filepath.stat().st_size / (1024*1024), 2),
                "uploaded": filepath.stat().st_mtime
            })
        
        # 按时间排序
        files.sort(key=lambda x: x["uploaded"], reverse=True)
        
        return jsonify({
            "success": True,
            "data": {
                "files": files,
                "count": len(files)
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@metabolomics_bp.route('/quick-test', methods=['GET'])
def quick_test():
    """
    快速测试：分析本地已知的mzML文件
    
    用于演示和测试。
    """
    if not METABOLOMICS_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Metabolomics module not available"
        }), 503
    
    # 测试文件
    test_file = r"D:\1250205_NEG_B44 (4).mzML"
    
    if not Path(test_file).exists():
        return jsonify({
            "success": False,
            "error": f"Test file not found: {test_file}"
        }), 404
    
    try:
        logger.info(f"Running quick test on: {test_file}")
        
        workflow = MetabolomicsWorkflow(use_evolution=False)
        
        # 只解析前50个谱图（快速测试）
        result = workflow.analyze_file(
            filepath=test_file,
            sample_name="Test_NEG_B44",
            detect_peaks=True,
            max_spectra=50
        )
        
        # 简化输出
        simplified = {
            'sample_name': result['sample_name'],
            'file_info': result['file_info'],
            'n_peaks': len(result['peaks']),
            'has_chromatogram_plot': bool(result.get('chromatogram_plot')),
            'peaks_preview': result['peaks'][:5] if result['peaks'] else []
        }
        
        return jsonify({
            "success": True,
            "data": simplified,
            "message": "Quick test completed successfully"
        })
        
    except Exception as e:
        logger.error(f"Quick test failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def register_metabolomics_routes(app):
    """注册代谢组学路由到 Flask 应用"""
    app.register_blueprint(metabolomics_bp)
    logger.info("Metabolomics routes registered")


if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    register_metabolomics_routes(app)
    
    print("Metabolomics routes registered:")
    for rule in app.url_map.iter_rules():
        if 'metabolomics' in str(rule):
            print(f"  {rule}")
