"""Real ROS node with failing SDK admission and a deterministic command clock."""

import copy
from queue import Full
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

pytest.importorskip("rclpy")
import rclpy
from rclpy.time import Time
from sensor_msgs.msg import JointState

from linker_arm_ros2 import arm_node


@pytest.fixture
def node(monkeypatch):
    import can

    def forbid_can(*args, **kwargs):
        pytest.fail("Command tests must not open a physical CAN bus")

    monkeypatch.setattr(can, "Bus", forbid_can)
    monkeypatch.setattr(can.interface, "Bus", forbid_can)
    sdk = Mock()
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
        lambda: SimpleNamespace(now=lambda: Time(seconds=node.test_time)),
    )
    try:
        yield node
    finally:
        node.destroy_node()
        rclpy.shutdown()


def command(node, values):
    msg = JointState()
    msg.position = [float(values)] * 7 if isinstance(values, (int, float)) else values
    node._cmd_callback(msg)


def accepted_state(node):
    return copy.deepcopy(
        (
            node._filter_buffers,
            node._filter_sums,
            node.has_first_cmd,
            node.first_cmd_time.nanoseconds
            if node.first_cmd_time is not None
            else None,
            node.last_cmd_time.nanoseconds if node.last_cmd_time is not None else None,
        )
    )


@pytest.mark.parametrize("joint", range(7))
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_joint_rejected_before_state_or_io_then_valid_recovers(
    node, joint, invalid
):
    before = accepted_state(node)
    values = [0.2] * 7
    values[joint] = invalid
    command(node, values)
    assert accepted_state(node) == before
    assert node.arm.mock_calls == []
    command(node, 0.3)
    node.arm.set_angles.assert_called_once_with([0.3] * 7)
    assert node.has_first_cmd


@pytest.mark.parametrize("existing_stream", [False, True])
def test_repeated_queue_rejection_preserves_accepted_history_and_clocks(
    node, existing_stream
):
    if existing_stream:
        command(node, 0.2)
    node.arm.reset_mock()
    before = accepted_state(node)
    node.arm.set_angles.side_effect = Full("target queue full")
    for _ in range(3):
        node.test_time += 0.1
        command(node, 0.8)
        assert accepted_state(node) == before
    # No follow-up speed write after a rejected target.
    assert node.arm.mock_calls[-1] == call.set_angles(
        [0.5 if existing_stream else 0.8] * 7
    )
    if existing_stream:
        node.arm.set_velocities.assert_not_called()
    else:
        # A successful slow setup is retained even if the first target is
        # refused repeatedly; do not keep filling the FIFO with speed writes.
        node.arm.set_velocities.assert_called_once()
    node.arm.set_angles.side_effect = None
    command(node, 0.4)
    expected = 0.3 if existing_stream else 0.4
    assert node.arm.set_angles.call_args.args[0] == pytest.approx([expected] * 7)
    assert node.last_cmd_time == Time(seconds=node.test_time)


def test_sdk_validation_rejection_does_not_enter_filter_history(node):
    command(node, 0.2)
    before = accepted_state(node)
    node.arm.set_angles.side_effect = ValueError("target outside joint limits")
    command(node, 100.0)
    assert accepted_state(node) == before
    node.arm.set_angles.side_effect = None
    command(node, 0.4)
    assert node.arm.set_angles.call_args.args[0] == pytest.approx([0.3] * 7)


def test_first_speed_failure_blocks_target_and_valid_retry_sets_speed_first(node):
    before = accepted_state(node)
    node.arm.set_velocities.side_effect = Full("speed queue full")
    command(node, 0.2)
    assert accepted_state(node) == before
    node.arm.set_angles.assert_not_called()
    assert node._speed_recovery_pending
    node.arm.set_velocities.side_effect = None
    node.arm.reset_mock()
    command(node, 0.4)
    assert node.arm.mock_calls == [
        call.set_velocities([node.slow_max_velocity] * 7),
        call.set_angles([0.4] * 7),
    ]
    assert node.has_first_cmd and not node._speed_recovery_pending


@pytest.mark.parametrize("normal_before", [False, True])
def test_speed_transition_failure_stays_retryable_and_never_escapes(
    node, normal_before
):
    command(node, 0.2)
    node.normal_speed_active = normal_before
    node.startup_delay = 0.5
    node.test_time += node.cmd_timeout + 1 if normal_before else 1
    node.arm.set_velocities.side_effect = Full("partial speed write")
    before = accepted_state(node)
    node._update_speed_mode()
    assert accepted_state(node) == before
    assert node.normal_speed_active == normal_before
    assert node._speed_recovery_pending
    node.arm.set_angles.reset_mock()
    command(node, 0.5)
    node.arm.set_angles.assert_not_called()
    node.arm.set_velocities.side_effect = None
    node._update_speed_mode()
    node.arm.set_velocities.assert_called_with([node.slow_max_velocity] * 7)
    assert not node.has_first_cmd and not node.normal_speed_active
    command(node, 0.4)
    assert node.first_cmd_time == Time(seconds=node.test_time)
    assert node.arm.set_angles.call_args.args[0] == [0.4] * 7


def test_failed_target_after_speed_recovery_does_not_resume_old_speed_timer(node):
    command(node, 0.2)
    node.startup_delay = 0.1
    node.test_time += 0.2
    node.arm.set_velocities.side_effect = Full()
    node._update_speed_mode()
    before = accepted_state(node)
    node.arm.set_velocities.side_effect = None
    node.arm.set_angles.side_effect = Full()
    command(node, 0.4)
    assert accepted_state(node) == before
    assert node._speed_recovery_pending
    node._update_speed_mode()
    assert not node.has_first_cmd and not node.normal_speed_active
    node.arm.set_velocities.assert_called_with([node.slow_max_velocity] * 7)


def test_timeout_between_timer_ticks_starts_fresh_filter_at_slow_speed(node):
    command(node, 0.2)
    node.normal_speed_active = True
    node.test_time += node.cmd_timeout
    node.arm.reset_mock()
    command(node, 0.8)
    assert node.arm.mock_calls == [
        call.set_velocities([node.slow_max_velocity] * 7),
        call.set_angles([0.8] * 7),
    ]
    assert node.first_cmd_time == node.last_cmd_time == Time(seconds=node.test_time)
    assert not node.normal_speed_active


def test_accepted_window_rolls_and_polluted_legacy_state_recovers(node):
    for value in (0.1, 0.2, 0.3, 0.4):
        command(node, value)
    assert node.arm.set_angles.call_args.args[0] == pytest.approx([0.3] * 7)
    node._filter_sums[2] = float("nan")
    node._filter_buffers[4] = [float("inf")]
    command(node, 0.5)
    assert node.arm.set_angles.call_args.args[0] == pytest.approx(
        [0.4, 0.4, 0.5, 0.4, 0.5, 0.4, 0.4]
    )


def test_finite_values_that_overflow_sum_are_rejected_without_corruption(node):
    command(node, 0.2)
    node._filter_sums = [1e308] * 7
    node._filter_buffers = [[1e308] for _ in range(7)]
    before = accepted_state(node)
    node.arm.reset_mock()
    command(node, 1e308)
    assert accepted_state(node) == before
    assert node.arm.mock_calls == []


def test_lifecycle_reset_discards_pre_home_or_pre_stop_filter(node):
    command(node, 0.2)
    node._reset_command_state()
    command(node, 0.8)
    node.arm.set_angles.assert_called_with([0.8] * 7)


@pytest.mark.parametrize("size", [0, 6, 8])
def test_wrong_length_has_no_side_effects(node, size):
    before = accepted_state(node)
    command(node, [0.2] * size)
    assert accepted_state(node) == before
    assert node.arm.mock_calls == []


def test_single_sample_filter_keeps_existing_behavior(node):
    node.filter_window = 1
    command(node, 0.2)
    command(node, 0.8)
    node.arm.set_angles.assert_called_with([0.8] * 7)


@pytest.mark.parametrize("window", [0, -1])
def test_invalid_window_fails_before_creating_sdk(node, monkeypatch, window):
    node.destroy_node()
    rclpy.shutdown()
    rclpy.init(args=["--ros-args", "-p", f"filter_window:={window}"])
    factory = Mock()
    monkeypatch.setattr(arm_node, "create_arm", factory)
    with pytest.raises(ValueError, match="filter_window must be a positive integer"):
        arm_node.ArmNode()
    factory.assert_not_called()
