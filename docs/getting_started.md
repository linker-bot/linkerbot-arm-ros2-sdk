# 连接与启动

## 1. 准备 CAN 接口

A7、A7 Lite、P7 使用经典 CAN，通信速率为 1 Mbit/s。Linux 需先安装适配器驱动并确认系统提供 `can0` 等 SocketCAN 接口，再配置：

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
ip -details link show can0
```

将 `can0` 替换为实际接口，双臂分别配置各自接口。需要自动定位接口时，见[CAN 检测工具](tools.md#can-detection)。

<a id="configure"></a>

## 2. 确认配置

编辑 `~/linkerbot_ws/src/linkerbot-arm-ros2/config/arm_config.yaml`。首次单臂连接示例：

```yaml
arm_type: "a7lite"  # a7 | a7lite | p7
auto_enable: false
calibrate_zero: false
left_arm: "can0"
right_arm: "can1"
```

修改对应字段，保留文件里的其余参数。仓库默认接口为左臂 `can4`、右臂 `can2`，须按实际设备替换。`auto_enable: false` 避免启动即回零；它不会失能已经由其他程序使能的硬件。所有配置值见[配置参数](configuration.md)。

launch 读取安装空间中的配置。修改后重新构建，保证启动时使用新文件：

```bash
cd ~/linkerbot_ws
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
source install/setup.bash
cat install/linker_arm_ros2/share/linker_arm_ros2/config/arm_config.yaml
```

## 3. 启动单臂或双臂

在已[激活 ROS 和 venv](INSTALLATION.md#新终端使用)的终端运行：

```bash
# 左臂
ros2 launch linker_arm_ros2 single_arm.launch.py
# 右臂：在另一次启动时使用
ros2 launch linker_arm_ros2 single_arm.launch.py side:=right
# 双臂：替代上述单臂启动
ros2 launch linker_arm_ros2 dual_arm.launch.py
```

选择其中一种启动方式，同一机械臂只运行一个控制进程。单臂唯一 launch 参数为 `side`，其他参数从 YAML 读取；双臂没有 launch 参数。

## 4. 读取状态

在另一个已激活相同环境的终端执行：

```bash
ros2 node list
ros2 topic echo /left_arm_joint_state --once
```

左臂 `name` 为 `"61"` 到 `"67"`，右臂为 `"51"` 到 `"57"`。`position` 单位 rad，`velocity` 单位 rad/s，`effort` 单位 N·m。仅完整且新鲜的反馈会发布；没有消息时查看[反馈有效性](feedback.md)。

## 5. 使能并回零

确认机械臂周围有足够回零空间后调用：

```bash
ros2 service call /left_arm_node/enable std_srvs/srv/Trigger '{}'
```

此服务执行失能、使能和慢速回零，不只是打开电机。收到 `success: true` 后再开始控制。右臂将路径改为 `/right_arm_node/enable`。继续阅读 [A7](tutorials/a7.md)、[A7 Lite](tutorials/a7lite.md) 或 [P7](tutorials/p7.md) 的目标与反馈示例；通用消息格式见[话题与关节控制](topics.md)。

## 6. 停止与退出

```bash
# 软件停止：保持节点运行，暂停后续目标
ros2 service call /left_arm_node/emergency_stop std_srvs/srv/Trigger '{}'
# 失能
ros2 service call /left_arm_node/disable std_srvs/srv/Trigger '{}'
```

停止后须显式使能或成功回零才恢复控制。退出时在 launch 终端按 Ctrl+C，节点会取消任务、尝试失能并关闭 SDK；清理异常须根据日志处理。服务语义与响应边界见[生命周期服务](services.md)。

[返回总览](environment_setup.md)
