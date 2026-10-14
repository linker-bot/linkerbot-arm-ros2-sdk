# Configuration

Launch reads `config/arm_config.yaml` from the install space. After editing the source configuration, [rebuild and restart](getting_started.md#configure). Parameters are read during node initialization; `ros2 param set` does not currently update controller behavior at runtime.

## YAML Settings

These are the repository's current YAML values, **not all node defaults**.

| Key | Current value | Meaning |
| --- | --- | --- |
| `arm_type` | `"a7lite"` | `a7`, `a7lite`, or `p7` |
| `auto_enable` | `true` | Disable, enable, and home at slow speed during startup |
| `calibrate_zero` | `false` | Calibrate zero at startup, before automatic enabling |
| `left_arm` | `"can4"` | Left-arm SocketCAN interface |
| `right_arm` | `"can2"` | Right-arm SocketCAN interface |
| `position_kp` | `25.0` | A7 Lite position-loop KP; applies only to that model |
| `publish_rate` | `100.0` | State publication timer frequency, Hz |
| `feedback_timeout` | `0.5` | Maximum host reception age of feedback, seconds |
| `cmd_timeout` | `6.0` | Time without accepted targets before slow-speed fallback, seconds |
| `slow_max_velocity` | `0.5` | Startup, homing, and recovery speed, rad/s |
| `normal_max_velocity` | `3.0` | Normal speed setting, rad/s |
| `startup_delay` | `2.0` | Delay from the first accepted target to normal speed, seconds |
| `filter_window` | `1` | Moving-average window; 1 disables smoothing |

`calibrate_zero: true` stores the current pose as zero; it does not move to an existing zero pose. Read [Zero Calibration](tools.md#zero-calibration) before using it.

## Node Parameters and Defaults

Direct node execution defaults to `arm_type=a7`, `can_interface=can0`, `cmd_timeout=3.0`, `startup_delay=6.0`, `filter_window=5`, and `position_kp=20.0`, which differ from YAML. The other motion and publication defaults in the table match.

Launch maps `left_arm` / `right_arm` to each node's `can_interface`, and `calibrate_zero` to `calibrate_zero_on_startup`. Use node parameter names when running the node directly:

```bash
ros2 run linker_arm_ros2 arm_node --ros-args \
  -r __node:=left_arm_node \
  -p side:=left -p arm_type:=a7lite -p can_interface:=can0 \
  -p auto_enable:=false -p filter_window:=1
```

| Node-only parameter | Default | Meaning |
| --- | --- | --- |
| `side` | `"left"` | `left` or `right`; set by the single-arm launch's `side` argument |
| `world_frame` | `"urdf"` | SDK frame convention: `urdf` or `maestro` |
| `tcp_offset` | `[0.0, 0.0, 0.0]` | Three-dimensional SDK TCP offset, meters |

Current launch files do not forward `world_frame` or `tcp_offset` from YAML. Set node parameters directly or write a custom launch file. These settings do not change JointState joint names or ordering.

## Valid Values

- `publish_rate`, `feedback_timeout`, and `cmd_timeout` must be finite and positive; the timer period must fit ROS nanoseconds.
- `startup_delay` must be finite and nonnegative; `filter_window` must be a positive integer.
- `slow_max_velocity` is in `(0, 50]`, and `normal_max_velocity` in `[0, 50]` rad/s. Zero does not bypass the SDK's positive-speed requirement for motion.
- `position_kp` must be finite, nonnegative, and representable as float32. `tcp_offset` must contain three finite numbers.
- Model, side, and frame must be valid; the interface name must be nonempty; startup switches must be booleans.

The node validates parameters before constructing the SDK or opening CAN. Motion remains subject to the SDK's model and joint-limit checks. See [Topics and Joint Control](topics.md#speed-management) for speed and filtering behavior.

[Back to overview](environment_setup.md)
