"""
屏幕录制器 - Screen Recorder

功能：
1. 录制全局鼠标事件（点击、移动、滚动）
2. 录制键盘事件
3. 截图锚点记录
4. 操作序列保存为 JSON
"""

import json
import logging
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# 尝试导入 pynput
try:
    from pynput import mouse, keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    logger.warning("pynput not installed, recorder functionality limited")

try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class RecordedAction:
    """录制的单个动作"""
    type: str  # mouse_click, mouse_move, key_press, scroll, delay, screenshot
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data
        }


@dataclass
class RecordingSession:
    """录制会话"""
    id: str
    name: str
    description: str
    created_at: str
    actions: List[RecordedAction] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "actions": [a.to_dict() for a in self.actions],
            "screenshots": self.screenshots,
            "duration": self.duration
        }
    
    @property
    def duration(self) -> float:
        if not self.actions:
            return 0.0
        return self.actions[-1].timestamp - self.actions[0].timestamp


class ScreenRecorder:
    """
    屏幕录制器
    
    录制用户操作序列，用于后续回放。
    """
    
    def __init__(self, save_dir: str = "data/recordings"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        self.is_recording = False
        self.current_session: Optional[RecordingSession] = None
        self.start_time: Optional[float] = None
        
        # 监听器
        self.mouse_listener = None
        self.keyboard_listener = None
        
        # 回调
        self.on_action: Optional[Callable] = None
        
        logger.info(f"ScreenRecorder initialized (save_dir: {save_dir})")
    
    def start_recording(
        self,
        name: str,
        description: str = "",
        capture_screenshots: bool = False
    ) -> Optional[RecordingSession]:
        """
        开始录制
        
        Args:
            name: 录制名称
            description: 描述
            capture_screenshots: 是否截取屏幕锚点
            
        Returns:
            RecordingSession: 录制会话对象
        """
        if not PYNPUT_AVAILABLE:
            logger.error("pynput not available, cannot start recording")
            return None
        
        if self.is_recording:
            logger.warning("Already recording, stop current session first")
            return None
        
        # 生成会话ID
        session_id = f"rec_{int(time.time())}"
        
        self.current_session = RecordingSession(
            id=session_id,
            name=name,
            description=description,
            created_at=datetime.now().isoformat()
        )
        
        self.start_time = time.time()
        self.is_recording = True
        
        # 启动监听器
        self._start_listeners()
        
        # 可选：截取初始屏幕
        if capture_screenshots and PIL_AVAILABLE:
            self._capture_screenshot("start")
        
        logger.info(f"Recording started: {session_id}")
        return self.current_session
    
    def stop_recording(self) -> Optional[RecordingSession]:
        """
        停止录制
        
        Returns:
            RecordingSession: 录制的会话
        """
        if not self.is_recording:
            logger.warning("Not recording")
            return None
        
        # 停止监听器
        self._stop_listeners()
        
        self.is_recording = False
        
        # 添加结束标记
        if self.current_session:
            self.current_session.actions.append(RecordedAction(
                type="stop",
                timestamp=time.time() - self.start_time,
                data={}
            ))
        
        logger.info(f"Recording stopped: {len(self.current_session.actions)} actions")
        return self.current_session
    
    def save_recording(self, session: RecordingSession = None) -> Optional[str]:
        """
        保存录制到文件
        
        Args:
            session: 要保存的会话（默认当前会话）
            
        Returns:
            str: 保存的文件路径
        """
        session = session or self.current_session
        if not session:
            return None
        
        filepath = self.save_dir / f"{session.id}.json"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Recording saved: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return None
    
    def load_recording(self, session_id: str) -> Optional[RecordingSession]:
        """加载录制"""
        filepath = self.save_dir / f"{session_id}.json"
        
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            session = RecordingSession(
                id=data["id"],
                name=data["name"],
                description=data["description"],
                created_at=data["created_at"],
                actions=[RecordedAction(**a) for a in data["actions"]],
                screenshots=data.get("screenshots", [])
            )
            
            return session
        except Exception as e:
            logger.error(f"Failed to load recording: {e}")
            return None
    
    def list_recordings(self) -> List[Dict[str, Any]]:
        """列出所有录制"""
        recordings = []
        
        for filepath in self.save_dir.glob("*.json"):
            try:
                session = self.load_recording(filepath.stem)
                if session:
                    recordings.append({
                        "id": session.id,
                        "name": session.name,
                        "description": session.description,
                        "created_at": session.created_at,
                        "duration": session.duration,
                        "actions_count": len(session.actions)
                    })
            except Exception as e:
                logger.debug(f"Failed to load {filepath}: {e}")
        
        # 按时间倒序
        recordings.sort(key=lambda x: x["created_at"], reverse=True)
        return recordings
    
    def _start_listeners(self):
        """启动鼠标和键盘监听器"""
        if not PYNPUT_AVAILABLE:
            return
        
        # 鼠标监听器
        self.mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll
        )
        self.mouse_listener.start()
        
        # 键盘监听器
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.keyboard_listener.start()
    
    def _stop_listeners(self):
        """停止监听器"""
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
    
    def _on_mouse_move(self, x, y):
        """鼠标移动事件"""
        if not self.is_recording:
            return
        
        # 限制记录频率（每100ms最多一次）
        if self.current_session.actions:
            last_action = self.current_session.actions[-1]
            if (last_action.type == "mouse_move" and 
                time.time() - self.start_time - last_action.timestamp < 0.1):
                return
        
        action = RecordedAction(
            type="mouse_move",
            timestamp=time.time() - self.start_time,
            data={"x": x, "y": y}
        )
        self.current_session.actions.append(action)
        
        if self.on_action:
            self.on_action(action)
    
    def _on_mouse_click(self, x, y, button, pressed):
        """鼠标点击事件"""
        if not self.is_recording:
            return
        
        action = RecordedAction(
            type="mouse_click",
            timestamp=time.time() - self.start_time,
            data={
                "x": x,
                "y": y,
                "button": str(button),
                "pressed": pressed
            }
        )
        self.current_session.actions.append(action)
        
        logger.debug(f"Mouse click: ({x}, {y}) {button} {'pressed' if pressed else 'released'}")
        
        if self.on_action:
            self.on_action(action)
    
    def _on_mouse_scroll(self, x, y, dx, dy):
        """鼠标滚动事件"""
        if not self.is_recording:
            return
        
        action = RecordedAction(
            type="mouse_scroll",
            timestamp=time.time() - self.start_time,
            data={"x": x, "y": y, "dx": dx, "dy": dy}
        )
        self.current_session.actions.append(action)
    
    def _on_key_press(self, key):
        """键盘按下事件"""
        if not self.is_recording:
            return
        
        try:
            key_str = key.char
        except AttributeError:
            key_str = str(key)
        
        action = RecordedAction(
            type="key_press",
            timestamp=time.time() - self.start_time,
            data={"key": key_str}
        )
        self.current_session.actions.append(action)
        
        logger.debug(f"Key press: {key_str}")
        
        if self.on_action:
            self.on_action(action)
    
    def _on_key_release(self, key):
        """键盘释放事件"""
        pass  # 通常不需要记录释放事件
    
    def _capture_screenshot(self, tag: str = ""):
        """截取屏幕"""
        if not PIL_AVAILABLE:
            return
        
        try:
            screenshot_dir = self.save_dir / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            
            filename = f"{self.current_session.id}_{tag}_{int(time.time())}.png"
            filepath = screenshot_dir / filename
            
            screenshot = ImageGrab.grab()
            screenshot.save(filepath)
            
            self.current_session.screenshots.append(str(filepath))
            logger.debug(f"Screenshot saved: {filepath}")
            
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")


# 全局实例
_recorder: Optional[ScreenRecorder] = None


def get_recorder() -> ScreenRecorder:
    """获取全局录制器实例"""
    global _recorder
    if _recorder is None:
        _recorder = ScreenRecorder()
    return _recorder


if __name__ == "__main__":
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试屏幕录制器 ===")
    
    recorder = ScreenRecorder()
    
    if not PYNPUT_AVAILABLE:
        print("❌ pynput not installed, skipping test")
        exit(0)
    
    # 开始录制
    session = recorder.start_recording(
        name="测试录制",
        description="用于测试的录制"
    )
    
    if session:
        print(f"开始录制: {session.id}")
        print("请在5秒内进行一些鼠标和键盘操作...")
        
        time.sleep(5)
        
        # 停止
        recorder.stop_recording()
        
        # 保存
        filepath = recorder.save_recording()
        print(f"录制已保存: {filepath}")
        print(f"共 {len(session.actions)} 个动作")
        
        # 列出录制
        recordings = recorder.list_recordings()
        print(f"\n所有录制 ({len(recordings)} 个):")
        for rec in recordings[:5]:
            print(f"  - {rec['name']}: {rec['actions_count']} 动作, {rec['duration']:.1f}s")
