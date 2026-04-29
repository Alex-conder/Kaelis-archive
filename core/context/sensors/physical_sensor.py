"""
Physical AI Sensor — Context Sensor for NVIDIA Isaac Sim & Omniverse

为 NVIDIA 物理 AI 生态（Isaac Sim、Omniverse Digital Twin）提供统一传感器接口，
将仿真/数字孪生世界的实时状态注入 Kaelis 记忆系统。

用法：
    from core.context.sensors.physical_sensor import IsaacSimSensor
    sensor = IsaacSimSensor(usd_path="/path/to/scene.usd")
    state = sensor.get_robot_state()
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.context.sensor_base import BaseContextSensor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional NVIDIA SDK availability flags
# ---------------------------------------------------------------------------
OMNI_AVAILABLE = False
try:
    import omni
    OMNI_AVAILABLE = True
except ImportError:
    logger.debug("omni kit not available. OmniverseSensor will run in mock mode.")

ISAAC_AVAILABLE = False
try:
    from omni.isaac.core import World
    ISAAC_AVAILABLE = True
except ImportError:
    logger.debug("omni.isaac.core not available. IsaacSimSensor will run in mock mode.")


# ---------------------------------------------------------------------------
# Abstract Physical Sensor
# ---------------------------------------------------------------------------

class PhysicalSensor(BaseContextSensor, ABC):
    """
    物理世界传感器抽象基类。

    采集目标：
        - 空间几何数据（位置、姿态、速度）
        - 机器人本体状态（关节角、力矩、传感器读数）
        - 数字孪生体状态（USD 属性、实时变换）
    """

    @abstractmethod
    def collect_spatial_data(self) -> Dict[str, Any]:
        """采集空间/几何数据。"""
        ...

    @abstractmethod
    def get_robot_state(self) -> Dict[str, Any]:
        """获取机器人本体状态。"""
        ...

    @abstractmethod
    def get_digital_twin_state(self) -> Dict[str, Any]:
        """获取数字孪生体状态。"""
        ...

    def collect(self) -> Dict[str, Any]:
        """
        BaseContextSensor 接口实现：聚合三类物理数据。
        """
        return {
            "spatial": self.collect_spatial_data(),
            "robot": self.get_robot_state(),
            "digital_twin": self.get_digital_twin_state(),
            "sensor_type": self.__class__.__name__,
        }

    def filter_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """默认不过滤物理数据（通常不含 PII）。"""
        return data


# ---------------------------------------------------------------------------
# Isaac Sim Sensor
# ---------------------------------------------------------------------------

class IsaacSimSensor(PhysicalSensor):
    """
    NVIDIA Isaac Sim 传感器。

    在 Isaac Sim 仿真环境中读取机器人 prim 的状态。
    若 Isaac Sim SDK 不可用，退化为 Mock 模式（返回预设/随机数据）。
    """

    def __init__(
        self,
        robot_prim_path: str = "/World/robot",
        usd_path: Optional[str] = None,
        sim_app: Optional[Any] = None,
    ):
        self.robot_prim_path = robot_prim_path
        self.usd_path = usd_path
        self._sim_app = sim_app
        self._world: Optional[Any] = None
        self._mock_mode = not ISAAC_AVAILABLE

        if not self._mock_mode:
            try:
                self._world = World() if sim_app is None else sim_app
            except Exception as e:
                logger.warning("IsaacSimSensor failed to acquire World: %s. Falling back to mock.", e)
                self._mock_mode = True

    def collect_spatial_data(self) -> Dict[str, Any]:
        if self._mock_mode:
            return self._mock_spatial()
        try:
            prim = self._world.scene.get_object(self.robot_prim_path)
            pos, ori = prim.get_world_pose()
            return {
                "position": pos.tolist() if hasattr(pos, "tolist") else list(pos),
                "orientation": ori.tolist() if hasattr(ori, "tolist") else list(ori),
                "timestamp": __import__("time").time(),
            }
        except Exception as e:
            logger.warning("IsaacSim spatial read failed: %s", e)
            return self._mock_spatial()

    def get_robot_state(self) -> Dict[str, Any]:
        if self._mock_mode:
            return self._mock_robot()
        try:
            prim = self._world.scene.get_object(self.robot_prim_path)
            joints = prim.get_joint_positions() if hasattr(prim, "get_joint_positions") else []
            return {
                "joint_positions": joints.tolist() if hasattr(joints, "tolist") else list(joints),
                "prim_path": self.robot_prim_path,
                "timestamp": __import__("time").time(),
            }
        except Exception as e:
            logger.warning("IsaacSim robot state read failed: %s", e)
            return self._mock_robot()

    def get_digital_twin_state(self) -> Dict[str, Any]:
        # Isaac Sim 场景中 robot prim 自身就是数字孪生体
        return {
            "prim_path": self.robot_prim_path,
            "usd_path": self.usd_path,
            "simulator": "isaac_sim",
            "mock": self._mock_mode,
        }

    def _mock_spatial(self) -> Dict[str, Any]:
        import random
        return {
            "position": [round(random.uniform(-5, 5), 3) for _ in range(3)],
            "orientation": [0.0, 0.0, 0.0, 1.0],
            "timestamp": __import__("time").time(),
            "mock": True,
        }

    def _mock_robot(self) -> Dict[str, Any]:
        import random
        return {
            "joint_positions": [round(random.uniform(-1.57, 1.57), 3) for _ in range(6)],
            "prim_path": self.robot_prim_path,
            "timestamp": __import__("time").time(),
            "mock": True,
        }


# ---------------------------------------------------------------------------
# Omniverse Sensor
# ---------------------------------------------------------------------------

class OmniverseSensor(PhysicalSensor):
    """
    NVIDIA Omniverse Digital Twin 传感器。

    读取 Omniverse Nucleus 或本地 USD 场景中的数字孪生体状态。
    若 Omniverse SDK 不可用，退化为 Mock 模式。
    """

    def __init__(
        self,
        nucleus_url: Optional[str] = None,
        usd_path: Optional[str] = None,
        prim_path: str = "/World/DigitalTwin",
    ):
        self.nucleus_url = nucleus_url
        self.usd_path = usd_path
        self.prim_path = prim_path
        self._stage: Optional[Any] = None
        self._mock_mode = not OMNI_AVAILABLE

        if not self._mock_mode:
            try:
                from pxr import Usd
                # 尝试打开本地 USD 文件
                if usd_path:
                    self._stage = Usd.Stage.Open(usd_path)
            except Exception as e:
                logger.warning("OmniverseSensor failed to open stage: %s. Mock mode.", e)
                self._mock_mode = True

    def collect_spatial_data(self) -> Dict[str, Any]:
        if self._mock_mode:
            return self._mock_spatial()
        try:
            from pxr import Gf
            prim = self._stage.GetPrimAtPath(self.prim_path)
            xform = prim.GetAttribute("xformOp:transform")
            if xform:
                m = xform.Get()
                return {
                    "translation": list(m.ExtractTranslation()),
                    "rotation": list(m.ExtractRotation().GetQuaternion().GetImaginary()) + [m.ExtractRotation().GetQuaternion().GetReal()],
                    "timestamp": __import__("time").time(),
                }
            return self._mock_spatial()
        except Exception as e:
            logger.warning("Omniverse spatial read failed: %s", e)
            return self._mock_spatial()

    def get_robot_state(self) -> Dict[str, Any]:
        # Omniverse 场景不保证存在 robot，返回数字孪生体元数据
        return {
            "prim_path": self.prim_path,
            "has_physics": False,
            "simulator": "omniverse",
            "mock": self._mock_mode,
        }

    def get_digital_twin_state(self) -> Dict[str, Any]:
        if self._mock_mode:
            return self._mock_twin()
        try:
            prim = self._stage.GetPrimAtPath(self.prim_path)
            attrs = {}
            for attr in prim.GetAttributes():
                try:
                    attrs[attr.GetName()] = str(attr.Get())
                except Exception:
                    pass
            return {
                "prim_path": self.prim_path,
                "type_name": prim.GetTypeName(),
                "attributes": attrs,
                "usd_path": self.usd_path,
                "nucleus_url": self.nucleus_url,
                "timestamp": __import__("time").time(),
            }
        except Exception as e:
            logger.warning("Omniverse twin state read failed: %s", e)
            return self._mock_twin()

    def _mock_spatial(self) -> Dict[str, Any]:
        import random
        return {
            "translation": [round(random.uniform(-10, 10), 3) for _ in range(3)],
            "rotation": [0.0, 0.0, 0.0, 1.0],
            "timestamp": __import__("time").time(),
            "mock": True,
        }

    def _mock_twin(self) -> Dict[str, Any]:
        return {
            "prim_path": self.prim_path,
            "type_name": "Xform",
            "attributes": {"mock": "true"},
            "usd_path": self.usd_path,
            "nucleus_url": self.nucleus_url,
            "mock": True,
        }


# ---------------------------------------------------------------------------
# Sensor Registry
# ---------------------------------------------------------------------------

class PhysicalSensorRegistry:
    """管理多个物理传感器实例，提供统一查询接口。"""

    def __init__(self):
        self._sensors: Dict[str, PhysicalSensor] = {}

    def register(self, name: str, sensor: PhysicalSensor) -> None:
        self._sensors[name] = sensor
        logger.info("Registered physical sensor: %s (%s)", name, sensor.__class__.__name__)

    def list_sensors(self) -> List[Dict[str, str]]:
        return [{"name": n, "type": s.__class__.__name__} for n, s in self._sensors.items()]

    def collect_all(self) -> Dict[str, Any]:
        result = {}
        for name, sensor in self._sensors.items():
            try:
                result[name] = sensor.collect()
            except Exception as e:
                logger.error("Sensor %s collect failed: %s", name, e)
                result[name] = {"error": str(e)}
        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_registry: Optional[PhysicalSensorRegistry] = None


def get_physical_sensor_registry() -> PhysicalSensorRegistry:
    global _registry
    if _registry is None:
        _registry = PhysicalSensorRegistry()
    return _registry
