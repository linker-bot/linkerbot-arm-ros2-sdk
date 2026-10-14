# 话题与关节控制

## 话题列表

| 话题 | 方向 | 消息类型 |
| --- | --- | --- |
| `/left_arm_joint_state` | 节点发布左臂状态 | `sensor_msgs/msg/JointState` |
| `/right_arm_joint_state` | 节点发布右臂状态 | `sensor_msgs/msg/JointState` |
| `/left_arm_joint_control` | 节点接收左臂目标 | `sensor_msgs/msg/JointState` |
| `/right_arm_joint_control` | 节点接收右臂目标 | `sensor_msgs/msg/JointState` |

以上为默认无 namespace 的完整路径。话题为相对名称，使用 namespace 或 remap 时相应变化。发布和订阅使用 ROS 默认可靠、易失 QoS，队列深度 10。

## 关节顺序与单位

| 臂侧 | `name`，按 J1 到 J7 顺序 |
| --- | --- |
| 左臂 | `["61", "62", "63", "64", "65", "66", "67"]` |
| 右臂 | `["51", "52", "53", "54", "55", "56", "57"]` |

状态字段为：`position`（rad）、`velocity`（rad/s）、`effort`（N·m）。关节名称采用 CAN ID，不是 URDF 关节名。SDK 根据型号和左右臂检查限位，不应把一款型号的范围套用于另一款。

## 发送目标

先完成[使能和回零](services.md)，再发布七个有限角度。下面示例保持全部关节在已确认的零位，并以 100 Hz 发布；实际运动时替换为经过限位与路径检查的目标。

```bash
ros2 topic pub --rate 100 /left_arm_joint_control sensor_msgs/msg/JointState \
  '{name: ["61", "62", "63", "64", "65", "66", "67"], position: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}'
```

具名消息可以使用任意关节顺序，但 `name` 必须恰好包含本臂的七个名称且没有重复，`position` 与名称一一对应；节点会重排为 J1 到 J7。`name: []` 保留兼容模式，直接按上述固定顺序解释位置。

长度错误、名称未知/重复/缺失、NaN/Inf 或滤波结果非有限时拒绝整条消息，不改变滤波历史与有效命令时间。目标仍要通过 SDK 校验，发送话题不会得到单条目标的服务回执；查看节点日志和实际反馈确认效果。

控制只使用 `name`、`position`；`header.stamp`、`velocity`、`effort` 不用于目标调度或速度配置。消息没有轨迹时标，也不能替代轨迹规划和碰撞检测。

<a id="speed-management"></a>

## 速度与滤波

首次目标前先完成全臂慢速配置。首条目标被 SDK 接受后开始 `startup_delay` 计时，随后切到正常速度。达到 `cmd_timeout` 未接受新目标时回退慢速并重置滤波，下次目标重新进入启动阶段。

命令超时是速度模式回退，**不会自动发送急停或失能**。需要停止时调用[停止服务](services.md#stop-and-resume)。

速度配置在后台等待物理发送回执，执行器继续处理反馈和服务。此期间仅保留最新合法目标；被替换目标不进入滤波历史，待发年龄达到 `cmd_timeout` 时按主机单调时钟丢弃。新目标成功提交后不会重放旧待发目标。其他生命周期任务忙碌时，目标暂不接收。

速度配置部分失败后，须先恢复所有关节慢速，再接受目标。滤波只提交 SDK 接受的目标；停止、成功回零及超时恢复会清空窗口。P7 的流式输入还受 SDK 速度/加速度限幅，首帧保持测量位置，须持续输入才能推进后续目标。

## 接收状态

```bash
ros2 topic echo /left_arm_joint_state --once
ros2 topic hz /left_arm_joint_state
```

`publish_rate` 是发布定时器频率，不保证电机反馈采样频率。重复缓存可能重复发布相同时间戳，失效或过期时暂停发布。数据采集和闭环控制应检查消息新鲜度，详见[反馈有效性](feedback.md)。

[返回总览](environment_setup.md)
