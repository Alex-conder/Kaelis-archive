"""
录制与回放 API 路由

提供屏幕录制和回放的 HTTP 接口。
"""

import logging
from flask import Blueprint, request, jsonify

# 导入录制器和播放器
try:
    from core.recorder import get_recorder
    from core.player import get_player
    RECORDER_AVAILABLE = True
except ImportError as e:
    RECORDER_AVAILABLE = False
    logging.warning(f"Recorder not available: {e}")

logger = logging.getLogger(__name__)

# 创建 Blueprint
recorder_bp = Blueprint('recorder', __name__, url_prefix='/api/recorder')

# 全局录制状态
_recording_status = {
    "is_recording": False,
    "current_session": None,
    "last_recording": None
}


@recorder_bp.route('/status', methods=['GET'])
def get_status():
    """获取录制状态"""
    return jsonify({
        "success": True,
        "data": _recording_status
    })


@recorder_bp.route('/start', methods=['POST'])
def start_recording():
    """
    开始录制
    
    Request Body:
        {
            "name": "录制名称",
            "description": "描述",
            "capture_screenshots": false
        }
    """
    if not RECORDER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Recorder not available"
        }), 503
    
    if _recording_status["is_recording"]:
        return jsonify({
            "success": False,
            "error": "Already recording"
        }), 409
    
    try:
        data = request.get_json() or {}
        
        recorder = get_recorder()
        
        session = recorder.start_recording(
            name=data.get('name', f'Recording_{int(time.time())}'),
            description=data.get('description', ''),
            capture_screenshots=data.get('capture_screenshots', False)
        )
        
        if session:
            _recording_status["is_recording"] = True
            _recording_status["current_session"] = {
                "id": session.id,
                "name": session.name,
                "started_at": session.created_at
            }
            
            return jsonify({
                "success": True,
                "data": {
                    "session_id": session.id,
                    "name": session.name,
                    "status": "recording"
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to start recording"
            }), 500
            
    except Exception as e:
        logger.error(f"Start recording failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@recorder_bp.route('/stop', methods=['POST'])
def stop_recording():
    """停止录制并保存"""
    if not RECORDER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Recorder not available"
        }), 503
    
    if not _recording_status["is_recording"]:
        return jsonify({
            "success": False,
            "error": "Not recording"
        }), 400
    
    try:
        recorder = get_recorder()
        
        session = recorder.stop_recording()
        
        if session:
            # 保存到文件
            filepath = recorder.save_recording(session)
            
            _recording_status["is_recording"] = False
            _recording_status["last_recording"] = {
                "id": session.id,
                "name": session.name,
                "filepath": filepath,
                "duration": session.duration,
                "actions_count": len(session.actions)
            }
            _recording_status["current_session"] = None
            
            return jsonify({
                "success": True,
                "data": {
                    "session_id": session.id,
                    "duration": session.duration,
                    "actions_count": len(session.actions),
                    "filepath": filepath
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to stop recording"
            }), 500
            
    except Exception as e:
        logger.error(f"Stop recording failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@recorder_bp.route('/recordings', methods=['GET'])
def list_recordings():
    """获取录制列表"""
    if not RECORDER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Recorder not available"
        }), 503
    
    try:
        recorder = get_recorder()
        recordings = recorder.list_recordings()
        
        return jsonify({
            "success": True,
            "data": {
                "recordings": recordings,
                "count": len(recordings)
            }
        })
        
    except Exception as e:
        logger.error(f"List recordings failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@recorder_bp.route('/recordings/<recording_id>', methods=['GET'])
def get_recording(recording_id):
    """获取单个录制详情"""
    if not RECORDER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Recorder not available"
        }), 503
    
    try:
        recorder = get_recorder()
        session = recorder.load_recording(recording_id)
        
        if not session:
            return jsonify({
                "success": False,
                "error": f"Recording {recording_id} not found"
            }), 404
        
        return jsonify({
            "success": True,
            "data": session.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Get recording failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@recorder_bp.route('/recordings/<recording_id>', methods=['DELETE'])
def delete_recording(recording_id):
    """删除录制"""
    try:
        from core.recorder import ScreenRecorder
        recorder = ScreenRecorder()
        
        filepath = recorder.save_dir / f"{recording_id}.json"
        
        if filepath.exists():
            filepath.unlink()
            return jsonify({
                "success": True,
                "message": f"Recording {recording_id} deleted"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Recording not found"
            }), 404
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@recorder_bp.route('/play/<recording_id>', methods=['POST'])
def play_recording(recording_id):
    """
    播放录制
    
    Request Body:
        {
            "speed": 1.0,
            "stop_on_error": false
        }
    """
    if not RECORDER_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "Player not available"
        }), 503
    
    try:
        data = request.get_json() or {}
        speed = data.get('speed', 1.0)
        stop_on_error = data.get('stop_on_error', False)
        
        # 加载录制
        recorder = get_recorder()
        session = recorder.load_recording(recording_id)
        
        if not session:
            return jsonify({
                "success": False,
                "error": f"Recording {recording_id} not found"
            }), 404
        
        # 播放（注意：这会在服务器端执行，可能不安全）
        # 实际生产环境应该只在客户端播放，或使用专门的工作节点
        
        return jsonify({
            "success": True,
            "message": "Playback started",
            "data": {
                "recording_id": recording_id,
                "speed": speed,
                "actions_count": len(session.actions)
            }
        })
        
    except Exception as e:
        logger.error(f"Play recording failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@recorder_bp.route('/convert-to-skill/<recording_id>', methods=['POST'])
def convert_to_skill(recording_id):
    """
    将录制转换为技能
    
    这允许将录制的操作序列封装为可复用的技能。
    """
    try:
        recorder = get_recorder()
        session = recorder.load_recording(recording_id)
        
        if not session:
            return jsonify({
                "success": False,
                "error": "Recording not found"
            }), 404
        
        # 创建技能
        from core.skill_manager import get_skill_manager
        skill_manager = get_skill_manager()
        
        skill = skill_manager.create_skill(
            name=f"录制技能: {session.name}",
            task_type="screen_automation",
            params={
                "recording_id": recording_id,
                "actions_count": len(session.actions),
                "duration": session.duration
            },
            workflow={"actions": [a.to_dict() for a in session.actions]},
            description=f"从录制 {session.id} 转换而来\n{session.description}",
            tags=["screen-recording", "automation"]
        )
        
        if skill:
            return jsonify({
                "success": True,
                "data": {
                    "skill_id": skill.id,
                    "name": skill.name,
                    "message": "Recording converted to skill"
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to create skill"
            }), 500
            
    except Exception as e:
        logger.error(f"Convert to skill failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# 导入 time 模块
import time


def register_recorder_routes(app):
    """注册录制路由到 Flask 应用"""
    app.register_blueprint(recorder_bp)
    logger.info("Recorder routes registered")


if __name__ == "__main__":
    from flask import Flask
    
    app = Flask(__name__)
    register_recorder_routes(app)
    
    print("Recorder routes registered:")
    for rule in app.url_map.iter_rules():
        if 'recorder' in str(rule):
            print(f"  {rule}")
