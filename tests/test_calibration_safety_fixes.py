"""Calibration queries and finite zero feedback without hardware."""

import importlib.util
import signal
import subprocess
import sys
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
def tool(monkeypatch):
    monkeypatch.setattr(signal, "signal", lambda *args: None)

    def load(name):
        spec = importlib.util.spec_from_file_location(
            f"safety_{name}", ROOT / "scripts" / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        monkeypatch.setattr(module.time, "sleep", lambda duration: None)
        return module

    return load


@pytest.mark.parametrize(
    "name",
    [
        "/arm_node",
        "/left_arm_node",
        "/right_arm_node",
        "/robot/arm_node",
        "/robot/left_arm_node",
        "/a/b/right_arm_node",
    ],
)
def test_calibration_detects_default_and_namespaced_controllers(tool, name):
    calibration = tool("calibrate_arm_zero")
    assert calibration.find_running_arm_nodes(f"/camera\n{name}\n{name}\n") == [name]


@pytest.mark.parametrize("failure", ["missing", "timeout", "error", "nonzero"])
def test_ros_query_failure_never_means_controller_stopped(tool, monkeypatch, failure):
    calibration = tool("calibrate_arm_zero")
    monkeypatch.setattr(
        calibration.shutil,
        "which",
        lambda name: None if failure == "missing" else "/bin/ros2",
    )
    result = SimpleNamespace(returncode=1, stdout="", stderr="DDS unavailable")
    query = Mock(return_value=result)
    if failure == "timeout":
        query.side_effect = subprocess.TimeoutExpired("ros2", 3)
    elif failure == "error":
        query.side_effect = OSError("cannot execute ros2")
    monkeypatch.setattr(calibration.subprocess, "run", query)
    with pytest.raises(RuntimeError, match="拒绝标定"):
        calibration.ensure_arm_nodes_stopped()


def test_successful_empty_ros_graph_is_accepted(tool, monkeypatch):
    calibration = tool("calibrate_arm_zero")
    monkeypatch.setattr(calibration.shutil, "which", lambda name: "/bin/ros2")
    monkeypatch.setattr(
        calibration.subprocess,
        "run",
        Mock(return_value=SimpleNamespace(returncode=0, stdout="/camera\n", stderr="")),
    )
    calibration.ensure_arm_nodes_stopped()


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), True, "0"]
)
def test_calibration_rejects_invalid_angle_before_success(tool, value):
    calibration = tool("calibrate_arm_zero")
    with pytest.raises(RuntimeError, match="有限"):
        calibration.verify_zero_angles("left", [0.0] * 6 + [value], 0.05, "test")


@pytest.mark.parametrize("tolerance", [0, -0.1, float("nan"), float("inf"), True])
def test_zero_verification_requires_valid_tolerance(tool, tolerance):
    with pytest.raises(ValueError, match="tolerance"):
        tool("calibrate_arm_zero").verify_zero_angles(
            "left", [0.0] * 7, tolerance, "test"
        )


@pytest.mark.parametrize(
    "option,value",
    [
        ("--tolerance", "nan"),
        ("--tolerance", "0"),
        ("--home-velocity", "inf"),
        ("--home-velocity", "0"),
        ("--disable-attempts", "0"),
        ("--flash-wait", "-1"),
        ("--reconnect-wait", "nan"),
    ],
)
def test_bad_calibration_cli_rejected_before_device_creation(tool, option, value):
    with pytest.raises(SystemExit) as error:
        tool("calibrate_arm_zero").parse_args([option, value])
    assert error.value.code == 2
