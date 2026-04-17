#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
linkerbot SDK 适配器。

本模块是整个包中 **唯一** 直接引用 linkerbot-python-sdk 的地方。
当 SDK 版本升级导致 API 变动时，只需修改此文件，上层代码无需改动。

SDK 来源（按优先级）：
  1. 已通过 pip 安装的 linkerbot-py 包
  2. 环境变量 LINKERBOT_SDK_SRC 指定的源码路径
  3. 工作空间 src/linkerbot-python-sdk/src/ 下的源码（git submodule）
"""
import logging
import os
import sys
from typing import Literal

from .arm_protocol import ArmProtocol

logger = logging.getLogger(__name__)

_SDK_ENV_VAR = "LINKERBOT_SDK_SRC"


def _find_sdk_source() -> str | None:
    """在预定义位置搜索 linkerbot SDK 源码目录。"""
    candidates: list[str] = []

    env_path = os.environ.get(_SDK_ENV_VAR, "")
    if env_path:
        candidates.append(env_path)

    this_dir = os.path.dirname(os.path.realpath(__file__))
    workspace_root = os.path.abspath(os.path.join(this_dir, "..", "..", ".."))
    candidates.append(os.path.join(workspace_root, "src", "linkerbot-python-sdk", "src"))

    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        d = os.path.dirname(d)
        sdk_candidate = os.path.join(d, "src", "linkerbot-python-sdk", "src")
        if sdk_candidate not in candidates:
            candidates.append(sdk_candidate)
        if d == os.path.dirname(d):
            break

    for path in candidates:
        if os.path.isdir(os.path.join(path, "linkerbot")):
            return os.path.abspath(path)
    return None


def _ensure_sdk_importable() -> None:
    """确保 ``import linkerbot`` 可以成功。"""
    try:
        import linkerbot  # noqa: F401
        return
    except ImportError:
        pass

    sdk_src = _find_sdk_source()
    if sdk_src is None:
        raise ImportError(
            "linkerbot SDK 未找到。请通过以下任一方式提供：\n"
            "  1. pip install linkerbot-py\n"
            f"  2. 设置环境变量 {_SDK_ENV_VAR}=/path/to/linkerbot-python-sdk/src\n"
            "  3. 初始化 git submodule: git submodule update --init src/linkerbot-python-sdk"
        )
    sys.path.insert(0, sdk_src)
    logger.info("已将 linkerbot SDK 源码加入 sys.path: %s", sdk_src)


_ensure_sdk_importable()

from linkerbot import A7, A7lite  # noqa: E402

_ARM_CLASSES: dict[str, type] = {
    "a7": A7,
    "a7lite": A7lite,
}


class LinkerBotSDKAdapter(ArmProtocol):
    """将 linkerbot SDK (A7 / A7lite) 适配为 ArmProtocol 统一接口。

    直接调用 SDK 创建实例，不做额外的 wake-up / verify / retry。
    SDK 创建失败则直接抛出异常，由 launch 的 respawn 机制处理重启。
    """

    def __init__(
        self,
        arm_type: str,
        side: Literal["left", "right"],
        interface_name: str,
        **kwargs,
    ) -> None:
        arm_type_lower = arm_type.lower()
        cls = _ARM_CLASSES.get(arm_type_lower)
        if cls is None:
            raise ValueError(
                f"不支持的 arm_type '{arm_type}'，可选：{list(_ARM_CLASSES)}"
            )

        self._arm = cls(side=side, interface_name=interface_name, **kwargs)
        self._arm_type = arm_type_lower

    # ── 生命周期 ─────────────────────────────────────────────────

    def enable(self) -> None:
        self._arm.enable()

    def disable(self) -> None:
        self._arm.disable()

    def reset_error(self) -> None:
        self._arm.reset_error()

    # ── 运动控制 ─────────────────────────────────────────────────

    def set_angles(self, target_joints: list[float]) -> None:
        self._arm._set_angles(target_joints)

    def move_j(self, target_joints: list[float], *, blocking: bool = True) -> None:
        self._arm.move_j(target_joints, blocking=blocking)

    def home(self, *, blocking: bool = True) -> None:
        self._arm.home(blocking=blocking)

    def emergency_stop(self) -> None:
        self._arm.emergency_stop()

    # ── 参数配置 ─────────────────────────────────────────────────

    def set_velocities(self, velocities: list[float]) -> None:
        self._arm.set_velocities(velocities)

    def set_accelerations(self, accelerations: list[float]) -> None:
        self._arm.set_accelerations(accelerations)

    def set_position_kps(self, kps: list[float]) -> None:
        self._arm.set_position_kps(kps)

    # ── 状态读取 ─────────────────────────────────────────────────

    def get_angles(self) -> list[float]:
        return self._arm.get_angles()

    def get_velocities(self) -> list[float]:
        return self._arm.get_velocities()

    def get_torques(self) -> list[float]:
        return self._arm.get_torques()

    # ── 标定 ─────────────────────────────────────────────────────

    def calibrate_zero(self) -> None:
        self._arm.calibrate_zero()

    # ── 资源释放 ─────────────────────────────────────────────────

    def close(self) -> None:
        if hasattr(self._arm, "close"):
            self._arm.close()

    # ── 扩展访问 ─────────────────────────────────────────────────

    @property
    def raw_sdk(self):
        """返回底层 SDK 实例（A7 或 A7lite），供高级用户直接调用 SDK 特有方法。"""
        return self._arm
