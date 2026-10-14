"""Exercise blocked configuration receipts with a real ROS single-thread executor."""

import threading
import time
from queue import Full
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

pytest.importorskip("rclpy")
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.time import Time
from sensor_msgs.msg import JointState
from std_srvs.srv import Trigger

from linker_arm_ros2 import arm_node

# Import after the node has bootstrapped SDK source discovery.
# isort: split
from linkerbot_arm import ArmFeedback, JointFeedback


@pytest.fixture
def setup(monkeypatch):
    import can

    def forbidden(*args, **kwargs):
        pytest.fail("Executor regressions must not open a physical CAN bus")

    monkeypatch.setattr(can, "Bus", forbidden)
    monkeypatch.setattr(can.interface, "Bus", forbidden)
    sdk = Mock()
    entered, release, stopped = (threading.Event() for _ in range(3))
    speed_threads = []
    outcome = SimpleNamespace(error=None)

    def blocked(values):
        speed_threads.append(threading.current_thread())
        entered.set()
        if not release.wait(3):
            raise TimeoutError("test speed receipt was never released")
        if outcome.error is not None:
            raise outcome.error

    def feedback():
        received = time.monotonic()
        return ArmFeedback(
            (JointFeedback(0, 0, 0, received, received, received),) * 7, True
        )

    sdk.get_feedback.side_effect = feedback
    sdk.disable.side_effect = stopped.set
    sdk.emergency_stop.side_effect = stopped.set
    monkeypatch.setattr(arm_node, "create_arm", lambda **kwargs: sdk)
    monkeypatch.setattr(arm_node.time, "sleep", lambda duration: None)
    rclpy.init(
        args=["--ros-args", "-p", "auto_enable:=false", "-p", "filter_window:=3"]
    )
    node = arm_node.ArmNode()
    node.enabled = True
    node.test_time = 10.0
    monkeypatch.setattr(
        node,
        "get_clock",
        lambda: SimpleNamespace(
            now=lambda: Time(seconds=node.test_time), ros_time_is_active=True
        ),
    )
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    node.state_pub.publish = Mock()
    try:
        yield SimpleNamespace(
            node=node,
            sdk=sdk,
            executor=executor,
            entered=entered,
            release=release,
            stopped=stopped,
            blocked=blocked,
            speed_threads=speed_threads,
            outcome=outcome,
        )
    finally:
        release.set()
        node.destroy_node()
        executor.shutdown(timeout_sec=1)
        if rclpy.ok():
            rclpy.shutdown()
    assert not any(t.name.startswith("ArmLifecycle.") for t in threading.enumerate())


def spin_until(executor, predicate):
    deadline = time.monotonic() + 2
    while not predicate() and time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.01)
    assert predicate(), "executor did not reach the expected state"


def message(value):
    msg = JointState()
    msg.position = [float(value)] * 7
    return msg


def command(setup, msg):
    future = setup.executor.create_task(setup.node._cmd_callback, msg)
    spin_until(setup.executor, future.done)
    assert future.exception() is None


def start_blocked(setup, phase):
    node, sdk = setup.node, setup.sdk
    if phase != "first":
        command(setup, message(0.2))
        spin_until(setup.executor, lambda: node.has_first_cmd)
        spin_until(setup.executor, lambda: not node._tasks.busy)
        sdk.set_angles.reset_mock()
        sdk.set_velocities.reset_mock()
    sdk.set_velocities.side_effect = setup.blocked
    if phase == "first":
        command(setup, message(0.4))
    else:
        node.startup_delay = 0.5
        node.test_time += 1.0
        if phase == "recovery":
            node._speed_recovery_pending = True
            node._slow_speed_ready = False
    spin_until(setup.executor, setup.entered.is_set)
    assert not setup.release.is_set()
    assert node._tasks.configuring_speed
    assert setup.speed_threads[0] is not threading.current_thread()


@pytest.mark.parametrize("invalid", ["names", "length", "nonfinite"])
def test_receipt_wait_keeps_executor_alive_and_only_latest_valid_target(setup, invalid):
    node, sdk, executor = setup.node, setup.sdk, setup.executor
    start_blocked(setup, "first")
    sdk.set_angles.assert_not_called()
    command(setup, message(0.6))
    command(setup, message(0.8))
    bad = message(0.9)
    if invalid == "names":
        bad.name = ["61"] * 7
    elif invalid == "length":
        bad.position = [0.9] * 6
    else:
        bad.position = [float("nan")] * 7
    command(setup, bad)
    assert node._pending_command[0] == [0.8] * 7
    assert not node.has_first_cmd and node.last_cmd_time is None
    assert node._filter_buffers == [[] for _ in range(7)]
    count = node.state_pub.publish.call_count
    spin_until(executor, lambda: node.state_pub.publish.call_count >= count + 2)
    client = node.create_client(Trigger, "/arm_node/home")
    assert client.wait_for_service(timeout_sec=1)
    busy = client.call_async(Trigger.Request())
    spin_until(executor, busy.done)
    assert not busy.result().success and "busy" in busy.result().message
    assert not setup.release.is_set()
    setup.release.set()
    spin_until(executor, lambda: not node._tasks.busy)
    sdk.set_angles.assert_called_once_with([0.8] * 7)
    assert node._filter_buffers == [[0.8] for _ in range(7)]
    assert node.has_first_cmd and node._pending_command is None


@pytest.mark.parametrize("phase", ["first", "normal", "recovery"])
@pytest.mark.parametrize("stop_name", ["disable", "emergency_stop"])
@pytest.mark.parametrize("late_failure", [False, True])
def test_stop_runs_during_speed_wait_and_late_receipt_cannot_resume(
    setup, phase, stop_name, late_failure
):
    node, sdk, executor = setup.node, setup.sdk, setup.executor
    if late_failure:
        setup.outcome.error = OSError("late physical send failure")
    start_blocked(setup, phase)
    command(setup, message(0.8))
    client = node.create_client(Trigger, "/arm_node/" + stop_name)
    assert client.wait_for_service(timeout_sec=1)
    future = client.call_async(Trigger.Request())
    spin_until(executor, setup.stopped.is_set)
    assert not setup.release.is_set()
    assert node._halted and node._pending_command is None
    sdk.set_angles.assert_not_called()
    count = node.state_pub.publish.call_count
    spin_until(executor, lambda: node.state_pub.publish.call_count >= count + 2)
    setup.release.set()
    spin_until(executor, future.done)
    assert future.result().success
    assert not node._tasks.busy
    assert not node.normal_speed_active and not node._speed_recovery_pending
    assert not node.has_first_cmd
    command(setup, message(0.9))
    sdk.set_angles.assert_not_called()
    if stop_name == "disable":
        assert not node.enabled


def test_expired_pending_target_is_not_sent_even_with_frozen_ros_clock(setup):
    start_blocked(setup, "first")
    node = setup.node
    with node._command_lock:
        positions, received = node._pending_command
        node._pending_command = (positions, received - node.cmd_timeout)
    setup.release.set()
    spin_until(setup.executor, lambda: not node._tasks.busy)
    setup.sdk.set_angles.assert_not_called()
    assert not node.has_first_cmd and node._pending_command is None
    command(setup, message(0.8))
    setup.sdk.set_angles.assert_called_once_with([0.8] * 7)
    setup.sdk.set_velocities.assert_called_once()


def test_normal_receipt_after_timeout_restores_slow_before_pending_target(setup):
    start_blocked(setup, "normal")
    command(setup, message(0.8))
    setup.node.test_time += setup.node.cmd_timeout
    setup.release.set()
    spin_until(setup.executor, lambda: setup.sdk.set_angles.call_count == 1)
    spin_until(setup.executor, lambda: not setup.node._tasks.busy)
    assert setup.sdk.set_velocities.call_args_list == [
        call([setup.node.normal_max_velocity] * 7),
        call([setup.node.slow_max_velocity] * 7),
    ]
    setup.sdk.set_angles.assert_called_once_with([0.8] * 7)
    assert not setup.node.normal_speed_active
    assert setup.node.first_cmd_time == Time(seconds=setup.node.test_time)


@pytest.mark.parametrize("phase", ["normal", "recovery"])
def test_successful_transition_accepts_latest_target_with_expected_filter(setup, phase):
    start_blocked(setup, phase)
    command(setup, message(0.6))
    command(setup, message(0.8))
    setup.sdk.set_angles.assert_not_called()
    setup.release.set()
    spin_until(setup.executor, lambda: not setup.node._tasks.busy)
    expected = 0.5 if phase == "normal" else 0.8
    setup.sdk.set_angles.assert_called_once_with([expected] * 7)
    assert setup.node.normal_speed_active == (phase == "normal")
    assert not setup.node._speed_recovery_pending
    assert setup.node._pending_command is None


def test_worker_start_failure_remains_retryable_and_replaces_pending(
    setup, monkeypatch
):
    def failed_start(thread):
        raise RuntimeError("worker start failed")

    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", failed_start)
        setup.node._cmd_callback(message(0.4))
    assert not setup.node._tasks.busy and setup.node._speed_recovery_pending
    setup.sdk.set_angles.assert_not_called()
    setup.node._cmd_callback(message(0.8))
    spin_until(setup.executor, lambda: not setup.node._tasks.busy)
    setup.sdk.set_angles.assert_called_once_with([0.8] * 7)
    assert not setup.node._speed_recovery_pending


def test_shutdown_cancels_pending_target_and_joins_speed_worker(setup):
    start_blocked(setup, "first")
    setup.sdk.disable.side_effect = setup.release.set
    setup.node.destroy_node()
    setup.sdk.set_angles.assert_not_called()
    setup.sdk.close.assert_called_once()
    assert setup.node._tasks._active is None
    assert not any(t.name.startswith("ArmLifecycle.") for t in threading.enumerate())


@pytest.mark.parametrize("phase", ["first", "normal", "recovery"])
@pytest.mark.parametrize("window", [1, 3])
def test_new_target_supersedes_pending_at_speed_worker_completion(
    setup, hold_speed_finalization, wait_for_tasks, phase, window
):
    node, sdk = setup.node, setup.sdk
    node.filter_window = window
    if phase != "first":
        node._cmd_callback(message(0.2))
        wait_for_tasks(node)
        node.startup_delay = 0.5
        node.test_time += 1.0
        if phase == "recovery":
            node._speed_recovery_pending = True
            node._slow_speed_ready = False

    finished, release = hold_speed_finalization(node)
    if phase == "first":
        node._cmd_callback(message(0.2))
    else:
        node._update_speed_mode()
    assert finished.wait(2)
    assert node._tasks.configuring_speed
    node._cmd_callback(message(0.4))
    assert node._pending_command[0] == [0.4] * 7
    release.set()
    wait_for_tasks(node)

    node._cmd_callback(message(0.6))
    assert node._pending_command is None
    node._control_loop()
    expected = 0.6 if phase == "recovery" or window == 1 else 0.4
    assert sdk.set_angles.call_count == 2
    assert sdk.set_angles.call_args.args[0] == pytest.approx([expected] * 7)
    history = [0.6] if phase == "recovery" or window == 1 else [0.2, 0.6]
    assert node._filter_buffers == [history] * 7


@pytest.mark.parametrize("rejection", ["names", "length", "nonfinite", "sdk"])
def test_rejected_new_target_preserves_pending_at_speed_worker_completion(
    setup, hold_speed_finalization, wait_for_tasks, rejection
):
    node, sdk = setup.node, setup.sdk
    finished, release = hold_speed_finalization(node)
    node._cmd_callback(message(0.2))
    assert finished.wait(2)
    node._cmd_callback(message(0.4))
    pending = node._pending_command
    release.set()
    wait_for_tasks(node)
    buffers = [list(buffer) for buffer in node._filter_buffers]
    sums = list(node._filter_sums)
    first_time, last_time = node.first_cmd_time, node.last_cmd_time
    sdk.set_angles.reset_mock()

    newer = message(0.6)
    if rejection == "names":
        newer.name = ["61"] * 7
    elif rejection == "length":
        newer.position = [0.6] * 6
    elif rejection == "nonfinite":
        newer.position = [float("nan")] * 7
    else:
        sdk.set_angles.side_effect = Full("target queue full")
    node.test_time += 0.1
    node._cmd_callback(newer)
    assert node._pending_command == pending
    assert node._filter_buffers == buffers and node._filter_sums == sums
    assert node.first_cmd_time == first_time and node.last_cmd_time == last_time
    assert sdk.set_angles.call_count == (1 if rejection == "sdk" else 0)

    sdk.set_angles.side_effect = None
    sdk.set_angles.reset_mock()
    node._control_loop()
    assert sdk.set_angles.call_count == 1
    assert sdk.set_angles.call_args.args[0] == pytest.approx([0.3] * 7)
    assert node._filter_buffers == [[0.2, 0.4]] * 7
    assert node._pending_command is None


@pytest.mark.parametrize("disable", [False, True])
def test_stop_clears_pending_at_speed_worker_completion(
    setup, hold_speed_finalization, wait_for_tasks, disable
):
    node, sdk = setup.node, setup.sdk
    finished, release = hold_speed_finalization(node)
    node._cmd_callback(message(0.2))
    assert finished.wait(2)
    node._cmd_callback(message(0.4))
    assert node._pending_command is not None

    future = node._tasks.submit(
        lambda cancel: node._stop(cancel, disable=disable), stop=True
    )
    assert setup.stopped.wait(2)
    release.set()
    wait_for_tasks(node)
    spin_until(setup.executor, future.done)
    assert future.result()[0]
    node._cmd_callback(message(0.6))
    node._control_loop()
    sdk.set_angles.assert_called_once_with([0.2] * 7)
    assert node._halted and node._pending_command is None
    assert node._filter_buffers == [[]] * 7
