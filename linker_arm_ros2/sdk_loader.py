"""Load the canonical arm SDK without depending on ROS2 or the aggregate SDK.

An importable linkerbot_arm takes priority over source discovery. The legacy
source variable remains a deprecated alias for canonical SDK paths.
"""

import importlib
import logging
import os
import sys
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)
SDK_ENV_VAR = "LINKERBOT_ARM_SRC"
LEGACY_SDK_ENV_VAR = "LINKERBOT_SDK_SRC"


def _source_root(path: Path) -> str | None:
    for candidate in (path, path / "src"):
        if (candidate / "linkerbot_arm" / "__init__.py").is_file():
            return str(candidate.resolve())
    return None


def find_sdk_source() -> str | None:
    """Find an explicit SDK checkout or a nearby canonical arm repository.

    Explicit variables accept a repository root or its src directory. Invalid
    explicit paths raise rather than silently selecting another checkout.
    """
    for variable in (SDK_ENV_VAR, LEGACY_SDK_ENV_VAR):
        configured = os.environ.get(variable, "")
        if not configured:
            continue
        legacy = variable == LEGACY_SDK_ENV_VAR
        if legacy:
            logger.warning(
                "%s is deprecated; migrate to %s and linkerbot-arm 0.6.x",
                LEGACY_SDK_ENV_VAR,
                SDK_ENV_VAR,
            )
        source = _source_root(Path(configured).expanduser())
        if source is None:
            raise ImportError(
                f"{variable}={configured!r} does not contain the linkerbot_arm SDK. "
                f"Set {SDK_ENV_VAR} to the linkerbot-arm repository or its src directory."
            )
        return source

    # Source checkouts, colcon symlink-install and regular install layouts.
    for parent in Path(__file__).resolve().parents:
        for repository in (parent / "linkerbot-arm", parent / "src" / "linkerbot-arm"):
            source = _source_root(repository)
            if source is not None:
                return source
    return None


def load_sdk() -> ModuleType:
    """Return the SDK module, preserving genuine dependency/import errors."""
    try:
        return importlib.import_module("linkerbot_arm")
    except ModuleNotFoundError as exc:
        if exc.name != "linkerbot_arm":
            raise

    source = find_sdk_source()
    if source is None:
        raise ImportError(
            "linkerbot-arm SDK not found. Install linkerbot-arm 0.6.x in the "
            "Python environment running ROS2, or set "
            f"{SDK_ENV_VAR}=/path/to/linkerbot-arm/src. "
            "A linkerbot-arm checkout beside the ROS2 repository or under the "
            "workspace src directory is also supported."
        )

    added = source not in sys.path
    if added:
        sys.path.insert(0, source)
    importlib.invalidate_caches()
    try:
        sdk = importlib.import_module("linkerbot_arm")
    except BaseException:
        if added:
            sys.path.remove(source)
        raise
    logger.info("Loaded linkerbot_arm from SDK source: %s", source)
    return sdk


def ensure_sdk_importable() -> None:
    """Retain the existing helper's None return while initializing the SDK."""
    load_sdk()
