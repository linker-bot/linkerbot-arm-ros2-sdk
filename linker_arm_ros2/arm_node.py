#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
linker_arm_ros2 主节点 — ROS2 通信层。

生命周期（auto_enable=true 时）：
  1. 创建 SDK 实例（自动检查 7 个电机通信）
  2. disable → 0.1s → enable → 0.2s（清除旧状态后使能，等待确保 CAN 帧到达）
  3. 设置慢速 → home(blocking=True) 阻塞回零
  4. 进入控制循环：
     - 无控制指令时：发布状态
     - 有控制指令时：set_angles() 流式下发 + 发布状态
  5. Ctrl+C → disable → 0.5s → close（等待确保 disable 帧发送完毕）

流式控制使用 set_angles()（直接下发电机目标角度），
而非 move_j()（有 motion guard，不支持高频调用）。
电机按其 PP 模式内置的 velocity/acceleration profile 追踪目标。

等待时间（0.1s / 0.2s / 0.5s）用于保证 CAN 帧在 ROS2 多线程环境下可靠发送，
同时适用于 A7 和 A7Lite。

依赖关系：
  arm_node.py → arm_factory.py → sdk_adapter.py → linkerbot SDK
"""
from __future__ import annotations

import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger

from linker_arm_ros2.arm_factory import create_arm
from linker_arm_ros2.arm_protocol import ArmProtocol

NUM_JOINTS = 7
_MOTOR_IDS = {
    "left": list(range(61, 68)),
    "right": list(range(51, 58)),
}


class ArmNode(Node):

    def __init__(self):
        super().__init__("arm_node")

        # ── 参数（由 arm_config.yaml 通过 launch 注入）──────────────
        self.declare_parameter("arm_type", "a7")
        self.declare_parameter("side", "left")
        self.declare_parameter("can_interface", "can0")
        self.declare_parameter("publish_rate", 100.0)
        self.declare_parameter("cmd_timeout", 3.0)
        self.declare_parameter("auto_enable", True)
        self.declare_parameter("calibrate_zero_on_startup", False)
        self.declare_parameter("world_frame", "urdf")
        self.declare_parameter("tcp_offset", [0.0, 0.0, 0.0])
        self.declare_parameter("slow_max_velocity", 0.5)
        self.declare_parameter("normal_max_velocity", 3.0)
        self.declare_parameter("startup_delay", 6.0)
        self.declare_parameter("filter_window", 5)

        self.arm_type = self.get_parameter("arm_type").value
        self.side = self.get_parameter("side").value
        self.can_interface = self.get_parameter("can_interface").value
        self.publish_rate = self.get_parameter("publish_rate").value
        self.cmd_timeout = self.get_parameter("cmd_timeout").value
        self.auto_enable = self.get_parameter("auto_enable").value
        self.calibrate_zero_on_startup = self.get_parameter("calibrate_zero_on_startup").value
        self.world_frame = self.get_parameter("world_frame").value
        self.tcp_offset = list(self.get_parameter("tcp_offset").value)
        self.slow_max_velocity = self.get_parameter("slow_max_velocity").value
        self.normal_max_velocity = self.get_parameter("normal_max_velocity").value
        self.startup_delay = self.get_parameter("startup_delay").value
        self.filter_window = self.get_parameter("filter_window").value

        # ── 关节名称（与电机 CAN ID 一致）──────────────────────────
        self.joint_names = [str(mid) for mid in _MOTOR_IDS[self.side]]

        # ── 内部状态 ──────────────────────────────────────────────
        self.enabled = False
        self.has_first_cmd = False
        self.first_cmd_time = None
        self.last_cmd_time = None
        self.normal_speed_active = False

        self._filter_buffers: list[list[float]] = [[] for _ in range(NUM_JOINTS)]
        self._filter_sums: list[float] = [0.0] * NUM_JOINTS

        # ── Step 1: 创建 SDK 实例（自动检查电机通信）─────────────────
        self.arm: ArmProtocol = create_arm(
            arm_type=self.arm_type,
            side=self.side,
            interface_name=self.can_interface,
            world_frame=self.world_frame,
            tcp_offset=self.tcp_offset,
        )
        self.get_logger().info(
            f"SDK arm created: type={self.arm_type}, side={self.side}, "
            f"can={self.can_interface}"
        )

        # ── Step 2: 标定零位（可选）+ 使能 + 慢速回零 ────────────────
        if self.calibrate_zero_on_startup:
            self.arm.calibrate_zero()
            self.get_logger().info("Zero calibration completed")

        if self.auto_enable:
            self.arm.disable()
            time.sleep(0.1)
            self.arm.enable()
            time.sleep(0.2)
            self.enabled = True
            self.get_logger().info("Arm enabled")

            self.arm.set_velocities([self.slow_max_velocity] * NUM_JOINTS)
            self.get_logger().info(
                f"Homing at slow speed ({self.slow_max_velocity} rad/s)..."
            )
            self.arm.home(blocking=True)
            self.get_logger().info("Home completed, entering control loop")

        # ── Publisher / Subscriber ─────────────────────────────────
        state_topic = f"{self.side}_arm_joint_state"
        control_topic = f"{self.side}_arm_joint_control"

        self.state_pub = self.create_publisher(JointState, state_topic, 10)
        self.cmd_sub = self.create_subscription(
            JointState, control_topic, self._cmd_callback, 10
        )

        # ── Timer ──────────────────────────────────────────────────
        self.create_timer(1.0 / self.publish_rate, self._control_loop)

        # ── Services ───────────────────────────────────────────────
        self.create_service(Trigger, "~/enable", self._srv_enable)
        self.create_service(Trigger, "~/disable", self._srv_disable)
        self.create_service(Trigger, "~/home", self._srv_home)
        self.create_service(Trigger, "~/emergency_stop", self._srv_emergency_stop)
        self.create_service(Trigger, "~/reset_error", self._srv_reset_error)
        self.create_service(Trigger, "~/calibrate_zero", self._srv_calibrate_zero)

        self.get_logger().info(
            f"ArmNode ready: pub={state_topic}, sub={control_topic}"
        )

    # ================================================================
    # 控制循环
    # ================================================================

    def _control_loop(self):
        self._publish_state()
        if self.enabled and self.has_first_cmd:
            self._update_speed_mode()

    def _publish_state(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self.joint_names
        try:
            msg.position = list(self.arm.get_angles())
            msg.velocity = list(self.arm.get_velocities())
            msg.effort = list(self.arm.get_torques())
        except Exception as e:
            self.get_logger().warn(
                f"Failed to read state: {e}", throttle_duration_sec=2.0
            )
            return
        self.state_pub.publish(msg)

    def _update_speed_mode(self):
        now = self.get_clock().now()
        time_since_last_cmd = (now - self.last_cmd_time).nanoseconds / 1e9

        if time_since_last_cmd >= self.cmd_timeout:
            if self.normal_speed_active:
                self.get_logger().warn(
                    f"No command for {time_since_last_cmd:.1f}s, switching to slow speed"
                )
                self.arm.set_velocities([self.slow_max_velocity] * NUM_JOINTS)
                self.normal_speed_active = False
            self.has_first_cmd = False
            return

        time_since_first_cmd = (now - self.first_cmd_time).nanoseconds / 1e9
        if not self.normal_speed_active and time_since_first_cmd >= self.startup_delay:
            self.normal_speed_active = True
            self.arm.set_velocities([self.normal_max_velocity] * NUM_JOINTS)
            self.get_logger().info(
                f"Startup delay elapsed, switching to normal speed "
                f"({self.normal_max_velocity} rad/s)"
            )

    # ================================================================
    # 指令回调
    # ================================================================

    def _cmd_callback(self, msg: JointState):
        if not self.enabled:
            self.get_logger().warn(
                "Received command but arm is not enabled, ignoring",
                throttle_duration_sec=5.0,
            )
            return

        positions = list(msg.position)
        if len(positions) != NUM_JOINTS:
            self.get_logger().error(
                f"Expected {NUM_JOINTS} joint positions, got {len(positions)}"
            )
            return

        filtered = self._apply_filter(positions)
        try:
            self.arm.set_angles(filtered)
        except Exception as e:
            self.get_logger().error(
                f"set_angles failed: {e}", throttle_duration_sec=1.0
            )

        now = self.get_clock().now()
        if not self.has_first_cmd:
            self.has_first_cmd = True
            self.first_cmd_time = now
            self.normal_speed_active = False
            self.arm.set_velocities([self.slow_max_velocity] * NUM_JOINTS)
            self.get_logger().info(
                f"First command received, slow speed for {self.startup_delay}s"
            )
        self.last_cmd_time = now

    def _apply_filter(self, positions: list[float]) -> list[float]:
        filtered = [0.0] * NUM_JOINTS
        for i in range(NUM_JOINTS):
            buf = self._filter_buffers[i]
            if len(buf) >= self.filter_window:
                self._filter_sums[i] -= buf[0]
                buf.pop(0)
            buf.append(positions[i])
            self._filter_sums[i] += positions[i]
            filtered[i] = self._filter_sums[i] / len(buf)
        return filtered

    # ================================================================
    # Service 回调
    # ================================================================

    def _srv_enable(self, request, response):
        try:
            self.arm.disable()
            time.sleep(0.1)
            self.arm.enable()
            time.sleep(0.2)
            self.enabled = True
            self.arm.set_velocities([self.slow_max_velocity] * NUM_JOINTS)
            self.arm.home(blocking=True)
            response.success = True
            response.message = f"{self.side} arm enabled and homed"
            self.get_logger().info(response.message)
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f"Enable failed: {e}")
        return response

    def _srv_disable(self, request, response):
        try:
            self.arm.disable()
            self.enabled = False
            self.has_first_cmd = False
            self.normal_speed_active = False
            response.success = True
            response.message = f"{self.side} arm disabled"
            self.get_logger().info(response.message)
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f"Disable failed: {e}")
        return response

    def _srv_home(self, request, response):
        if not self.enabled:
            response.success = False
            response.message = "Arm is not enabled"
            return response
        try:
            self.arm.set_velocities([self.slow_max_velocity] * NUM_JOINTS)
            self.arm.home(blocking=True)
            self.has_first_cmd = False
            self.normal_speed_active = False
            response.success = True
            response.message = f"{self.side} arm homed"
            self.get_logger().info(response.message)
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f"Home failed: {e}")
        return response

    def _srv_emergency_stop(self, request, response):
        try:
            self.arm.emergency_stop()
            response.success = True
            response.message = f"{self.side} arm emergency stopped"
            self.get_logger().warn(response.message)
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f"Emergency stop failed: {e}")
        return response

    def _srv_reset_error(self, request, response):
        try:
            self.arm.reset_error()
            response.success = True
            response.message = f"{self.side} arm errors reset"
            self.get_logger().info(response.message)
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f"Reset error failed: {e}")
        return response

    def _srv_calibrate_zero(self, request, response):
        if self.enabled:
            response.success = False
            response.message = "Arm must be disabled before calibrating zero"
            return response
        try:
            self.arm.calibrate_zero()
            response.success = True
            response.message = f"{self.side} arm zero calibrated"
            self.get_logger().info(response.message)
        except Exception as e:
            response.success = False
            response.message = str(e)
            self.get_logger().error(f"Calibrate zero failed: {e}")
        return response

    # ================================================================
    # 节点销毁 (Ctrl+C)
    # ================================================================

    def destroy_node(self):
        self.get_logger().info("Shutting down: disable → close...")
        try:
            if self.enabled:
                self.arm.disable()
                self.get_logger().info("Arm disabled")
        except Exception:
            pass
        time.sleep(0.5)
        try:
            self.arm.close()
            self.get_logger().info("SDK connection closed")
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ArmNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
