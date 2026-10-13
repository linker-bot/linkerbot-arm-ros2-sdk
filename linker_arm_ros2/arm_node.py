#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ROS2 communication node with cancellable lifecycle tasks.

SDK construction and middleware setup finish before auto-enable/home starts.
Lifecycle services await worker results without occupying the ROS executor;
state publication continues while a normal task runs. A separate stop task
cancels home, and streaming stays gated until an explicit successful home or
enable. Shutdown cancels workers, attempts disable, then releases SDK resources.

The 0.1/0.2/0.5 second waits retain existing command-drain allowances; they are
not hardware acknowledgements. Physical stop timing remains SDK/backend-specific.
"""

from __future__ import annotations

import math
import struct
import threading
import time

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger

from linker_arm_ros2.arm_factory import create_arm
from linker_arm_ros2.arm_protocol import ArmProtocol
from linker_arm_ros2.lifecycle_tasks import LifecycleTasks, TaskCancelled

NUM_JOINTS = 7
_MOTOR_IDS = {
    "left": list(range(61, 68)),
    "right": list(range(51, 58)),
}


class ArmNode(Node):
    def __init__(self):
        super().__init__("arm_node")

        self.arm = None
        self.enabled = False
        self._may_be_enabled = False
        self._halted = False
        self._connection_closed = False
        self._destroyed = False
        self._command_lock = threading.RLock()
        self._tasks = LifecycleTasks()
        self._service_group = ReentrantCallbackGroup()
        try:
            self._initialize()
        except BaseException:
            try:
                self.destroy_node()
            except BaseException as cleanup_error:
                self.get_logger().error(
                    f"Initialization cleanup failed: {cleanup_error}"
                )
            raise

    def _initialize(self):
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
        self.declare_parameter("position_kp", 20.0)

        self.arm_type = self.get_parameter("arm_type").value
        self.side = self.get_parameter("side").value
        self.can_interface = self.get_parameter("can_interface").value
        self.publish_rate = self.get_parameter("publish_rate").value
        self.cmd_timeout = self.get_parameter("cmd_timeout").value
        self.auto_enable = self.get_parameter("auto_enable").value
        self.calibrate_zero_on_startup = self.get_parameter(
            "calibrate_zero_on_startup"
        ).value
        self.world_frame = self.get_parameter("world_frame").value
        self.tcp_offset = self.get_parameter("tcp_offset").value
        self.slow_max_velocity = self.get_parameter("slow_max_velocity").value
        self.normal_max_velocity = self.get_parameter("normal_max_velocity").value
        self.startup_delay = self.get_parameter("startup_delay").value
        self.filter_window = self.get_parameter("filter_window").value
        self.position_kp = self.get_parameter("position_kp").value
        self._validate_parameters()
        self.tcp_offset = list(self.tcp_offset)

        # ── 关节名称（与电机 CAN ID 一致）──────────────────────────
        self.joint_names = [str(mid) for mid in _MOTOR_IDS[self.side]]

        # ── 内部状态 ──────────────────────────────────────────────
        self.enabled = False
        self.has_first_cmd = False
        self.first_cmd_time = None
        self.last_cmd_time = None
        self.normal_speed_active = False
        self._speed_recovery_pending = False
        self._slow_speed_ready = False

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
        self.create_service(
            Trigger, "~/enable", self._srv_enable, callback_group=self._service_group
        )
        self.create_service(
            Trigger, "~/disable", self._srv_disable, callback_group=self._service_group
        )
        self.create_service(
            Trigger, "~/home", self._srv_home, callback_group=self._service_group
        )
        self.create_service(
            Trigger,
            "~/emergency_stop",
            self._srv_emergency_stop,
            callback_group=self._service_group,
        )
        self.create_service(
            Trigger,
            "~/reset_error",
            self._srv_reset_error,
            callback_group=self._service_group,
        )
        self.create_service(
            Trigger,
            "~/calibrate_zero",
            self._srv_calibrate_zero,
            callback_group=self._service_group,
        )

        self.get_logger().info(f"ArmNode ready: pub={state_topic}, sub={control_topic}")
        # Services and state publishing exist before any enable/home task starts.
        if self.auto_enable or self.calibrate_zero_on_startup:
            self._tasks.submit(self._startup)

    def _validate_parameters(self):
        """Reject unusable configuration before constructing the hardware SDK."""
        if not isinstance(self.side, str) or self.side not in _MOTOR_IDS:
            raise ValueError("side must be 'left' or 'right'")
        if not isinstance(self.arm_type, str) or self.arm_type.lower() not in (
            "a7", "a7lite", "p7"
        ):
            raise ValueError("arm_type must be a7, a7lite or p7")
        if self.world_frame not in ("urdf", "maestro"):
            raise ValueError("world_frame must be 'urdf' or 'maestro'")
        if not isinstance(self.can_interface, str) or not self.can_interface.strip():
            raise ValueError("can_interface must be a non-empty interface name")
        if not isinstance(self.auto_enable, bool) or not isinstance(
            self.calibrate_zero_on_startup, bool
        ):
            raise ValueError("auto_enable and calibrate_zero_on_startup must be booleans")
        if isinstance(self.filter_window, bool) or not isinstance(
            self.filter_window, int
        ) or self.filter_window < 1:
            raise ValueError("filter_window must be a positive integer")

        def finite(name, value):
            try:
                valid = (
                    not isinstance(value, bool)
                    and isinstance(value, (int, float))
                    and math.isfinite(value)
                )
            except (TypeError, OverflowError):
                valid = False
            if not valid:
                raise ValueError(f"{name} must be a finite number")
            return value

        rate = finite("publish_rate", self.publish_rate)
        if rate <= 0 or not 1 <= 1e9 / rate <= 2**63 - 1:
            raise ValueError("publish_rate must produce a positive representable ROS timer period")
        if finite("cmd_timeout", self.cmd_timeout) <= 0:
            raise ValueError("cmd_timeout must be positive")
        if finite("startup_delay", self.startup_delay) < 0:
            raise ValueError("startup_delay must be non-negative")
        # Every enable/home needs positive speed for a nonzero return distance.
        if not 0 < finite("slow_max_velocity", self.slow_max_velocity) <= 50:
            raise ValueError("slow_max_velocity must be in (0, 50] rad/s")
        if not 0 <= finite("normal_max_velocity", self.normal_max_velocity) <= 50:
            raise ValueError("normal_max_velocity must be in [0, 50] rad/s")
        kp = finite("position_kp", self.position_kp)
        if kp < 0:
            raise ValueError("position_kp must be non-negative")
        try:
            struct.pack("<f", kp)
        except (OverflowError, struct.error) as error:
            raise ValueError("position_kp must be representable as float32") from error
        if isinstance(self.tcp_offset, (str, bytes)):
            raise ValueError("tcp_offset must contain three finite numbers")
        try:
            if len(self.tcp_offset) != 3:
                raise ValueError("tcp_offset must contain three finite numbers")
            for value in self.tcp_offset:
                finite("tcp_offset", value)
        except TypeError as error:
            raise ValueError("tcp_offset must contain three finite numbers") from error

    # ================================================================
    # 控制循环
    # ================================================================

    def _control_loop(self):
        self._publish_state()
        if self._command_lock.acquire(blocking=False):
            try:
                if not self._tasks.busy and not self._halted:
                    if self.enabled and self.has_first_cmd:
                        self._update_speed_mode()
            finally:
                self._command_lock.release()

    def _publish_state(self):
        if self._connection_closed:
            return
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

    def _set_speed_mode(self, *, normal):
        velocity = self.normal_max_velocity if normal else self.slow_max_velocity
        try:
            self.arm.set_velocities([velocity] * NUM_JOINTS)
        except Exception as error:
            # A multi-joint speed write may have partially succeeded. Before
            # admitting another target, restore slow speed for every joint.
            self._speed_recovery_pending = True
            self._slow_speed_ready = False
            self.get_logger().error(
                f"Speed update failed; target admission waits for slow-speed retry: {error}",
                throttle_duration_sec=1.0,
            )
            return False
        self.normal_speed_active = normal
        self._slow_speed_ready = not normal
        return True

    def _update_speed_mode(self):
        now = self.get_clock().now()
        time_since_last_cmd = (now - self.last_cmd_time).nanoseconds / 1e9

        if self._speed_recovery_pending:
            if self._set_speed_mode(normal=False):
                self._reset_command_state()
            return

        if time_since_last_cmd >= self.cmd_timeout:
            if self.normal_speed_active:
                if not self._set_speed_mode(normal=False):
                    return
                self.get_logger().warn(
                    f"No accepted command for {time_since_last_cmd:.1f}s, switching to slow speed"
                )
            self._reset_command_state()
            return

        time_since_first_cmd = (now - self.first_cmd_time).nanoseconds / 1e9
        if not self.normal_speed_active and time_since_first_cmd >= self.startup_delay:
            if self._set_speed_mode(normal=True):
                self.get_logger().info(
                    f"Startup delay elapsed, switching to normal speed "
                    f"({self.normal_max_velocity} rad/s)"
                )

    # ================================================================
    # 指令回调
    # ================================================================

    def _cmd_callback(self, msg: JointState):
        # Never wait behind a lifecycle SDK call on the ROS executor thread.
        if not self._command_lock.acquire(blocking=False):
            return
        try:
            if self._tasks.busy or self._halted or self._connection_closed:
                return
            self._accept_command(msg)
        finally:
            self._command_lock.release()

    def _accept_command(self, msg: JointState):
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

        names = list(msg.name)
        if names:
            if (
                len(names) != NUM_JOINTS
                or len(set(names)) != NUM_JOINTS
                or set(names) != set(self.joint_names)
            ):
                self.get_logger().error(
                    f"Joint names must contain each configured CAN ID exactly once: {self.joint_names}",
                    throttle_duration_sec=1.0,
                )
                return
            by_name = dict(zip(names, positions))
            positions = [by_name[name] for name in self.joint_names]

        for index, position in enumerate(positions, 1):
            if not math.isfinite(position):
                self.get_logger().error(
                    f"Joint {index} target must be finite, got {position}",
                    throttle_duration_sec=1.0,
                )
                return

        # Also handle a command arriving after timeout but before the timer.
        now = self.get_clock().now()
        restarting = (
            not self.has_first_cmd
            or self._speed_recovery_pending
            or (now - self.last_cmd_time).nanoseconds / 1e9 >= self.cmd_timeout
        )
        try:
            filtered, buffers, sums = self._prepare_filter(positions, reset=restarting)
        except ValueError as error:
            self.get_logger().error(str(error), throttle_duration_sec=1.0)
            return

        # Speed configuration precedes the first/recovery target. These two SDK
        # calls are not atomic: success here means admission, not a motor ACK.
        if restarting and (not self._slow_speed_ready or self.normal_speed_active):
            if not self._set_speed_mode(normal=False):
                return
        try:
            self.arm.set_angles(filtered)
        except Exception as error:
            self.get_logger().error(
                f"set_angles rejected command: {error}", throttle_duration_sec=1.0
            )
            return

        # Commit only a target accepted by the SDK. Rejected messages neither
        # enter filter history nor extend the valid-command timeout.
        self._filter_buffers, self._filter_sums = buffers, sums
        self._speed_recovery_pending = False
        now = self.get_clock().now()
        if restarting:
            self.has_first_cmd = True
            self.first_cmd_time = now
            self.get_logger().info(
                f"First command accepted, slow speed for {self.startup_delay}s"
            )
        self.last_cmd_time = now

    def _prepare_filter(self, positions, *, reset=False):
        buffers, sums, filtered = [], [], []
        for i, position in enumerate(positions):
            previous = self._filter_buffers[i]
            total = self._filter_sums[i]
            if (
                reset
                or not math.isfinite(total)
                or not all(map(math.isfinite, previous))
            ):
                previous, total = [], 0.0
            if len(previous) >= self.filter_window:
                total -= previous[0]
                previous = previous[1:]
            candidate = previous + [position]
            total += position
            value = total / len(candidate)
            if not math.isfinite(total) or not math.isfinite(value):
                raise ValueError(f"Joint {i + 1} filtered target must be finite")
            buffers.append(candidate)
            sums.append(total)
            filtered.append(value)
        return filtered, buffers, sums

    def _apply_filter(self, positions: list[float]) -> list[float]:
        """Preview filtered positions without committing a rejected command."""
        return self._prepare_filter(positions)[0]

    # ================================================================
    # Service 回调
    # ================================================================

    def _apply_position_kps(self) -> None:
        """A7 Lite: apply position-loop KP from config to all joints."""
        if self.arm_type.lower() != "a7lite":
            return
        self.arm.set_position_kps([self.position_kp] * NUM_JOINTS)
        self.get_logger().info(f"A7 Lite position KP set to {self.position_kp}")

    def _check_task(self, cancel):
        if cancel.is_set() or self._destroyed:
            raise TaskCancelled("Lifecycle operation cancelled")
        if self._connection_closed:
            raise RuntimeError("SDK connection is closed; restart the node")

    def _task_call(self, cancel, operation, *args):
        with self._command_lock:
            self._check_task(cancel)
            return operation(*args)

    def _pause(self, cancel, duration):
        if cancel.wait(duration):
            raise TaskCancelled("Lifecycle operation cancelled")
        self._check_task(cancel)

    def _reset_command_state(self):
        self.has_first_cmd = False
        self.normal_speed_active = False
        self.first_cmd_time = None
        self.last_cmd_time = None
        self._speed_recovery_pending = False
        self._filter_buffers = [[] for _ in range(NUM_JOINTS)]
        self._filter_sums = [0.0] * NUM_JOINTS
        self._slow_speed_ready = False

    def _home(self, cancel):
        self._task_call(
            cancel, self.arm.set_velocities, [self.slow_max_velocity] * NUM_JOINTS
        )
        self._check_task(cancel)
        # SDK cancellation guards admission even if stop arrives just before
        # home enters the SDK, and cancels P7's host-streamed waypoints.
        self.arm.home_cancellable(cancel)
        with self._command_lock:
            self._check_task(cancel)
            self._reset_command_state()
            self._halted = False
        return f"{self.side} arm homed"

    def _enable(self, cancel):
        self._task_call(cancel, self.arm.disable)
        self.enabled = False
        self._pause(cancel, 0.1)
        with self._command_lock:
            self._check_task(cancel)
            # enable can fail after sending only some joints' frames.
            self._may_be_enabled = True
            self.arm.enable()
            self.enabled = True
        self._pause(cancel, 0.2)
        self._task_call(cancel, self._apply_position_kps)
        self._home(cancel)
        return f"{self.side} arm enabled and homed"

    def _calibrate(self, cancel):
        if self.enabled or self._may_be_enabled:
            raise RuntimeError("Arm must be disabled before calibrating zero")
        self._task_call(cancel, self.arm.calibrate_zero)
        self._pause(cancel, 2.0)
        return f"{self.side} arm zero calibrated"

    def _startup(self, cancel):
        try:
            if self.calibrate_zero_on_startup:
                self._calibrate(cancel)
            if self.auto_enable:
                self._enable(cancel)
            self.get_logger().info("Startup completed")
            return "Startup completed"
        except BaseException as error:
            if not cancel.is_set():
                self.get_logger().error(f"Startup failed: {error}")
                try:
                    self._close_connection()
                except BaseException:
                    pass  # _close_connection logged the secondary error; preserve cause.
            raise

    async def _service_task(self, response, operation, *, stop=False):
        success, message = await self._tasks.submit(operation, stop=stop)
        response.success = success
        response.message = message
        if not success:
            self.get_logger().warn(message)
        return response

    async def _srv_enable(self, request, response):
        def enable(cancel):
            try:
                return self._enable(cancel)
            except BaseException:
                if not cancel.is_set():
                    try:
                        self._close_connection()
                    except BaseException:
                        pass  # Keep the enable failure as the service response.
                raise

        return await self._service_task(response, enable)

    async def _srv_home(self, request, response):
        def home(cancel):
            if not self.enabled:
                raise RuntimeError("Arm is not enabled")
            return self._home(cancel)

        return await self._service_task(response, home)

    def _stop(self, cancel, *, disable):
        with self._command_lock:
            self._check_task(cancel)
            self._halted = True
            self._reset_command_state()
            if disable:
                self.arm.disable()
                self.enabled = False
                self._may_be_enabled = False
            else:
                self.arm.emergency_stop()
        return f"{self.side} arm {'disabled' if disable else 'emergency stopped'}"

    async def _srv_disable(self, request, response):
        return await self._service_task(
            response, lambda cancel: self._stop(cancel, disable=True), stop=True
        )

    async def _srv_emergency_stop(self, request, response):
        return await self._service_task(
            response, lambda cancel: self._stop(cancel, disable=False), stop=True
        )

    async def _srv_reset_error(self, request, response):
        def reset(cancel):
            self._task_call(cancel, self.arm.reset_error)
            return f"{self.side} arm errors reset"

        return await self._service_task(response, reset)

    async def _srv_calibrate_zero(self, request, response):
        return await self._service_task(response, self._calibrate)

    def _close_connection(self):
        with self._command_lock:
            if self.arm is None or self._connection_closed:
                return
            self._halted = True
            try:
                if self.enabled or self._may_be_enabled:
                    self.arm.disable()
                    self.enabled = False
                    self._may_be_enabled = False
                    time.sleep(0.5)
            except BaseException as error:
                self.get_logger().error(f"Disable during cleanup failed: {error}")
            try:
                self.arm.close()
            except BaseException as error:
                self.get_logger().error(f"SDK close failed; cleanup can retry: {error}")
                raise
            self._connection_closed = True

    def destroy_node(self):
        if self._destroyed:
            self._close_connection()
            return
        self._destroyed = True
        tasks = self._tasks.cancel_for_shutdown()
        try:
            # Cancel the SDK motion wait/stream before joining the lifecycle task.
            with self._command_lock:
                if self.arm is not None and not self._connection_closed:
                    if self.enabled or self._may_be_enabled:
                        try:
                            self.arm.disable()
                            self.enabled = False
                            self._may_be_enabled = False
                            time.sleep(0.5)
                        except BaseException as error:
                            self.get_logger().error(f"Shutdown disable failed: {error}")
            try:
                self._tasks.join(tasks)
            finally:
                self._close_connection()
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ArmNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if node is not None:
                node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


if __name__ == "__main__":
    main()
