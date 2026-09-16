"""Exercise source selection and real isolated imports without CAN hardware."""

import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from linker_arm_ros2 import sdk_loader

LOADER_PATH = sdk_loader.__file__


@pytest.fixture(autouse=True)
def isolate_discovery(monkeypatch, tmp_path):
    for variable in ("LINKERBOT_ARM_SRC", "LINKERBOT_SDK_SRC"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(sdk_loader, "__file__", str(tmp_path / "ros/sdk_loader.py"))


def make_sdk(path, *, legacy=False):
    package = path / ("linkerbot" if legacy else "linkerbot_arm")
    arm = package / "arm"
    arm.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (arm / "__init__.py").write_text("")
    return path


@pytest.mark.parametrize("layout", ["sibling", "workspace", "installed"])
def test_discovery_only_loads_canonical_checkout(monkeypatch, tmp_path, layout):
    if layout == "sibling":
        loader = tmp_path / "linker_arm_ros2/linker_arm_ros2/sdk_loader.py"
        canonical = tmp_path / "linkerbot-arm/src"
        legacy = tmp_path / "linkerbot-python-sdk/src"
    else:
        loader = tmp_path / (
            "src/linker_arm_ros2/linker_arm_ros2/sdk_loader.py"
            if layout == "workspace"
            else "install/linker_arm_ros2/lib/python3.12/site-packages/linker_arm_ros2/sdk_loader.py"
        )
        canonical = tmp_path / "src/linkerbot-arm/src"
        legacy = tmp_path / "src/linkerbot-python-sdk/src"
    make_sdk(canonical)
    make_sdk(legacy, legacy=True)
    monkeypatch.setattr(sdk_loader, "__file__", str(loader))
    assert sdk_loader.find_sdk_source() == str(canonical)
    (canonical / "linkerbot_arm/__init__.py").unlink()
    assert sdk_loader.find_sdk_source() is None


@pytest.mark.parametrize("repo_root", [False, True])
@pytest.mark.parametrize("variable", ["LINKERBOT_ARM_SRC", "LINKERBOT_SDK_SRC"])
def test_environment_accepts_repo_or_source_root(
    monkeypatch, tmp_path, caplog, repo_root, variable
):
    source = make_sdk(tmp_path / "custom/src")
    monkeypatch.setenv(variable, str(source.parent if repo_root else source))
    with caplog.at_level(logging.WARNING):
        assert sdk_loader.find_sdk_source() == str(source)
    assert ("deprecated" in caplog.text) == (variable == "LINKERBOT_SDK_SRC")


def test_new_variable_takes_priority(monkeypatch, tmp_path):
    source = make_sdk(tmp_path / "new/src")
    old = make_sdk(tmp_path / "old/src", legacy=True)
    monkeypatch.setenv("LINKERBOT_ARM_SRC", str(source))
    monkeypatch.setenv("LINKERBOT_SDK_SRC", str(old))
    assert sdk_loader.find_sdk_source() == str(source)


def test_invalid_explicit_path_does_not_fall_through(monkeypatch, tmp_path):
    make_sdk(tmp_path / "linkerbot-arm/src")
    monkeypatch.setenv("LINKERBOT_ARM_SRC", str(tmp_path / "missing"))
    with pytest.raises(ImportError, match="LINKERBOT_ARM_SRC"):
        sdk_loader.find_sdk_source()


def test_new_variable_rejects_old_namespace(monkeypatch, tmp_path):
    source = make_sdk(tmp_path / "old/src", legacy=True)
    monkeypatch.setenv("LINKERBOT_ARM_SRC", str(source))
    with pytest.raises(ImportError, match="does not contain"):
        sdk_loader.find_sdk_source()


def test_installed_canonical_sdk_retains_priority(monkeypatch):
    module = ModuleType("linkerbot_arm")
    monkeypatch.setattr(sdk_loader.importlib, "import_module", lambda name: module)
    monkeypatch.setattr(
        sdk_loader, "find_sdk_source", lambda: pytest.fail("unexpected fallback")
    )
    assert sdk_loader.load_sdk() is module
    assert sdk_loader.ensure_sdk_importable() is None


@pytest.mark.parametrize(
    "dependency", ["can", "numpy", "scipy", "pydantic", "linkerbot_arm.arm"]
)
def test_dependency_errors_are_not_hidden(monkeypatch, dependency):
    error = ModuleNotFoundError(f"No module named {dependency!r}", name=dependency)

    def fail(name):
        raise error

    monkeypatch.setattr(sdk_loader.importlib, "import_module", fail)
    monkeypatch.setattr(
        sdk_loader, "find_sdk_source", lambda: pytest.fail("unexpected fallback")
    )
    with pytest.raises(ModuleNotFoundError) as caught:
        sdk_loader.load_sdk()
    assert caught.value is error


def run_isolated(code, *, env, args=()):
    # Ignore site packages and ambient PYTHONPATH. A fake loader location also
    # prevents discovery of the real arm checkout above this test repository.
    bootstrap = """
import importlib.util
import pathlib
import sys
spec = importlib.util.spec_from_file_location('loader', sys.argv[1])
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
loader.__file__ = sys.argv[2] + '/isolated/sdk_loader.py'
"""
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            bootstrap + code,
            LOADER_PATH,
            *map(str, args),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("repo_root", [False, True])
def test_explicit_source_imports_in_clean_interpreter(tmp_path, legacy, repo_root):
    source = make_sdk(tmp_path / "custom/src", legacy=legacy)
    variable = "LINKERBOT_SDK_SRC" if legacy else "LINKERBOT_ARM_SRC"
    env = dict(os.environ, **{variable: str(source.parent if repo_root else source)})
    result = run_isolated(
        """
sdk = loader.load_sdk()
assert pathlib.Path(sdk.__file__).is_relative_to(pathlib.Path(sys.argv[2]))
assert sdk.__name__ == sys.argv[3]
if sdk.__name__ == 'linkerbot_arm':
    assert 'linkerbot' not in sys.modules
assert loader.ensure_sdk_importable() is None
""",
        env=env,
        args=(source, "linkerbot.arm" if legacy else "linkerbot_arm"),
    )
    assert ("deprecated" in result.stderr) == legacy


def test_failed_source_import_restores_path_and_preserves_error(tmp_path):
    source = make_sdk(tmp_path / "broken/src")
    (source / "linkerbot_arm/__init__.py").write_text(
        "import missing_arm_dependency_xyz\n"
    )
    run_isolated(
        """
before = list(sys.path)
try:
    loader.load_sdk()
except ModuleNotFoundError as error:
    assert error.name == 'missing_arm_dependency_xyz'
else:
    raise AssertionError('dependency error was hidden')
assert sys.path == before
""",
        env=dict(os.environ, LINKERBOT_ARM_SRC=str(source)),
        args=(source,),
    )


def test_legacy_source_does_not_mix_with_loaded_package(tmp_path):
    source = make_sdk(tmp_path / "legacy/src", legacy=True)
    run_isolated(
        """
from types import ModuleType
other = ModuleType('linkerbot')
other.__path__ = ['/another-sdk/linkerbot']
sys.modules['linkerbot'] = other
try:
    loader.load_sdk()
except ImportError as error:
    assert 'already loaded' in str(error)
else:
    raise AssertionError('mixed two legacy packages')
""",
        env=dict(os.environ, LINKERBOT_SDK_SRC=str(source)),
        args=(source,),
    )


def test_old_installed_namespace_does_not_replace_canonical_sdk(tmp_path):
    old = make_sdk(tmp_path / "old/src", legacy=True)
    run_isolated(
        """
sys.path.insert(0, sys.argv[2])
try:
    loader.load_sdk()
except ImportError as error:
    assert 'LINKERBOT_ARM_SRC' in str(error)
else:
    raise AssertionError('implicitly loaded legacy SDK')
assert 'linkerbot' not in sys.modules
""",
        env=dict(os.environ),
        args=(old,),
    )


def test_missing_sdk_has_actionable_error(monkeypatch):
    def missing(name):
        raise ModuleNotFoundError(
            "No module named 'linkerbot_arm'", name="linkerbot_arm"
        )

    monkeypatch.setattr(sdk_loader.importlib, "import_module", missing)
    with pytest.raises(ImportError, match="LINKERBOT_ARM_SRC"):
        sdk_loader.load_sdk()


def test_calibration_uses_shared_loader(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/calibrate_arm_zero.py"
    spec = importlib.util.spec_from_file_location("calibration_test_module", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    calls = []
    monkeypatch.setattr(sdk_loader, "ensure_sdk_importable", lambda: calls.append(True))
    module.ensure_sdk_importable()
    assert calls == [True]
