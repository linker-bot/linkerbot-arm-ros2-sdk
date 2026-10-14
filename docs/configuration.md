# 配置参数

launch 从安装空间的 `config/arm_config.yaml` 读取配置。修改源码配置后[重新构建并启动](getting_started.md#configure)。参数在节点初始化时读取，当前不支持通过 `ros2 param set` 动态更新控制行为。

## YAML 配置

下表为仓库当前 YAML 值，**不是全部节点默认值**。

| 配置键 | 当前值 | 含义 |
| --- | --- | --- |
| `arm_type` | `"a7lite"` | `a7`、`a7lite`、`p7` |
| `auto_enable` | `true` | 启动时失能、使能并慢速回零 |
| `calibrate_zero` | `false` | 启动时标定零位，发生在自动使能前 |
| `left_arm` | `"can4"` | 左臂 SocketCAN 接口 |
| `right_arm` | `"can2"` | 右臂 SocketCAN 接口 |
| `position_kp` | `25.0` | A7 Lite 位置环 KP，仅该型号生效 |
| `publish_rate` | `100.0` | 状态发布定时器频率，Hz |
| `feedback_timeout` | `0.5` | 反馈最大主机接收年龄，秒 |
| `cmd_timeout` | `6.0` | 无有效目标后的慢速回退时间，秒 |
| `slow_max_velocity` | `0.5` | 启动、回零与恢复速度，rad/s |
| `normal_max_velocity` | `3.0` | 正常速度配置，rad/s |
| `startup_delay` | `2.0` | 首次有效目标后切正常速度的延时，秒 |
| `filter_window` | `1` | 滑动平均窗口；1 表示不平滑 |

`calibrate_zero: true` 会把当前位置写成零位，不是运动到已有零位。使用前阅读[标定说明](tools.md#zero-calibration)。

## 节点参数与默认值

直接运行节点时，默认 `arm_type=a7`、`can_interface=can0`、`cmd_timeout=3.0`、`startup_delay=6.0`、`filter_window=5`、`position_kp=20.0`，与 YAML 不同。其余上表的运动及发布参数默认值相同。

launch 将 `left_arm` / `right_arm` 转为每个节点的 `can_interface`，将 `calibrate_zero` 转为 `calibrate_zero_on_startup`。直接运行节点须使用节点参数名：

```bash
ros2 run linker_arm_ros2 arm_node --ros-args \
  -r __node:=left_arm_node \
  -p side:=left -p arm_type:=a7lite -p can_interface:=can0 \
  -p auto_enable:=false -p filter_window:=1
```

| 仅节点参数 | 默认值 | 说明 |
| --- | --- | --- |
| `side` | `"left"` | `left` 或 `right`；单臂 launch 的 `side` 参数控制它 |
| `world_frame` | `"urdf"` | SDK 坐标系：`urdf` 或 `maestro` |
| `tcp_offset` | `[0.0, 0.0, 0.0]` | SDK 的三维 TCP 偏移，米 |

当前 launch 不转发 YAML 中的 `world_frame`、`tcp_offset`；需要自定义时用节点参数或自行编写 launch。它们不会改变 JointState 的关节名称和顺序。

## 参数边界

- `publish_rate`、`feedback_timeout`、`cmd_timeout` 必须为有限正数，定时器周期须能以 ROS 纳秒表示。
- `startup_delay` 为有限非负数，`filter_window` 为正整数。
- `slow_max_velocity` 范围 `(0, 50]`，`normal_max_velocity` 范围 `[0, 50]` rad/s。设为零不代替 SDK 对运动所需正速度的检查。
- `position_kp` 为可编码为 float32 的有限非负数；`tcp_offset` 必须包含三个有限数值。
- 型号、侧别、坐标系必须合法，接口名不得为空，启动开关须为布尔值。

节点在创建 SDK、打开 CAN 前校验参数；实际运动仍须通过 SDK 的型号与关节限位校验。速度与滤波行为见[话题与关节控制](topics.md#speed-management)。

[返回总览](environment_setup.md)
