# linker_arm_ros2

ROS2 package for controlling LinkerBot robotic arms via [linkerbot-python-sdk](https://gitea.linkerhub.work/LinkerOS/linkerbot-python-sdk).

## Overview

This package provides a ROS2 communication layer that wraps `linkerbot-python-sdk` to enable robotic arm control through standard ROS2 topics and services.

### Features

- Joint state publishing (`sensor_msgs/JointState`)
- Joint command subscription (`std_msgs/Float64MultiArray`)
- Configurable CAN interface and publish rate
- Launch file with YAML parameter support

## Dependencies

- ROS2 (Humble or later)
- `linkerbot-python-sdk`
- `rclpy`, `std_msgs`, `sensor_msgs`

## Build

```bash
cd <workspace_root>
colcon build --packages-select linker_arm_ros2
source install/setup.bash
```

## Usage

```bash
ros2 launch linker_arm_ros2 linker_arm.launch.py
```

Or run the node directly:

```bash
ros2 run linker_arm_ros2 linker_arm_node --ros-args -p can_interface:=can0
```

## Topics

| Topic | Type | Direction |
|-------|------|-----------|
| `linker_arm/joint_states` | `sensor_msgs/JointState` | Published |
| `linker_arm/joint_commands` | `std_msgs/Float64MultiArray` | Subscribed |

## Configuration

See `config/linker_arm.yaml` for available parameters.

## License

Apache-2.0
