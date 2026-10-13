"""Configuration and named commands without hardware."""

import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def forbid_can(monkeypatch):
    import can

    def forbidden(*args, **kwargs):
        pytest.fail("Safety regressions must not open physical CAN")

    monkeypatch.setattr(can, "Bus", forbidden)
    monkeypatch.setattr(can.interface, "Bus", forbidden)


@pytest.fixture
def ros(monkeypatch):
    rclpy = pytest.importorskip("rclpy")
    from linker_arm_ros2 import arm_node

    monkeypatch.setattr(arm_node.time, "sleep", lambda duration: None)
    rclpy.init(
        args=["--ros-args", "-p", "auto_enable:=false", "-p", "filter_window:=1"]
    )
    try:
        yield arm_node
    finally:
        if rclpy.ok():
            rclpy.shutdown()


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("side", "front"),
        ("arm_type", "h75"),
        ("world_frame", "world"),
        ("can_interface", ""),
        ("filter_window", 0),
        ("filter_window", True),
        ("publish_rate", 0.0),
        ("publish_rate", float("nan")),
        ("publish_rate", 1e-300),
        ("cmd_timeout", 0.0),
        ("cmd_timeout", float("inf")),
        ("startup_delay", -0.1),
        ("startup_delay", float("nan")),
        ("slow_max_velocity", 0.0),
        ("slow_max_velocity", 50.1),
        ("normal_max_velocity", -0.1),
        ("normal_max_velocity", float("inf")),
        ("position_kp", -1.0),
        ("position_kp", float("nan")),
        ("position_kp", 1e100),
        ("tcp_offset", [0.0, 0.0]),
        ("tcp_offset", [0.0, float("nan"), 0.0]),
    ],
)
def test_bad_node_configuration_never_constructs_sdk(
    ros, monkeypatch, parameter, value
):
    factory = Mock()
    monkeypatch.setattr(ros, "create_arm", factory)
    original = ros.ArmNode.get_parameter
    monkeypatch.setattr(
        ros.ArmNode,
        "get_parameter",
        lambda self, name: (
            SimpleNamespace(value=value) if name == parameter else original(self, name)
        ),
    )
    with pytest.raises(ValueError):
        ros.ArmNode()
    factory.assert_not_called()


def test_zero_normal_speed_and_zero_startup_delay_remain_valid(ros, monkeypatch):
    sdk = Mock()
    monkeypatch.setattr(ros, "create_arm", lambda **kwargs: sdk)
    original = ros.ArmNode.get_parameter
    monkeypatch.setattr(
        ros.ArmNode,
        "get_parameter",
        lambda self, name: (
            SimpleNamespace(value=0.0)
            if name in ("normal_max_velocity", "startup_delay")
            else original(self, name)
        ),
    )
    node = ros.ArmNode()
    try:
        assert node.normal_max_velocity == 0.0
        assert node.startup_delay == 0.0
    finally:
        node.destroy_node()


@pytest.mark.parametrize("side", ["left", "right"])
def test_named_targets_reorder_into_the_configured_can_order(ros, monkeypatch, side):
    from sensor_msgs.msg import JointState

    sdk = Mock()
    monkeypatch.setattr(ros, "create_arm", lambda **kwargs: sdk)
    original = ros.ArmNode.get_parameter
    monkeypatch.setattr(
        ros.ArmNode,
        "get_parameter",
        lambda self, name: (
            SimpleNamespace(value=side) if name == "side" else original(self, name)
        ),
    )
    node = ros.ArmNode()
    try:
        node.enabled = True
        msg = JointState()
        expected = [0.01 * index for index in range(7)]
        msg.name = list(reversed(node.joint_names))
        msg.position = list(reversed(expected))
        node._cmd_callback(msg)
        sdk.set_angles.assert_called_once_with(expected)
    finally:
        node.destroy_node()


@pytest.mark.parametrize(
    "names",
    [[], ["61"] * 7, [str(n) for n in range(60, 67)], [str(n) for n in range(61, 67)]],
)
def test_names_validation_preserves_fixed_order_compatibility_and_admission(
    ros, monkeypatch, names
):
    from sensor_msgs.msg import JointState

    sdk = Mock()
    monkeypatch.setattr(ros, "create_arm", lambda **kwargs: sdk)
    node = ros.ArmNode()
    try:
        node.enabled = True
        msg = JointState()
        msg.name = names
        msg.position = [0.01 * index for index in range(7)]
        before = copy.deepcopy(
            (node._filter_buffers, node._filter_sums, node.last_cmd_time)
        )
        node._cmd_callback(msg)
        if names:
            assert not sdk.mock_calls
            assert (
                node._filter_buffers,
                node._filter_sums,
                node.last_cmd_time,
            ) == before
        else:
            sdk.set_angles.assert_called_once_with(list(msg.position))
    finally:
        node.destroy_node()


def test_named_position_length_mismatch_is_rejected_without_io(ros, monkeypatch):
    from sensor_msgs.msg import JointState

    sdk = Mock()
    monkeypatch.setattr(ros, "create_arm", lambda **kwargs: sdk)
    node = ros.ArmNode()
    try:
        node.enabled = True
        msg = JointState()
        msg.name = node.joint_names
        msg.position = [0.0] * 6
        node._cmd_callback(msg)
        assert not sdk.mock_calls
        assert not node.has_first_cmd
    finally:
        node.destroy_node()
