"""Cancellable lifecycle and cleanup of all instances without hardware."""

import importlib.util
import signal
import sys
from pathlib import Path
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


def prepare_lifecycle(tool, monkeypatch, *, real_home=False):
    module = tool("test_lifecycle")
    arms = {"left": Mock(), "right": Mock()}
    monkeypatch.setattr(module, "load_config", lambda: None)
    monkeypatch.setattr(
        module, "create_arm", lambda arm_type, side, can_interface: arms[side]
    )
    for name in ("test_enable", "test_home", "test_state_read", "test_streaming"):
        if not real_home or name != "test_home":
            monkeypatch.setattr(module, name, Mock())
    return module, arms


def test_lifecycle_second_constructor_failure_cleans_first_arm(tool, monkeypatch):
    module, arms = prepare_lifecycle(tool, monkeypatch)

    def factory(arm_type, side, can_interface):
        if side == "right":
            raise RuntimeError("right constructor")
        return arms[side]

    monkeypatch.setattr(module, "create_arm", factory)
    with pytest.raises(RuntimeError, match="right constructor"):
        module.main([])
    arms["left"].disable.assert_called_once()
    arms["left"].close.assert_called_once()


@pytest.mark.parametrize(
    "stage", ["test_enable", "test_home", "test_state_read", "test_streaming"]
)
def test_lifecycle_stage_failure_always_cleans_every_created_arm(
    tool, monkeypatch, stage
):
    module, arms = prepare_lifecycle(tool, monkeypatch)
    getattr(module, stage).side_effect = RuntimeError(stage)
    arms["left"].disable.side_effect = RuntimeError("secondary disable")
    with pytest.raises(RuntimeError, match=stage):
        module.main([])
    for arm in arms.values():
        arm.disable.assert_called_once()
        arm.close.assert_called_once()


def test_lifecycle_cleanup_failure_does_not_skip_other_arm(tool, monkeypatch):
    module, arms = prepare_lifecycle(tool, monkeypatch)
    arms["left"].disable.side_effect = RuntimeError("disable")
    arms["left"].close.side_effect = RuntimeError("close")
    with pytest.raises(RuntimeError, match="cleanup failed"):
        module.main([])
    for arm in arms.values():
        arm.disable.assert_called_once()
        arm.close.assert_called_once()


def test_cleanup_wait_interruption_still_closes_all_arms(tool, monkeypatch):
    module, arms = prepare_lifecycle(tool, monkeypatch)

    def sleep(duration):
        if duration == 0.5:
            raise KeyboardInterrupt()

    monkeypatch.setattr(module.time, "sleep", sleep)
    errors = module._cleanup_arms(arms)
    assert len(errors) == 1
    assert isinstance(errors[0], KeyboardInterrupt)
    for arm in arms.values():
        arm.disable.assert_called_once()
        arm.close.assert_called_once()


def test_shutdown_before_construction_does_not_open_an_arm(tool, monkeypatch):
    module, arms = prepare_lifecycle(tool, monkeypatch)
    factory = Mock()
    monkeypatch.setattr(module, "create_arm", factory)
    module.on_signal(signal.SIGINT, None)
    module.main([])
    factory.assert_not_called()
    assert not any(arm.mock_calls for arm in arms.values())


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_signal_cancels_home_and_skips_remaining_stages(tool, monkeypatch, sig):
    module, arms = prepare_lifecycle(tool, monkeypatch, real_home=True)

    def homing(cancel):
        module.on_signal(sig, None)
        assert cancel.is_set()

    arms["left"].home_cancellable.side_effect = homing
    module.main([])
    arms["left"].home_cancellable.assert_called_once_with(module._shutdown_event)
    arms["right"].home_cancellable.assert_not_called()
    module.test_state_read.assert_not_called()
    module.test_streaming.assert_not_called()
    for arm in arms.values():
        arm.disable.assert_called_once()
        arm.close.assert_called_once()
