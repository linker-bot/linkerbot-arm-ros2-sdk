"""Standalone tools use the same canonical SDK without opening hardware."""

import importlib.util
import signal
import sys
from pathlib import Path
from unittest.mock import create_autospec

import linkerbot_arm
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", ["calibrate_arm_zero", "test_lifecycle"])
@pytest.mark.parametrize("arm_type", ["a7", "a7lite"])
def test_tools_construct_canonical_arm(monkeypatch, script, arm_type):
    sdk_class = {"a7": "A7", "a7lite": "A7lite"}[arm_type]
    cls = create_autospec(getattr(linkerbot_arm, sdk_class))
    monkeypatch.setattr(linkerbot_arm, sdk_class, cls)
    # Importing the lifecycle script registers signal handlers; keep the test
    # runner's own handlers while exercising the real SDK loading and factory.
    monkeypatch.setattr(signal, "signal", lambda *args: None)
    spec = importlib.util.spec_from_file_location(
        f"tool_{script}", ROOT / "scripts" / f"{script}.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    arm = module.create_arm(arm_type, "right", "can1")
    assert arm is cls.return_value
    cls.assert_called_once_with(side="right", interface_name="can1")
