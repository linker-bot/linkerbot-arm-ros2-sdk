# Troubleshooting

Check the environment, CAN, node, services, then topics. Preserve the actual error message and avoid repeatedly enabling or calibrating without understanding the failure.

## Installation and Interpreter

For `ModuleNotFoundError`, NumPy ABI errors, or missing `packaging.licenses`, confirm that the correct ROS distribution and its system-Python venv are activated and that the matching constraints are used:

```bash
python -c "import sys; print(sys.executable)"
python -c "import numpy, scipy, pinocchio; print(numpy.__version__, scipy.__version__, pinocchio.__file__)"
python -m pip check
head -n 1 ~/linkerbot_ws/install/linker_arm_ros2/lib/linker_arm_ros2/arm_node
```

The node interpreter must match the venv containing the SDK. Do not mix PyPI `pin`/NumPy 2 with the APT Pinocchio profile. Recreate a separate environment using [Installation and Build](INSTALLATION.md).

<a id="sdk-source"></a>

## Wrong SDK Source

```bash
python -c "import linkerbot_arm; print(linkerbot_arm.__file__)"
```

An importable `linkerbot_arm` takes precedence over source environment variables. For source loading, set:

```bash
export LINKERBOT_ARM_SRC=/absolute/path/to/linkerbot-arm-python/src
```

The repository root is also accepted, but this does not override an already importable SDK. Restart Python/the node after changing the source. Automatic discovery recognizes only the older `linkerbot-arm` directory name; install the renamed checkout or specify its path. `LINKERBOT_SDK_SRC` is a deprecated alias, not a loader for the old `linkerbot` aggregate package. Reinstall from the current manifest if `home_cancellable` / `get_feedback` are missing.

## CAN or Motor Initialization Fails

```bash
ip -details link show can0
ros2 node list
```

Check the interface, 1 Mbit/s bitrate, power, wiring, termination, side, and model. SDK construction checks all seven motors; any unreachable motor can fail initialization. Launch uses `respawn: true` with a 3-second delay. Repeated restarts indicate an unresolved initialization or environment problem. Stop launch before diagnosing separately to avoid concurrent control.

## Service Fails or Reports Busy

Read `Trigger.message`. Ordinary services and speed configuration share a worker and fail while busy; stop services can cancel the active task. `home` requires enabling; calibration requires disabling. Restart the node after startup/enable failure closes its connection. See [Lifecycle Services](services.md).

## No State Messages

```bash
ros2 topic list
ros2 topic info /left_arm_joint_state --verbose
```

Check the side, namespace, ROS domain, and QoS. Inspect `Joint state publication paused` logs for incomplete/stale fields, CAN faults, or an unmapped clock epoch. Repeated caches do not become new measurements. See [Feedback Validity](feedback.md) for recovery.

## Targets Have No Effect

Confirm successful enabling/homing, then check seven finite angles, joint names, SDK limits, and node logs. After stopping, explicitly enable or successfully home. Targets are not accepted during lifecycle tasks; during speed configuration, only the latest valid target is retained. The control message's velocity field does not configure motor speed. See [Topics and Joint Control](topics.md).

P7's first frame holds measured position and subsequent inputs are velocity/acceleration limited; publish continuously when testing streaming. `cmd_timeout` only returns to slow speed, not a stopped state.

## Configuration Changes Have No Effect

Check `install/linker_arm_ros2/share/linker_arm_ros2/config/arm_config.yaml`, rebuild, and restart. YAML keys such as `left_arm` or `calibrate_zero` are not node parameter names. `ros2 param set` alone does not change initialized controller behavior.

[Back to overview](environment_setup.md)
