# linker_arm_ros2

[中文文档](README.md)

ROS2 Python package for controlling LinkerBot robotic arms (A7 / A7 Lite / P7) via [linkerbot-arm](https://gitea.linkerhub.work/zhuzhixiang/linkerbot-arm).

This package provides a unified ROS2 communication layer for both A7 and A7 Lite arms. The SDK handles all CAN bus communication, protocol encoding/decoding, and motor management internally — this package simply bridges the SDK API to standard ROS2 topics and services.

## Features

- **Unified driver** for both A7 and A7 Lite arm models via a single config file
- **Centralized configuration** — all parameters in `config/arm_config.yaml`, no launch arguments needed
- **Protocol-Adapter architecture** — ROS2 layer fully decoupled from SDK; SDK updates require no ROS2 node changes
- **Streaming control** — uses `set_angles()` for high-frequency target updates (100Hz teleoperation), bypassing SDK's `move_j()` motion guard
- **Joint state publishing** at configurable rate (default 100 Hz): position, velocity, effort (torque)
- **Joint names** match motor CAN IDs (left: 61-67, right: 51-57)
- **Lifecycle services**: enable, disable, home, emergency stop, reset error, calibrate zero
- **Speed management**: slow start → normal after delay → slow on command timeout
- **Command rejection and recovery**: non-finite positions are rejected before
  filtering. SDK-rejected targets do not enter filter history or refresh accepted
  command timestamps. Initial/recovery commands configure slow speed before the
  target. A failed speed write gates new targets until all-joint slow-speed setup
  succeeds, then restarts the startup interval. Homing, stopping and command
  timeout clear filter history; `filter_window` must be positive. Success means SDK
  admission, not hardware execution. Rejected targets are logged and not replayed.
- **Dual-arm support**: launch left and right arms with separate CAN interfaces
- **Topic-compatible** with existing downstream nodes — no changes required
- **System dependency support**: compatible with NumPy 1.x and ROS2 Pinocchio; see the environment guide

## Prerequisites

- ROS2 Jazzy (or Humble)
- Python 3.10+ (use the Python shipped with your ROS2 distribution)
- CAN interface configured and active (e.g. `can0`, `can1`)
- `linkerbot-arm` 0.6.x, imported as `linkerbot_arm`; see [environment setup](docs/environment_setup.md) for package and source installation
- Pinocchio built for the selected NumPy version; see the environment guide
- System packages: numpy, scipy, python-can, pydantic

## Build

```bash
cd ~/linkerbot_data_collection/linkerhand_data_collection_ws

# Install the independent arm SDK first and use colcon from the same Python environment.
# Source deployments may place linkerbot-arm at src/linkerbot-arm.

# Build
colcon build --packages-select linker_arm_ros2 --symlink-install
source install/setup.bash
```

> Code verification: ROS2 supports P7; standalone calibration and lifecycle scripts still support A7/A7lite only.

## CAN Device Detection

Use the built-in detection script to automatically identify which CAN interface each arm is connected to:

```bash
# First-time only: compile the detection tool
g++ scripts/detect_can.cpp -std=c++17 -o scripts/detect_can

# Run detection (requires sudo to activate CAN interfaces)
bash scripts/detect_can.sh
```

The script will:
1. Automatically activate all CAN interfaces (setting bitrate to 1 Mbps)
2. Detect connected devices (hands, arms, TA teleop arm) on each CAN bus
3. Generate `scripts/can_config.yaml` with the detection results

> If your sudo password differs from the default, edit the `PASSWORD` variable in `scripts/detect_can.sh`, or pass it via environment variable: `PASSWORD=yourpass bash scripts/detect_can.sh`

After detection, copy the `left_arm` and `right_arm` values from `scripts/can_config.yaml` into `config/arm_config.yaml`, then launch:

```bash
# Example: detection found left_arm on can1, right_arm on can2
# Update config/arm_config.yaml:
#   left_arm: "can1"
#   right_arm: "can2"

ros2 launch linker_arm_ros2 dual_arm.launch.py
```

## Configuration

All parameters are managed in `config/arm_config.yaml`:

```yaml
# Arm model
arm_type: "a7lite"        # a7 | a7lite | p7

# Startup behavior
auto_enable: true         # Auto-enable motors on startup
calibrate_zero: false     # Calibrate zero on startup (before enable)

# CAN interfaces
left_arm: "can1"
right_arm: "can0"

# Motion parameters
position_kp: 25.0        # Applied to A7lite only
publish_rate: 100.0       # State publish rate (Hz)
cmd_timeout: 6.0          # Seconds without command before switching to slow speed
slow_max_velocity: 0.5    # Slow speed limit (rad/s)
normal_max_velocity: 3.0  # Normal speed limit (rad/s)
startup_delay: 2.0        # Seconds after first command before switching to normal speed
filter_window: 1          # Moving average filter window size
```

Changes take effect on next `ros2 launch` — no rebuild required.

The CAN interface names above are examples. `world_frame` and `tcp_offset` are node parameters; the current launch files use their node defaults rather than loading them from YAML.

## Usage

### Dual arm (recommended)

```bash
ros2 launch linker_arm_ros2 dual_arm.launch.py
```

All parameters are read from `arm_config.yaml` — no launch arguments needed.

### Single arm

```bash
# Left arm (default)
ros2 launch linker_arm_ros2 single_arm.launch.py

# Right arm
ros2 launch linker_arm_ros2 single_arm.launch.py side:=right
```

`side` is the only launch argument; all other parameters come from `arm_config.yaml`.

### Service control

```bash
# Enable
ros2 service call /left_arm_node/enable std_srvs/srv/Trigger

# Disable
ros2 service call /left_arm_node/disable std_srvs/srv/Trigger

# Home
ros2 service call /left_arm_node/home std_srvs/srv/Trigger

# Emergency stop
ros2 service call /left_arm_node/emergency_stop std_srvs/srv/Trigger
```

## Node Lifecycle

When `auto_enable: true`, the node executes this sequence on startup:

```
1. Create SDK instance → auto-checks communication with all 7 motors
2. disable() → clear old state
3. Wait 0.1s → ensure motors finish processing disable
4. enable() → reset_error + set_control_mode(PP) + enable motors
5. Wait 0.2s → ensure all motors complete enable
6. set_velocities(slow) → set slow speed
7. Run cancellable home in a worker; admit streaming only after completion
8. Enter control loop → publish state at 100Hz
9. On control command → set_angles() streaming
10. Ctrl+C → disable() → wait 0.5s → close()
```

> The wait times (steps 3, 5, 10) ensure CAN frames are fully sent before proceeding,
> avoiding timing issues in the ROS2 multi-threaded environment.
> This strategy applies to both A7 and A7Lite arms.

### Speed Management

```
                    startup_delay
                    ├──────────┤
  ┌─────────────────┬──────────┬────────────────────┬──────────┐
  │  Waiting for    │  Slow    │   Normal speed     │ Timeout  │
  │  commands       │  speed   │ (normal_max_vel)   │ → slow   │
  │ (slow_max_vel)  │          │                    │          │
  └─────────────────┴──────────┴────────────────────┴──────────┘
  ↑                 ↑          ↑                    ↑
  Node starts    1st command  After startup_delay  cmd_timeout with no cmd
```

## Topics

| Topic | Type | Direction | Description |
|-------|------|-----------|-------------|
| `left_arm_joint_state` | `sensor_msgs/JointState` | Published | Angles (rad), velocities (rad/s), torques (Nm), name=["61"..."67"] |
| `right_arm_joint_state` | `sensor_msgs/JointState` | Published | Same, name=["51"..."57"] |
| `left_arm_joint_control` | `sensor_msgs/JointState` | Subscribed | Target joint angles in `position` field (7 floats, rad) |
| `right_arm_joint_control` | `sensor_msgs/JointState` | Subscribed | Same, for right arm |

**Joint names (JointState.name) match motor CAN IDs**:
- Left arm: `["61", "62", "63", "64", "65", "66", "67"]`
- Right arm: `["51", "52", "53", "54", "55", "56", "57"]`

## Services

All services use `std_srvs/srv/Trigger`, namespaced under the node name.

| Service | Description |
|---------|-------------|
| `~/enable` | Enable all 7 motors + slow-speed homing |
| `~/disable` | Disable all 7 motors |
| `~/home` | Cancellable slow homing; responds on completion while state and other services remain available |
| `~/emergency_stop` | Cancel homing and call the SDK software stop; gate subsequent streaming |
| `~/reset_error` | Reset motor error states |
| `~/calibrate_zero` | Set current position as zero (arm must be disabled first) |

Lifecycle services keep the existing `Trigger` type and respond when the operation
returns. One normal task runs at a time; overlapping normal requests return busy.
Disable/emergency-stop cancels the active home, whose response reports failure.
State publishing continues. Streaming resumes only after a successful explicit
home or enable. SDK/backend latency still applies to software stop calls.

Startup/enable failures attempt disable and close; a closed connection requires a
node restart. Install the exact arm/transport sources in
`requirements/source-versions.txt`; older SDKs are rejected before opening CAN.
Matching version numbers alone do not identify this unreleased source baseline.

## Parameters

All parameters are configured in `config/arm_config.yaml` and injected via launch files.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `arm_type` | string | `"a7"` | Arm model: `"a7"` or `"a7lite"` |
| `auto_enable` | bool | `true` | Auto disable → enable → slow homing on startup |
| `calibrate_zero` | bool | `false` | Calibrate zero before enabling |
| `left_arm` | string | `"can1"` | Left arm CAN interface |
| `right_arm` | string | `"can0"` | Right arm CAN interface |
| `publish_rate` | double | `100.0` | State publish rate (Hz) |
| `cmd_timeout` | double | `6.0` | Seconds without command before falling back to slow speed |
| `slow_max_velocity` | double | `0.5` | Slow speed limit (rad/s) |
| `normal_max_velocity` | double | `3.0` | Normal speed limit (rad/s) |
| `startup_delay` | double | `2.0` | Seconds after first command before switching to normal speed |
| `filter_window` | int | `1` | Moving average filter window size |

## Joint Limits

### A7

| Joint | URDF Name | Left (rad) | Right (rad) | Range (°) |
|-------|----------|-----------|-----------|---------|
| J1 Shoulder Pitch | Shoulder_Pitch | [-2.97, 1.05] | [-1.05, 2.97] | 230° |
| J2 Shoulder Roll | Shoulder_Roll | [-0.35, 3.49] | [-3.49, 0.35] | 220° |
| J3 Shoulder Yaw | Shoulder_Yaw | [-2.79, 2.79] | [-2.79, 2.79] | 320° |
| J4 Elbow Pitch | Elbow_Pitch | [-0.21, 2.355] | [-0.21, 2.355] | 147° |
| J5 Wrist Yaw | Wrist_Yaw | [-2.79, 2.79] | [-2.79, 2.79] | 320° |
| J6 Wrist Pitch | Wrist_Pitch | [-1.57, 1.57] | [-1.57, 1.57] | 180° |
| J7 Wrist Roll | Wrist_Roll | [-1.57, 1.57] | [-1.57, 1.57] | 180° |

### A7 Lite

| Joint | URDF Name | Left (rad) | Right (rad) | Range (°) |
|-------|----------|-----------|-----------|---------|
| J1 | L/R1_JOINT | [-2.18, 3.75] | [-3.75, 2.18] | 340° |
| J2 | L/R2_JOINT | [-3.33, 0.19] | [-0.19, 3.33] | 202° |
| J3 | L/R3_JOINT | [-2.26, 2.26] | [-2.26, 2.26] | 259° |
| J4 | L/R4_JOINT | [-0.78, 1.74] | [-1.74, 0.78] | 144° |
| J5 | L/R5_JOINT | [-2.96, 2.96] | [-2.96, 2.96] | 339° |
| J6 | L/R6_JOINT | [-1.57, 1.57] | [-1.57, 1.57] | 180° |
| J7 | L/R7_JOINT | [-1.57, 1.57] | [-1.57, 1.57] | 180° |

> Joint limits from `linkerbot-arm/src/linkerbot_arm/arm/kinetix/urdf/`

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      arm_node.py (ROS2)                       │
│  Publisher / Subscriber / Services / Speed management         │
│  set_angles() streaming | 100Hz state publishing              │
│  Depends only on ArmProtocol, unaware of SDK implementation   │
└──────────────────┬───────────────────────────────────────────┘
                   │ create_arm()
┌──────────────────▼───────────────────────────────────────────┐
│                    arm_factory.py                              │
│  Creates Adapter instance based on arm_type                   │
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│              arm_protocol.py (ABC)                             │
│  enable / disable / set_angles / set_velocities               │
│  get_angles / get_velocities / get_torques / ...              │
└──────────────────┬───────────────────────────────────────────┘
                   │ implements
┌──────────────────▼───────────────────────────────────────────┐
│             sdk_adapter.py                                    │
│  LinkerBotSDKAdapter — adapter for the linkerbot_arm SDK │
│  SDK lookup: installed package → env var → arm checkout      │
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│          linkerbot-arm (source / installed)                  │
│  src/linkerbot-arm/src/linkerbot_arm/                      │
│  A7 / A7lite → CAN Bus → Motors                              │
└──────────────────────────────────────────────────────────────┘
```

### set_angles vs move_j

| | `set_angles()` | `move_j()` |
|---|---|---|
| Purpose | Streaming teleoperation (100Hz) | Point-to-point motion |
| Motion guard | None | Yes (blocked while moving) |
| Motion timer | Not started | Started (estimates completion) |
| Underlying call | `_set_angles()` | `_set_angles()` + timer |
| Control mode | PP | PP |

This node uses `set_angles()` for streaming control; `move_j()` is only used internally by `home()`.

## SDK Loading and Migration

The adapter, calibration tool and lifecycle script share `sdk_loader.py`:

1. `linkerbot_arm` importable in the current Python environment, including an installed package or an existing Python search path.
2. `LINKERBOT_ARM_SRC=/path/to/linkerbot-arm/src`; repository roots are also accepted.
3. Explicit `LINKERBOT_SDK_SRC`, retained for one transition cycle with a migration warning.
4. A `linkerbot-arm` checkout beside the ROS2 repository or under an ancestor workspace's `src/`.

The old full SDK checkout is no longer discovered automatically, and an installed legacy
`linkerbot` package is not an automatic fallback. The old variable may temporarily point
to legacy full SDK source; the new variable only accepts the `linkerbot_arm` namespace.
Invalid explicit paths and missing dependencies produce actionable errors. Source variables
do not override an already importable canonical SDK; restart Python when changing SDK sources.

ROS2 directly requires `linkerbot-arm>=0.6.0,<0.7.0`, without the aggregate SDK or hand package.
The independent `linkerbot_arm`, `linkerbot_hand` and `linkerbot_transport` namespaces can coexist.

## Environment Strategy

Use the Python version provided by your ROS2 distribution. Install the SDK, build with colcon
and run the node in the same environment. Configure the ROS2 system Pinocchio/NumPy binaries
separately from the PyPI `kinetix` extra.

| Dependency | Version and source |
|-----------|---------|
| linkerbot-arm | 0.6.x; pin a verified release or source commit |
| linkerbot-transport | 1.0.0; company package index or pinned source commit |
| NumPy / SciPy | Meet SDK minimums and match the chosen Pinocchio binaries |
| Pydantic | 2.x |
| Pinocchio | Required when constructing all three arm models, including joint-only control |

See [environment setup](docs/environment_setup.md) for installation, the company transport
package source and checks that do not open hardware.

## File Structure

```
linker_arm_ros2/
├── package.xml                  # ROS2 package manifest
├── setup.py                     # Python package setup
├── setup.cfg                    # Install script paths
├── README.md                    # Chinese documentation (default)
├── README_EN.md                 # English documentation
├── resource/linker_arm_ros2     # ament resource marker
│
├── config/
│   └── arm_config.yaml          # Unified config (arm type, CAN, motion params)
│
├── linker_arm_ros2/             # Python package
│   ├── __init__.py
│   ├── arm_protocol.py          # Abstract interface (ABC)
│   ├── sdk_loader.py            # Shared SDK discovery
│   ├── sdk_adapter.py           # ArmProtocol adapter for the arm SDK
│   ├── arm_factory.py           # Factory: creates ArmProtocol instances
│   └── arm_node.py              # Main ROS2 node
│
├── launch/
│   ├── single_arm.launch.py     # Single arm launch (reads arm_config.yaml)
│   └── dual_arm.launch.py       # Dual arm launch (reads arm_config.yaml)
│
├── scripts/
│   ├── detect_can.cpp           # CAN device auto-detection program (compile with g++)
│   ├── detect_can.sh            # Detection wrapper script (activates CAN, runs with sudo)
│   └── test_lifecycle.py        # SDK lifecycle test (enable/disable/home/stream/close)
│
└── docs/
    └── environment_setup.md     # Environment setup guide
```

## Extending to New Arm Models

To add support for a new arm (e.g. a different brand):

1. Implement `ArmProtocol` in a new adapter file (e.g. `new_brand_adapter.py`)
2. Add a branch in `arm_factory.py` to select the new adapter based on `arm_type`
3. No changes needed in `arm_node.py` or launch files

## License

Apache-2.0
