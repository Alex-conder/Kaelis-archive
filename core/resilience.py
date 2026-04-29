"""
弹性组件 — CircuitBreaker

为外部服务调用提供熔断保护。
"""

import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # 正常状态
    OPEN = "open"           # 熔断状态
    HALF_OPEN = "half_open" # 半开状态（试探）


class CircuitBreaker:
    """
    熔断器。

    - 连续 failure_threshold 次失败后熔断
    - 冷却 recovery_timeout 秒后进入半开状态
    - 半开状态下一次成功调用恢复关闭状态
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time and (time.time() - self._last_failure_time) >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"[CircuitBreaker:{self.name}] Recovery timeout reached, entering HALF_OPEN")
            return self._state

    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info(f"[CircuitBreaker:{self.name}] Recovered to CLOSED")

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"[CircuitBreaker:{self.name}] Tripped to OPEN after {self._failure_count} failures")

    def call(self, func: Callable, *args, **kwargs):
        """
        包装函数调用，自动记录成功/失败。
        若熔断器打开，直接抛出异常。
        """
        if self.is_open():
            raise Exception(f"CircuitBreaker [{self.name}] is OPEN")

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e


# 全局熔断器注册表
_circuit_breakers: dict = {}
_circuit_lock = threading.Lock()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """获取或创建指定名称的熔断器"""
    with _circuit_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, **kwargs)
        return _circuit_breakers[name]
