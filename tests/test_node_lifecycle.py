"""Real ROS services and executor, using fake SDKs without opening hardware."""

import threading
import time
from unittest.mock import Mock

import pytest

pytest.importorskip("rclpy")
import rclpy
from rclpy.executors import SingleThreadedExecutor
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger

from linker_arm_ros2 import arm_node


class FakeArm:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self.fail = None
        self.targets = 0

    def _call(self, name):
        self.calls.append(name)
        if self.fail == name:
            raise RuntimeError(f"injected {name} failure")

    def enable(self):
        self._call("enable")

    def disable(self):
        self._call("disable")

    def emergency_stop(self):
        self._call("emergency_stop")

    def close(self):
        self._call("close")

    def set_velocities(self, values):
        self._call("velocity")

    def set_position_kps(self, values):
        self._call("kp")

    def calibrate_zero(self):
        self._call("calibrate")

    def set_angles(self, values):
        self._call("target")

    def get_angles(self):
        return [0.0] * 7

    get_velocities = get_angles
    get_torques = get_angles

    def home_cancellable(self, cancel):
        self._call("home")
        self.started.set()
        while not cancel.is_set() and not self.release.wait(0.005):
            self.targets += 1


@pytest.fixture
def context(monkeypatch):
    import can

    def forbid_can(*args, **kwargs):
        pytest.fail("Lifecycle tests must not open a physical CAN bus")

    monkeypatch.setattr(can, "Bus", forbid_can)
    monkeypatch.setattr(can.interface, "Bus", forbid_can)
    sdk = FakeArm()
    monkeypatch.setattr(arm_node, "create_arm", lambda **kwargs: sdk)
    monkeypatch.setattr(arm_node.time, "sleep", lambda duration: None)
    monkeypatch.setattr(
        arm_node.ArmNode,
        "_pause",
        lambda self, cancel, duration: self._check_task(cancel),
    )
    rclpy.init(
        args=["--ros-args", "-p", "auto_enable:=false", "-p", "arm_type:=a7lite"]
    )
    yield sdk
    sdk.release.set()
    if rclpy.ok():
        rclpy.shutdown()


def spin_until(executor, predicate):
    deadline = time.monotonic() + 2
    while not predicate() and time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.01)
    assert predicate()


@pytest.mark.parametrize("stop_name", ["emergency_stop", "disable"])
def test_home_can_be_stopped_while_state_publication_continues(context, stop_name):
    sdk = context
    node = arm_node.ArmNode()
    node.enabled = True
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    published = Mock()
    node.state_pub.publish = published
    home = node.create_client(Trigger, "/arm_node/home")
    stop = node.create_client(Trigger, "/arm_node/" + stop_name)
    try:
        assert home.wait_for_service(timeout_sec=1)
        assert stop.wait_for_service(timeout_sec=1)
        homing = home.call_async(Trigger.Request())
        spin_until(executor, sdk.started.is_set)
        spin_until(executor, lambda: published.call_count >= 2)
        assert not homing.done()
        duplicate = home.call_async(Trigger.Request())
        spin_until(executor, duplicate.done)
        assert not duplicate.result().success
        message = JointState()
        message.position = [0.1] * 7
        node._cmd_callback(message)
        assert "target" not in sdk.calls
        stopping = stop.call_async(Trigger.Request())
        spin_until(executor, stopping.done)
        spin_until(executor, homing.done)
        assert stopping.result().success
        assert not homing.result().success
        assert stop_name in sdk.calls
        assert not sdk.release.is_set()  # cancellation, not simulated completion
        assert not node._tasks.busy
        node._cmd_callback(message)
        assert "target" not in sdk.calls  # stop remains latched for streaming
    finally:
        sdk.release.set()
        node.destroy_node()
        executor.shutdown()
    assert sdk.calls.count("close") == 1


@pytest.mark.parametrize("stage", ["enable", "kp", "home"])
def test_startup_failure_after_partial_enable_disables_and_closes(context, stage):
    sdk = context
    sdk.fail = stage
    node = arm_node.ArmNode()
    node.auto_enable = True
    try:
        future = node._tasks.submit(node._startup)
        assert _wait_future(future)
        assert not future.result()[0]
        assert "enable" in sdk.calls
        assert sdk.calls[-2:] == ["disable", "close"]
        assert node._connection_closed
        assert not node.enabled
    finally:
        node.destroy_node()
    assert sdk.calls.count("close") == 1


def _wait_future(future):
    deadline = time.monotonic() + 2
    event = threading.Event()
    while not future.done() and time.monotonic() < deadline:
        event.wait(0.005)
    return future.done()


def test_constructor_entity_failure_closes_sdk(context, monkeypatch):
    sdk = context
    original = RuntimeError("service creation failed")
    create_service = arm_node.ArmNode.create_service

    def fail(self, service_type, name, *args, **kwargs):
        if name == "~/home":
            raise original
        return create_service(self, service_type, name, *args, **kwargs)

    monkeypatch.setattr(arm_node.ArmNode, "create_service", fail)
    with pytest.raises(RuntimeError) as exc:
        arm_node.ArmNode()
    assert exc.value is original
    assert sdk.calls == ["close"]


def test_main_shuts_context_down_if_constructor_fails(context, monkeypatch):
    rclpy.shutdown()

    def fail():
        raise RuntimeError("constructor failed")

    monkeypatch.setattr(arm_node, "ArmNode", fail)
    with pytest.raises(RuntimeError, match="constructor failed"):
        arm_node.main(args=[])
    assert not rclpy.ok()


def test_destroy_cancels_running_home_before_closing(context):
    sdk = context
    node = arm_node.ArmNode()
    node.enabled = True
    future = node._tasks.submit(node._home)
    assert sdk.started.wait(1)
    node.destroy_node()
    assert _wait_future(future)
    assert not future.result()[0]
    assert sdk.calls[-2:] == ["disable", "close"]
    assert not any(t.name.startswith("ArmLifecycle.") for t in threading.enumerate())
    node.destroy_node()
    assert sdk.calls.count("close") == 1


def test_disable_failure_does_not_skip_close(context):
    sdk = context
    node = arm_node.ArmNode()
    node.enabled = True
    sdk.fail = "disable"
    node.destroy_node()
    assert sdk.calls[-1] == "close"


def test_task_thread_start_failure_releases_admission(context, monkeypatch):
    node = arm_node.ArmNode()

    def fail(thread):
        raise RuntimeError("worker start failed")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(threading.Thread, "start", fail)
            with pytest.raises(RuntimeError, match="worker start failed"):
                node._tasks.submit(lambda cancel: "done")
        assert not node._tasks.busy
        future = node._tasks.submit(lambda cancel: "done")
        assert _wait_future(future)
        assert future.result() == (True, "done")
    finally:
        node.destroy_node()


def test_automatic_startup_home_is_interruptible(context):
    sdk = context
    rclpy.shutdown()
    rclpy.init(args=["--ros-args", "-p", "arm_type:=a7lite"])
    node = arm_node.ArmNode()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    client = node.create_client(Trigger, "/arm_node/disable")
    try:
        assert sdk.started.wait(1)
        assert client.wait_for_service(timeout_sec=1)
        result = client.call_async(Trigger.Request())
        spin_until(executor, result.done)
        assert result.result().success
        assert not node.enabled
        assert not node._tasks.busy
        assert "close" not in sdk.calls
    finally:
        node.destroy_node()
        executor.shutdown()


def test_failed_node_close_can_be_retried(context):
    sdk = context
    node = arm_node.ArmNode()
    sdk.fail = "close"
    try:
        with pytest.raises(RuntimeError, match="close failure"):
            node.destroy_node()
        assert not node._connection_closed
    finally:
        sdk.fail = None
        node.destroy_node()
    assert node._connection_closed
    assert sdk.calls.count("close") == 2
