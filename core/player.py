"""
操作播放器 - Action Player

功能：
1. 回放录制的操作序列
2. 支持图像识别定位
3. 速度控制（倍速/慢速）
4. 失败重试机制
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Callable, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# pyautogui 采用延迟导入，避免模块级导入在 headless/CI 环境阻塞
_pyautogui_mod = None


def _get_pyautogui():
    """延迟导入并返回 pyautogui 模块"""
    global _pyautogui_mod
    if _pyautogui_mod is None:
        import pyautogui
        pyautogui.FAILSAFE = True
        _pyautogui_mod = pyautogui
    return _pyautogui_mod


def _pyautogui_available() -> bool:
    try:
        _get_pyautogui()
        return True
    except ImportError:
        return False


try:
    from PIL import ImageGrab, Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class ActionPlayer:
    """
    操作播放器
    
    回放录制的操作序列。
    """
    
    def __init__(self):
        self.is_playing = False
        self.current_action_index = 0
        self.speed_multiplier = 1.0
        self.on_action: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # 配置
        self.retry_count = 3
        self.retry_delay = 1.0
        self.image_match_threshold = 0.8
        
        logger.info("ActionPlayer initialized")
    
    def play_recording(
        self,
        recording_data: Dict[str, Any],
        speed: float = 1.0,
        stop_on_error: bool = False
    ) -> bool:
        """
        播放录制
        
        Args:
            recording_data: 录制数据（从 JSON 加载）
            speed: 播放速度倍率（1.0 = 正常, 2.0 = 2倍速, 0.5 = 慢速）
            stop_on_error: 出错时停止
            
        Returns:
            bool: 是否成功完成
        """
        if not _pyautogui_available():
            logger.error("pyautogui not available, cannot play")
            return False
        
        actions = recording_data.get("actions", [])
        if not actions:
            logger.warning("No actions to play")
            return False
        
        self.is_playing = True
        self.speed_multiplier = speed
        self.current_action_index = 0
        
        logger.info(f"Starting playback: {len(actions)} actions at {speed}x speed")
        
        try:
            last_timestamp = 0
            
            for i, action_data in enumerate(actions):
                if not self.is_playing:
                    logger.info("Playback stopped by user")
                    return False
                
                self.current_action_index = i
                
                action_type = action_data.get("type")
                action_timestamp = action_data.get("timestamp", 0)
                action_data_dict = action_data.get("data", {})
                
                # 计算延迟
                delay = (action_timestamp - last_timestamp) / speed
                if delay > 0:
                    time.sleep(delay)
                
                last_timestamp = action_timestamp
                
                # 执行动作
                success = self._execute_action(action_type, action_data_dict)
                
                if not success:
                    logger.error(f"Action {i} failed: {action_type}")
                    if stop_on_error:
                        return False
                    # 否则继续
                
                if self.on_action:
                    self.on_action(i, action_type, success)
            
            logger.info("Playback completed")
            if self.on_complete:
                self.on_complete()
            
            return True
            
        except Exception as e:
            logger.error(f"Playback error: {e}")
            if self.on_error:
                self.on_error(e)
            return False
        finally:
            self.is_playing = False
    
    def stop(self):
        """停止播放"""
        self.is_playing = False
        logger.info("Playback stop requested")
    
    def _execute_action(self, action_type: str, data: Dict[str, Any]) -> bool:
        """执行单个动作"""
        try:
            if action_type == "mouse_click":
                return self._execute_mouse_click(data)
            elif action_type == "mouse_move":
                return self._execute_mouse_move(data)
            elif action_type == "mouse_scroll":
                return self._execute_mouse_scroll(data)
            elif action_type == "key_press":
                return self._execute_key_press(data)
            elif action_type == "delay":
                return self._execute_delay(data)
            elif action_type == "stop":
                return True
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Execute action failed: {e}")
            return False
    
    def _execute_mouse_click(self, data: Dict[str, Any]) -> bool:
        """执行鼠标点击"""
        pg = _get_pyautogui()
        x = data.get("x", 0)
        y = data.get("y", 0)
        button_str = data.get("button", "Button.left")
        pressed = data.get("pressed", True)
        
        # 解析按钮
        button = getattr(pg, button_str.split(".")[-1], pg.left)
        
        # 移动并点击
        pg.moveTo(x, y, duration=0.1)
        
        if pressed:
            pg.mouseDown(button=button)
            pg.mouseUp(button=button)
        
        logger.debug(f"Mouse click at ({x}, {y})")
        return True
    
    def _execute_mouse_move(self, data: Dict[str, Any]) -> bool:
        """执行鼠标移动"""
        pg = _get_pyautogui()
        x = data.get("x", 0)
        y = data.get("y", 0)
        
        pg.moveTo(x, y, duration=0.1)
        return True
    
    def _execute_mouse_scroll(self, data: Dict[str, Any]) -> bool:
        """执行鼠标滚动"""
        pg = _get_pyautogui()
        dy = data.get("dy", 0)
        dx = data.get("dx", 0)
        
        pg.scroll(int(dy), int(dx))
        return True
    
    def _execute_key_press(self, data: Dict[str, Any]) -> bool:
        """执行按键"""
        pg = _get_pyautogui()
        key = data.get("key", "")
        
        if not key:
            return False
        
        # 处理特殊键
        special_keys = {
            "Key.enter": "enter",
            "Key.space": "space",
            "Key.tab": "tab",
            "Key.esc": "esc",
            "Key.backspace": "backspace",
            "Key.delete": "delete",
            "Key.up": "up",
            "Key.down": "down",
            "Key.left": "left",
            "Key.right": "right",
            "Key.shift": "shift",
            "Key.ctrl": "ctrl",
            "Key.alt": "alt",
            "Key.cmd": "win"
        }
        
        if key in special_keys:
            pg.press(special_keys[key])
        elif len(key) == 1:
            pg.press(key)
        else:
            # 尝试直接写入
            pg.typewrite(key, interval=0.01)
        
        logger.debug(f"Key press: {key}")
        return True
    
    def _execute_delay(self, data: Dict[str, Any]) -> bool:
        """执行延迟"""
        seconds = data.get("seconds", 1)
        time.sleep(seconds)
        return True
    
    def click_on_image(
        self,
        image_path: str,
        confidence: float = 0.9,
        retries: int = 3
    ) -> bool:
        """
        在屏幕上查找图像并点击
        
        Args:
            image_path: 图像文件路径
            confidence: 匹配置信度
            retries: 重试次数
            
        Returns:
            bool: 是否成功
        """
        if not _pyautogui_available() or not PIL_AVAILABLE:
            logger.error("Required libraries not available")
            return False
        
        pg = _get_pyautogui()
        for attempt in range(retries):
            try:
                location = pg.locateOnScreen(
                    image_path,
                    confidence=confidence
                )
                
                if location:
                    center = pg.center(location)
                    pg.click(center)
                    logger.info(f"Clicked on image at {center}")
                    return True
                else:
                    logger.debug(f"Image not found (attempt {attempt + 1})")
                    if attempt < retries - 1:
                        time.sleep(1)
                    
            except Exception as e:
                logger.debug(f"Image search error: {e}")
        
        logger.error(f"Failed to find and click image after {retries} attempts")
        return False
    
    def wait_for_image(
        self,
        image_path: str,
        timeout: float = 10.0,
        confidence: float = 0.9
    ) -> bool:
        """
        等待图像出现在屏幕上
        
        Args:
            image_path: 图像文件路径
            timeout: 超时时间（秒）
            confidence: 匹配置信度
            
        Returns:
            bool: 是否找到
        """
        if not _pyautogui_available():
            return False
        
        pg = _get_pyautogui()
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                location = pg.locateOnScreen(
                    image_path,
                    confidence=confidence
                )
                if location:
                    return True
            except Exception:
                pass
            
            time.sleep(0.5)
        
        return False
    
    def play_with_image_fallback(
        self,
        recording_data: Dict[str, Any],
        fallback_images: Dict[int, str] = None
    ) -> bool:
        """
        播放录制，特定动作失败时使用图像定位回退
        
        Args:
            recording_data: 录制数据
            fallback_images: 动作索引到图像路径的映射
            
        Returns:
            bool: 是否成功
        """
        actions = recording_data.get("actions", [])
        fallback_images = fallback_images or {}
        
        for i, action_data in enumerate(actions):
            success = self._execute_action(
                action_data.get("type"),
                action_data.get("data", {})
            )
            
            if not success and i in fallback_images:
                logger.info(f"Trying image fallback for action {i}")
                success = self.click_on_image(fallback_images[i])
            
            if not success:
                logger.error(f"Action {i} failed even with fallback")
        
        return True


# 增强型播放器，与自进化引擎集成
class AdaptivePlayer(ActionPlayer):
    """
    自适应播放器
    
    能够根据失败情况调整参数（与自进化引擎集成）。
    """
    
    def __init__(self):
        super().__init__()
        self.failure_history: List[Dict] = []
        self.adaptive_params = {
            "click_delay": 0.1,
            "move_duration": 0.2,
            "retry_delay": 1.0
        }
    
    def adjust_for_failure(self, action_index: int, error: Exception):
        """
        根据失败调整参数
        
        这是与自进化引擎集成的关键方法。
        """
        self.failure_history.append({
            "action_index": action_index,
            "error": str(error),
            "timestamp": time.time()
        })
        
        # 简单启发式调整
        if "timeout" in str(error).lower():
            self.adaptive_params["retry_delay"] *= 1.5
            logger.info(f"Increased retry delay to {self.adaptive_params['retry_delay']}")
        
        elif "not found" in str(error).lower():
            self.adaptive_params["click_delay"] += 0.1
            logger.info(f"Increased click delay to {self.adaptive_params['click_delay']}")
    
    def get_optimized_params(self) -> Dict[str, Any]:
        """获取优化后的参数，可用于保存为技能"""
        return {
            "adaptive_params": self.adaptive_params,
            "failure_count": len(self.failure_history),
            "adjustments": self.failure_history
        }


# 全局实例
_player: Optional[ActionPlayer] = None


def get_player() -> ActionPlayer:
    """获取全局播放器实例"""
    global _player
    if _player is None:
        _player = AdaptivePlayer()
    return _player


if __name__ == "__main__":
    from core.logging_config import init_logging
    init_logging()
    
    print("=== 测试操作播放器 ===")
    
    if not _pyautogui_available():
        print("❌ pyautogui not installed, skipping test")
        exit(0)
    
    player = ActionPlayer()
    
    # 测试录制数据
    test_recording = {
        "actions": [
            {"type": "mouse_move", "timestamp": 0, "data": {"x": 500, "y": 300}},
            {"type": "mouse_click", "timestamp": 0.5, "data": {"x": 500, "y": 300, "button": "Button.left", "pressed": True}},
            {"type": "key_press", "timestamp": 1.0, "data": {"key": "a"}},
            {"type": "delay", "timestamp": 1.5, "data": {"seconds": 0.5}},
            {"type": "stop", "timestamp": 2.0, "data": {}}
        ]
    }
    
    print("\n测试播放 (2倍速)...")
    print("⚠️ 将鼠标移到屏幕角落可停止")
    
    # 实际播放（谨慎运行）
    # player.play_recording(test_recording, speed=2.0)
    
    print("测试完成")
