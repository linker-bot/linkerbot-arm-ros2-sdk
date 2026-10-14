# 故障排查

按环境 → CAN → 节点 → 服务 → 话题顺序检查。先保留具体错误信息，避免在不明原因时反复使能或标定。

## 安装与解释器

出现 `ModuleNotFoundError`、NumPy ABI 错误或 `packaging.licenses` 缺失时，确认已 source 正确 ROS、激活对应系统 Python venv，并使用发行版 constraints：

```bash
python -c "import sys; print(sys.executable)"
python -c "import numpy, scipy, pinocchio; print(numpy.__version__, scipy.__version__, pinocchio.__file__)"
python -m pip check
head -n 1 ~/linkerbot_ws/install/linker_arm_ros2/lib/linker_arm_ros2/arm_node
```

节点解释器须与安装 SDK 的 venv 一致。不要将 PyPI `pin`/NumPy 2 组合混入 APT Pinocchio profile；按[安装与构建](INSTALLATION.md)重建独立环境。

<a id="sdk-source"></a>

## SDK 来源错误

```bash
python -c "import linkerbot_arm; print(linkerbot_arm.__file__)"
```

正常可导入的 `linkerbot_arm` 优先于源码环境变量。需源码加载时可设置：

```bash
export LINKERBOT_ARM_SRC=/absolute/path/to/linkerbot-arm-python/src
```

也接受仓库根目录，但不会覆盖已可导入的 SDK。修改来源后重启 Python/节点。自动发现只识别旧目录名 `linkerbot-arm`；新目录名应安装或显式设置路径。旧 `LINKERBOT_SDK_SRC` 只是兼容别名，不加载旧 `linkerbot` 聚合包。缺少 `home_cancellable` / `get_feedback` 时按当前源码清单重新安装。

## CAN 或电机初始化失败

```bash
ip -details link show can0
ros2 node list
```

检查接口名、1 Mbit/s、供电、接线、终端电阻、左右臂和型号。节点构造 SDK 时检查七个电机；任何一个不可达都可能导致失败。launch 设置了 `respawn: true`、3 秒重启延迟，反复重启说明初始化或环境仍未解决。先停止 launch，再单独检查，避免并发控制。

## 服务失败或 busy

读取 `Trigger.message`。普通服务与速度配置共用 worker，忙碌时返回失败；停止服务可取消活动任务。`home` 要求已使能，标定要求失能。启动/使能失败关闭连接后需重启节点。详见[生命周期服务](services.md)。

## 状态话题没有消息

```bash
ros2 topic list
ros2 topic info /left_arm_joint_state --verbose
```

确认侧别、namespace、ROS domain 和 QoS。查看节点的 `Joint state publication paused` 日志，可能是字段未齐、过期、CAN 故障或时钟周期尚未建立；重复缓存不会变成新数据。恢复说明见[反馈有效性](feedback.md)。

## 控制目标不生效

先确认使能/回零服务成功，再检查七个有限角度、关节名称、SDK 限位以及节点日志。停止后须显式使能或成功回零；生命周期忙碌时不接收目标，速度配置时仅保留最新合法目标。控制消息的速度字段不会配置电机速度。详见[话题与关节控制](topics.md)。

P7 首帧保持测量位置，后续输入受速度/加速度限幅；测试流式控制时须持续发布。`cmd_timeout` 只回退慢速，不等于停止。

## 修改配置未生效

检查 `install/linker_arm_ros2/share/linker_arm_ros2/config/arm_config.yaml`，重新构建并重启。不要将 YAML 的 `left_arm` 或 `calibrate_zero` 当成节点参数名；也不能仅靠 `ros2 param set` 改变已初始化的控制行为。

[返回总览](environment_setup.md)
