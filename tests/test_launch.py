"""Parse the actual launch descriptions with ROS2, without starting devices."""

import importlib.util
from pathlib import Path

import pytest
import yaml

pytest.importorskip("launch_ros")
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch_ros.actions import Node

from launch import LaunchContext

ROOT = Path(__file__).resolve().parents[1]


def load_launch(name, monkeypatch, tmp_path, config):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/arm_config.yaml").write_text(yaml.safe_dump(config))
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "launch" / f"{name}.launch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module, "get_package_share_directory", lambda package: str(tmp_path)
    )
    return module


def evaluated_node(node, context):
    assert isinstance(node, Node)
    # Use launch_ros's real parameter evaluation and serialization. We stop
    # before ExecuteProcess, so no SDK constructor or CAN connection runs.
    node._perform_substitutions(context)
    arguments = node._Node__expanded_parameter_arguments
    assert len(arguments) == 1
    path, is_file = arguments[0]
    assert is_file
    try:
        content = yaml.safe_load(Path(path).read_text())
        params = next(iter(content.values()))["ros__parameters"]
    finally:
        Path(path).unlink()
    return node.node_name, params


@pytest.mark.parametrize("arm_type", ["a7", "a7lite", "p7"])
@pytest.mark.parametrize("side", [None, "right"])
def test_single_arm_launch_selects_side_and_parameters(
    monkeypatch, tmp_path, arm_type, side
):
    config = {
        "arm_type": arm_type,
        "left_arm": "can4",
        "right_arm": "can2",
        "auto_enable": False,
        "calibrate_zero": True,
        "publish_rate": "80",
        "cmd_timeout": "6",
        "slow_max_velocity": "0.4",
        "normal_max_velocity": "2",
        "startup_delay": "1.5",
        "filter_window": "3",
        "position_kp": "25",
    }
    module = load_launch("single_arm", monkeypatch, tmp_path, config)
    description = module.generate_launch_description()
    context = LaunchContext()
    context.launch_configurations["ros_namespace"] = "/"
    if side is not None:
        context.launch_configurations["side"] = side
    nodes = []
    for action in description.entities:
        if isinstance(action, DeclareLaunchArgument):
            action.execute(context)
        elif isinstance(action, OpaqueFunction):
            nodes.extend(action.execute(context))
    assert len(nodes) == 1
    selected = side or "left"
    name, params = evaluated_node(nodes[0], context)
    assert name == f"/{selected}_arm_node"
    assert params == {
        "arm_type": arm_type,
        "side": selected,
        "can_interface": config[f"{selected}_arm"],
        "auto_enable": False,
        "calibrate_zero_on_startup": True,
        "publish_rate": 80.0,
        "cmd_timeout": 6.0,
        "slow_max_velocity": 0.4,
        "normal_max_velocity": 2.0,
        "startup_delay": 1.5,
        "filter_window": 3,
        "position_kp": 25.0,
    }


@pytest.mark.parametrize("arm_type", ["a7", "a7lite", "p7"])
def test_dual_arm_launch_preserves_defaults_and_separate_channels(
    monkeypatch, tmp_path, arm_type
):
    module = load_launch("dual_arm", monkeypatch, tmp_path, {"arm_type": arm_type})
    description = module.generate_launch_description()
    context = LaunchContext()
    context.launch_configurations["ros_namespace"] = "/"
    nodes = [action for action in description.entities if isinstance(action, Node)]
    assert len(nodes) == 2
    for node, side, channel in zip(nodes, ("left", "right"), ("can0", "can1")):
        name, params = evaluated_node(node, context)
        assert name == f"/{side}_arm_node"
        assert params == {
            "arm_type": arm_type,
            "side": side,
            "can_interface": channel,
            "auto_enable": True,
            "calibrate_zero_on_startup": False,
            "publish_rate": 100.0,
            "cmd_timeout": 3.0,
            "slow_max_velocity": 0.5,
            "normal_max_velocity": 3.0,
            "startup_delay": 6.0,
            "filter_window": 5,
            "position_kp": 20.0,
        }
