# Topics and Joint Control

## Topic List

| Topic | Direction | Message type |
| --- | --- | --- |
| `/left_arm_joint_state` | Node publishes left-arm state | `sensor_msgs/msg/JointState` |
| `/right_arm_joint_state` | Node publishes right-arm state | `sensor_msgs/msg/JointState` |
| `/left_arm_joint_control` | Node receives left-arm targets | `sensor_msgs/msg/JointState` |
| `/right_arm_joint_control` | Node receives right-arm targets | `sensor_msgs/msg/JointState` |

These are the default full paths without a namespace. Topic names are relative, so namespaces and remapping change them. Publishers and subscribers use ROS default reliable, volatile QoS with depth 10.

## Joint Order and Units

| Side | `name`, ordered J1 through J7 |
| --- | --- |
| Left | `["61", "62", "63", "64", "65", "66", "67"]` |
| Right | `["51", "52", "53", "54", "55", "56", "57"]` |

State fields are `position` (rad), `velocity` (rad/s), and `effort` (N·m). Joint names are CAN IDs, not URDF joint names. The SDK checks limits for the model and side; do not apply one model's limits to another.

## Sending Targets

Complete [enabling and homing](services.md), then publish seven finite angles. This example holds all joints at a confirmed zero pose and publishes at 100 Hz. For motion, replace the values with targets checked against joint limits and the intended path.

```bash
ros2 topic pub --rate 100 /left_arm_joint_control sensor_msgs/msg/JointState \
  '{name: ["61", "62", "63", "64", "65", "66", "67"], position: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}'
```

Named messages may use any joint order, but `name` must contain exactly the seven names for this side, without duplicates. Each position corresponds to its name; the node reorders them to J1 through J7. `name: []` retains compatibility mode and uses the fixed order above.

Incorrect lengths, unknown/duplicate/missing names, NaN/Inf, or non-finite filter results reject the entire message without changing filter history or accepted-command timing. Targets remain subject to SDK validation. Topic publication provides no per-target service receipt; inspect node logs and actual feedback to verify the result.

Control uses only `name` and `position`. `header.stamp`, `velocity`, and `effort` do not schedule targets or configure speed. Messages carry no trajectory timing and do not replace trajectory planning or collision checking.

<a id="speed-management"></a>

## Speed and Filtering

The node configures every joint to slow speed before the first target. `startup_delay` starts when the SDK accepts the first target, followed by the normal-speed setting. After `cmd_timeout` without an accepted target, the node returns to slow speed and resets filtering; the next target starts a new startup phase.

Command timeout changes the speed mode; it **does not automatically stop or disable the arm**. Use the [stop service](services.md#stop-and-resume) when stopping is required.

Speed configuration waits for physical send receipts in a worker, allowing the executor to continue processing feedback and services. Only the latest valid target is retained during configuration. Replaced targets do not enter filter history, and pending targets are dropped when their monotonic host age reaches `cmd_timeout`. Once a newer target is accepted, an older pending target is not replayed. Targets are not admitted during other lifecycle tasks.

After partial speed-configuration failure, all joints must recover slow speed before another target is admitted. Filtering commits only SDK-accepted targets; stopping, successful homing, and timeout recovery clear the window. P7 streaming also applies SDK velocity/acceleration limits; its first frame holds measured position, and repeated input is needed to advance subsequent targets.

## Receiving State

```bash
ros2 topic echo /left_arm_joint_state --once
ros2 topic hz /left_arm_joint_state
```

`publish_rate` specifies the publication timer, not the motor feedback sampling rate. Repeated caches may publish the same timestamp; invalid or stale feedback pauses publication. Data collection and closed-loop control should check freshness. See [Feedback Validity](feedback.md).

[Back to overview](environment_setup.md)
