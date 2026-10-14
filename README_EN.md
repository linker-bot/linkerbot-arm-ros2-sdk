# LinkerBot Arm ROS2

[中文文档](README.md)

ROS2 Python package for controlling LinkerBot robotic arms (A7 / A7 Lite / P7) via [linkerbot-arm-python](https://gitea.linkerhub.work/linker-bot/linkerbot-arm-python).

The source repository is [linker-bot/linkerbot-arm-ros2](https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2),
with `main` as its default branch. The ROS2 package and Python import remain
`linker_arm_ros2`; the SDK distribution and import remain `linkerbot-arm` and `linkerbot_arm`.

This package provides a unified ROS2 communication layer for both A7 and A7 Lite arms. The SDK handles all CAN bus communication, protocol encoding/decoding, and motor management internally — this package simply bridges the SDK API to standard ROS2 topics and services.

## Features

- **Unified driver** for both A7 and A7 Lite arm models via a single config file
- **Centralized configuration** — all parameters in `config/arm_config.yaml`, no launch arguments needed
- **Protocol-Adapter architecture** — ROS2 layer fully decoupled from SDK; SDK updates require no ROS2 node changes
- **Streaming control** — uses `set_angles()` for high-frequency target updates (external control commands at 100 Hz), retaining node and SDK stop/task admission checks
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
- **Topic compatibility**: topics and message types are unchanged; unnamed commands retain their position order, while named commands are validated and reordered by CAN ID
- **System dependency support**: compatible with NumPy 1.x and ROS2 Pinocchio; see the environment guide

## Prerequisites

- ROS2 Jazzy with Python 3.12 for the validated deployment; Humble requires Python 3.10 and its full dependency combination has not been validated
- CAN interface configured and active (e.g. `can0`, `can1`)
- `linkerbot-arm` 0.6.x, imported as `linkerbot_arm`; see [environment setup](docs/environment_setup.md) for package and source installation
- Pinocchio built for the selected NumPy version; see the environment guide
- numpy, scipy, python-can, pydantic and `linkerbot-transport[can]` in the same Python environment;
  use this repository's [source manifest](requirements/source-versions.txt) to install the paired feedback SDK
  at its verified merge commit on `main`, including current safety fixes.
  Transport comes from the new organization's `main` without a version or tag constraint.
  See [environment setup](docs/environment_setup.md#ros2-系统依赖方案).

## Build

For a new checkout, clone `main` into the example workspace `~/linkerbot_ws`:

```bash
mkdir -p ~/linkerbot_ws/src
git clone --branch main https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2.git ~/linkerbot_ws/src/linkerbot-arm-ros2
```

Install the matching SDK and activate the venv following [environment setup](docs/environment_setup.md), then build:

```bash
cd ~/linkerbot_ws

# Activate the venv from the environment guide, then run Ubuntu Jazzy's colcon with its Python
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
head -n 1 install/linker_arm_ros2/lib/linker_arm_ros2/arm_node
python -c "import sys; print(sys.executable)"
source install/setup.bash
```

The generated node's shebang should point to the active venv. Environments that already
provide a venv colcon entry point can build directly; verify both its interpreter and the
generated node's interpreter. See [environment setup](docs/environment_setup.md#ros2-系统依赖方案).

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
2. Detect connected devices (hands, arms, TA master arm) on each CAN bus
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
feedback_timeout: 0.5     # Maximum host reception age for every feedback field (s)
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
3. Wait 0.1s → retain disable transmission allowance
4. enable() → reset_error + set_control_mode(PP) + enable motors
5. Wait 0.2s → retain enable transmission allowance
6. set_velocities(slow) → set slow speed
7. Run cancellable home in a worker; admit streaming only after completion
8. State publishing and services are established before startup tasks and remain available during home
9. On control command → set_angles() streaming
10. Ctrl+C → cancel tasks → disable() → wait for workers and transmission allowance → close()
```

> Steps 3, 5 and 10 retain transmission allowances, rather than device acknowledgements;
> the lifecycle applies to A7, A7lite and P7.

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

Control messages must contain seven finite positions. A non-empty `name` must contain
exactly the seven CAN ID names for the configured arm, each once. Any order is accepted;
the node reorders positions by name. Unknown, duplicate or missing names and mismatched
lengths reject the entire command without changing filter history or accepted-command
timestamps. Empty `name` retains the fixed position order above.

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
The paired A7lite SDK also latches its stop instead of restoring motion after two seconds.
Explicit `enable()` or a successful `home()` / `home_cancellable()` is required before it
accepts targets again.

Startup/enable failures attempt disable and close; a closed connection requires a
node restart. Install the exact arm/transport sources in
`requirements/source-versions.txt`; older SDKs are rejected before opening CAN.
Matching version numbers alone do not identify this unreleased source baseline.

## Parameters

All parameters are configured in `config/arm_config.yaml` and injected via launch files.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `arm_type` | string | `"a7"` | Arm model: `"a7"`, `"a7lite"` or `"p7"` |
| `auto_enable` | bool | `true` | Auto disable → enable → slow homing on startup |
| `calibrate_zero` | bool | `false` | Calibrate zero before enabling |
| `left_arm` | string | `"can1"` | Left arm CAN interface |
| `right_arm` | string | `"can0"` | Right arm CAN interface |
| `publish_rate` | double | `100.0` | State publish rate (Hz) |
| `feedback_timeout` | double | `0.5` | Maximum reception age for every joint position, velocity and torque field (s) |
| `cmd_timeout` | double | `6.0` | Seconds without command before falling back to slow speed |
| `slow_max_velocity` | double | `0.5` | Slow speed limit (rad/s) |
| `normal_max_velocity` | double | `3.0` | Normal speed limit (rad/s) |
| `startup_delay` | double | `2.0` | Seconds after first command before switching to normal speed |
| `filter_window` | int | `1` | Moving average filter window size |

Parameters are validated before constructing the SDK or opening CAN. `side` must be
`left` / `right`, `arm_type` must select a registered model, `world_frame` must be
`urdf` / `maestro`, and the CAN interface name must be non-empty. Auto-enable and startup
calibration switches must be booleans; `filter_window` must be a positive integer.
`publish_rate` must be finite and positive with a representable ROS nanosecond timer
period; `cmd_timeout` must be finite and positive; `startup_delay` must be finite and
non-negative. Homing `slow_max_velocity` is in `(0, 50]` rad/s and `normal_max_velocity`
is in `[0, 50]` rad/s. `position_kp` must be finite, non-negative and representable as
float32; `tcp_offset` must contain three finite numbers. A zero-speed configuration does
not override the SDK's positive-speed requirement for nonzero motion.

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
| Purpose | External control command streaming (100 Hz) | Point-to-point motion |
| Task admission | Node gate and model-specific SDK checks | SDK point-motion checks |
| Motion task | No point-motion task | Timer or trajectory task, depending on model |
| Underlying call | `_set_angles()`, with automatic P7 limiting | SDK planned/timed target submission |
| Control mode | SDK PP interface; P7 J6/J7 use PTM | SDK PP interface; P7 J6/J7 use PTM |

This node uses `set_angles()` for streaming control; `move_j()` is only used internally by `home()`.

The paired SDK bounds P7 external streaming targets using the configured per-joint velocity
and acceleration, including J6/J7. The first frame of a new or resumed stream seeds
its state from measured positions and holds there. Continue sending periodic external
commands to approach the requested target; one message does not complete a point move.
The SDK uses monotonic time and the actual interval between accepted targets to compute
velocity and acceleration bounds. These bounds apply to the submitted target trajectory,
rather than guaranteeing measured motor speed or physical arrival.

See the [environment guide](docs/environment_setup.md#独立工具与检查边界) for standalone
calibration checks, signal cancellation and per-instance cleanup.

An "external control command" is a `JointState` message published by an external program to
`left_arm_joint_control` or `right_arm_joint_control`, with target angles for all seven joints.

## SDK Loading and Migration

The adapter, calibration tool and lifecycle script share `sdk_loader.py`:

1. `linkerbot_arm` importable in the current Python environment, including an installed package or an existing Python search path.
2. `LINKERBOT_ARM_SRC=/path/to/linkerbot-arm-python/src`; repository roots are also accepted.
3. When the new variable is unset, `LINKERBOT_SDK_SRC` remains a compatibility alias;
   its path must also provide the new `linkerbot_arm` package, and using it prints a migration warning.
4. A checkout using the old directory name `linkerbot-arm`, beside the ROS2 repository or under an ancestor workspace's `src/`.

The new `linkerbot-arm-python` directory name is not discovered automatically. Install it
in the current Python environment or explicitly set `LINKERBOT_ARM_SRC` as shown above.

The node and tools load only `linkerbot_arm`. Both source variables accept only this
namespace; legacy `linkerbot` source and installed packages are not fallback sources.
The node checks the canonical SDK's cancellable-home and feedback freshness capabilities before opening CAN.
Invalid explicit paths and missing dependencies produce actionable errors. Source variables
do not override an already importable canonical SDK; restart Python when changing SDK sources.

ROS2 directly requires `linkerbot-arm>=0.6.0,<0.7.0`, without the aggregate SDK or hand package.
The independent `linkerbot_arm`, `linkerbot_hand` and `linkerbot_transport` namespaces can coexist.

## Environment Strategy

Use the Python version provided by your ROS2 distribution. Install the SDK, build with colcon
and run the node in the same environment. Configure the ROS2 system Pinocchio/NumPy binaries
separately from the PyPI `kinetix` extra.
The validated Jazzy deployment uses Python 3.12 and a venv with system site packages.
SDK `constraints/ros-jazzy.txt` pins NumPy and SciPy; APT provides Pinocchio and eigenpy.

| Dependency | Version and source |
|-----------|---------|
| linkerbot-arm | 0.6.x; install the paired feedback SDK commit pinned in the source manifest |
| linkerbot-transport | `main` in the new organization; no version, tag or old commit pin |
| NumPy | Jazzy deployment lock: 1.26.4 |
| SciPy | Validated venv: 1.13.1; Ubuntu system package: 1.11.4 |
| Pydantic | 2.x |
| Pinocchio / eigenpy | APT: 4.1.0 / 3.13.0; all three arm constructors require kinematics |

See [environment setup](docs/environment_setup.md) for installation, the company transport
package source and checks that do not open hardware.

Install the base SDK for ROS2, without the `kinetix` extra. The extra only installs pip
dependencies; the base SDK provides the same kinematics when compatible Pinocchio is present.
The retained `constraints/ros2.txt` represents a tested NumPy 1.x / SciPy <1.14 range rather
than a universal ROS2 requirement. The current legacy full SDK requires NumPy >=2.2.6 and
cannot share this Jazzy deployment lock; keep it in its own environment.

## File Structure

```
linkerbot-arm-ros2/
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

## Feedback validity

The node reads `get_feedback()` without CAN queries or forward kinematics. It
suppresses JointState when any joint field is missing, nonfinite, older than
`feedback_timeout` (default 0.5 s), or the SDK is closed/faulted. It logs state
transitions and resumes after complete fresh feedback. This does not change
motion commands or automatically stop/enable a device.

The stamp is the last observed ROS clock value at or before the **oldest** host
reception among all published fields. Repeated caches keep their stamp; faster
position updates cannot hide a stale torque field. Startup/clock epoch changes
wait for new feedback from every field. Simulated clock pauses do not pause
monotonic age checks. This is a conservative host observation, not synchronized
firmware sampling; rounding follows the interval between publication callbacks.
See [feedback timing](docs/feedback.md) for clock-jump and recovery semantics.
The SDK must support `get_feedback()`; older SDKs are rejected before CAN opens.
