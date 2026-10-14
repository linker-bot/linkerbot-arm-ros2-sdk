# Connecting and Starting

## 1. Prepare the CAN Interface

A7, A7 Lite, and P7 use classic CAN at 1 Mbit/s. On Linux, install the adapter driver and confirm that a SocketCAN interface such as `can0` exists before configuring it:

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
ip -details link show can0
```

Replace `can0` with the actual interface. Configure each arm's interface for dual-arm operation. For automatic interface detection, see the [CAN detection tool](tools.md#can-detection).

<a id="configure"></a>

## 2. Check the Configuration

Edit `~/linkerbot_ws/src/linkerbot-arm-ros2/config/arm_config.yaml`. Example for a first single-arm session:

```yaml
arm_type: "a7lite"  # a7 | a7lite | p7
auto_enable: false
calibrate_zero: false
left_arm: "can0"
right_arm: "can1"
```

Change these fields and retain the remaining parameters. The repository defaults to `can4` for the left arm and `can2` for the right; replace them to match your devices. `auto_enable: false` prevents automatic homing at startup; it does not disable hardware already enabled by another process. See [Configuration](configuration.md) for all values.

Launch reads the installed configuration. Rebuild after editing so the next launch uses the updated file:

```bash
cd ~/linkerbot_ws
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
source install/setup.bash
cat install/linker_arm_ros2/share/linker_arm_ros2/config/arm_config.yaml
```

## 3. Start One or Both Arms

In a terminal with [ROS and the venv activated](INSTALLATION.md#using-a-new-terminal), run:

```bash
# Left arm
ros2 launch linker_arm_ros2 single_arm.launch.py
# Right arm: use in a separate session
ros2 launch linker_arm_ros2 single_arm.launch.py side:=right
# Both arms: use instead of the single-arm commands above
ros2 launch linker_arm_ros2 dual_arm.launch.py
```

Choose one launch mode. Run only one controller process for each arm. The single-arm launch exposes only `side`; other settings come from YAML. The dual-arm launch exposes no arguments.

## 4. Read State

In another terminal with the same environment activated:

```bash
ros2 node list
ros2 topic echo /left_arm_joint_state --once
```

Left-arm names are `"61"` through `"67"`; right-arm names are `"51"` through `"57"`. `position` uses rad, `velocity` uses rad/s, and `effort` uses N·m. Only complete, fresh feedback is published. If no message arrives, see [Feedback Validity](feedback.md).

## 5. Enable and Home

Ensure that the arm has room to home, then call:

```bash
ros2 service call /left_arm_node/enable std_srvs/srv/Trigger '{}'
```

This service disables, enables, and homes the arm at slow speed; it does more than turn on the motors. Wait for `success: true` before starting control. For the right arm, use `/right_arm_node/enable`. Continue with the [A7](tutorials/a7.md), [A7 Lite](tutorials/a7lite.md), or [P7](tutorials/p7.md) target and feedback examples. See [Topics and Joint Control](topics.md) for the shared message format.

## 6. Stop and Exit

```bash
# Software stop: keep the node running and pause subsequent targets
ros2 service call /left_arm_node/emergency_stop std_srvs/srv/Trigger '{}'
# Disable
ros2 service call /left_arm_node/disable std_srvs/srv/Trigger '{}'
```

After stopping, explicitly enable or successfully home to resume control. Press Ctrl+C in the launch terminal to exit. The node cancels tasks, attempts to disable the arm, and closes the SDK; handle any cleanup error reported in the logs. See [Lifecycle Services](services.md) for response semantics and limits.

[Back to overview](environment_setup.md)
