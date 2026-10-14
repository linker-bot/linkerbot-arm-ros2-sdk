# 标定与诊断工具

以下工具从 ROS2 源码目录运行，使用已激活的[配套 Python 环境](INSTALLATION.md)。同一设备只允许一个控制进程；检测、标定和 SDK 生命周期工具应在对应机械臂节点及其他控制程序停止后运行。

<a id="can-detection"></a>

## CAN 接口检测

```bash
cd ~/linkerbot_ws/src/linkerbot-arm-ros2
g++ scripts/detect_can.cpp -std=c++17 -o scripts/detect_can
sudo scripts/detect_can
cat scripts/can_config.yaml
```

检测程序枚举接口，尝试激活未启用的接口为 1 Mbit/s，并通过主动探测识别设备。结果写入可执行文件所在目录的 `can_config.yaml`。它不修改 `config/arm_config.yaml`；核对结果后手动复制左右臂接口名，再重新构建。

## ROS2 零位服务

节点支持 A7、A7 Lite、P7 的零位服务。确认失能与物理零位后调用[calibrate_zero](services.md#zero-calibration)。该服务保存零位，不执行独立工具的交互确认和重连验证。

<a id="zero-calibration"></a>

## 独立零位标定

`scripts/calibrate_arm_zero.py` 仅支持 **A7 / A7 Lite**，按配置连接设备、确认物理零位、写入标定、重连并慢速回零验证。建议先逐臂执行：

```bash
cd ~/linkerbot_ws/src/linkerbot-arm-ros2
python scripts/calibrate_arm_zero.py --side left --config config/arm_config.yaml
# 查看全部选项，不连接机械臂
python scripts/calibrate_arm_zero.py --help
```

| 常用选项 | 默认值 | 含义 |
| --- | --- | --- |
| `--side` | `both` | `left`、`right` 或 `both` |
| `--home-velocity` | `0.3` | 回零验证速度，rad/s |
| `--tolerance` | `0.05` | 每关节回零允许绝对误差，rad |
| `--disable-only` | 关闭 | 仅连接并失能，不标定或回零 |

工具查询当前 ROS domain 的节点图，发现默认机械臂节点或查询失败时拒绝标定。这是图快照，不是设备互斥锁；无法识别任意改名节点、其他 domain 或独立 SDK 进程。操作者仍需停止所有可能控制该设备的程序。

工作空间存在 `task_config.json` 且型号不匹配时拒绝继续；先修正配置。`--ignore-config-mismatch` 仅在人工确认 YAML 与真机一致后使用。工具退出会尝试失能并关闭设备，清理失败会记录错误。

## 独立 SDK 生命周期检查

仅支持 **A7 / A7 Lite**，可用于区分 SDK 通信问题和 ROS2 集成问题：

```bash
cd ~/linkerbot_ws/src/linkerbot-arm-ros2
python scripts/test_lifecycle.py --single left --arm-type a7lite --left-can can0
```

该工具会使能、回零并发送流式目标，**会产生真实运动**，不是无硬件单元测试。SIGINT/SIGTERM 请求取消回零，随后尝试逐臂失能及关闭。无硬件测试见[测试与 Docker 验证](testing.md)。

[返回总览](environment_setup.md)
