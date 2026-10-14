# LinkerBot Arm ROS2

[English](README_EN.md)

基于 [linkerbot-arm-python](https://gitea.linkerhub.work/linker-bot/linkerbot-arm-python) 的 ROS2 机械臂控制包，支持 LinkerBot A7、A7 Lite 和 P7 三款 7 自由度机械臂。

源码仓库为 [linker-bot/linkerbot-arm-ros2](https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2)，
默认分支为 `main`。仓库改名后，ROS2 包名和 Python 导入仍为 `linker_arm_ros2`；
SDK 发行包和导入仍为 `linkerbot-arm`、`linkerbot_arm`。

本包提供统一的 ROS2 通信层，同时支持 A7、A7 Lite 和 P7 三款机械臂。SDK 内部已封装 CAN 总线通信、协议编解码、电机管理等底层功能，本包仅负责将 SDK API 桥接到标准的 ROS2 Topic 和 Service。

## 功能特性

- **统一驱动**：通过统一配置文件切换 A7 / A7 Lite / P7，无需两个独立仓库
- **集中配置**：launch 使用的参数集中在 `config/arm_config.yaml` 中管理，修改后重新 launch 即可生效
- **协议-适配器架构**：ROS2 通信层与 SDK 实现完全解耦，SDK 更新时无需修改 ROS2 节点代码
- **流式控制**：使用 `set_angles()` 高频下发目标角度（100 Hz 外部控制指令流），保留节点及 SDK 的停止、任务准入检查
- **关节状态发布**：以可配置频率（默认 100Hz）发布关节角度、速度、力矩
- **关节名称**：与电机 CAN ID 一致（左臂 61-67，右臂 51-57）
- **生命周期服务**：使能、失能、回零、急停、错误重置、零位标定
- **速度管理**：启动慢速 → 延迟后切换正常速度 → 超时无指令自动回退慢速
  速度配置在现有后台 worker 中等待发送回执，指令回调和定时器继续返回，状态发布及停止请求仍可执行。
- **指令拒绝与恢复**：非有限角度在滤波前拒绝；SDK 拒绝的目标不进入滤波历史，
  不刷新首条/最后有效命令计时。首次或恢复控制时先设置慢速，再提交目标。
  速度写入失败会暂停新目标准入，恢复全臂慢速配置后重新开始启动计时。
  回零、停止及命令超时后清空滤波窗口；`filter_window` 必须为正整数。
  以上成功表示 SDK 接受提交，不代表硬件已执行。被拒绝目标记录日志，不自动重放。
- **双臂支持**：同时启动左右臂，各自使用独立 CAN 接口
- **Topic 兼容**：保留话题和消息类型，无名指令保持原有位置顺序；具名指令按 CAN ID 验证和重排
- **系统依赖兼容**：支持 NumPy 1.x 与 ROS2 Pinocchio，安装方案见环境说明

## 前置条件

- ROS2 Humble（Ubuntu 22.04 / Python 3.10）或 Jazzy（Ubuntu 24.04 / Python 3.12）
- CAN 接口已配置并激活（如 `can0`、`can1`）
- `linkerbot-arm` 0.6.x（导入 `linkerbot_arm`），安装或源码部署方式见 [环境配置](docs/environment_setup.md)
- Pinocchio 与 NumPy 的二进制版本匹配，详见环境说明
- 同一 Python 环境已安装 SDK 依赖：NumPy、SciPy、Pydantic 及 `linkerbot-transport[can]`；
  按本仓库的[源码清单](requirements/source-versions.txt)安装配套 arm/transport，
  反馈 SDK 固定到已合入 `main`、完成冲突处理的配套提交；
  transport 使用新组织仓库的 `main`，不限制版本号或 tag，
  详见[环境配置](docs/environment_setup.md#ros2-系统依赖方案)

## 构建

先按操作系统选择发行版：Ubuntu 22.04 使用 **Humble**，Ubuntu 24.04 使用 **Jazzy**。
已有 Humble 用户无需升级系统；新装 Ubuntu 24.04 推荐 Jazzy。
两者使用同一份节点/launch/配置，SDK 安装时按 `ROS_DISTRO` 选择对应 constraints。
每个发行版使用独立 venv 与工作空间，不能混用 Python 或复用另一版本的构建结果。

首次安装先获取 `main` 源码，以下示例使用 `~/linkerbot_ws` 作为工作空间：

```bash
mkdir -p ~/linkerbot_ws/src
git clone --branch main https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2.git ~/linkerbot_ws/src/linkerbot-arm-ros2
```

按[环境配置](docs/environment_setup.md)安装配套 SDK 并激活 venv 后，再构建 ROS2 包：

```bash
cd ~/linkerbot_ws

# 先 source 所选 ROS、激活其 venv，再用该 Python 执行系统 colcon 入口
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
head -n 1 install/linker_arm_ros2/lib/linker_arm_ros2/arm_node
python -c "import sys; print(sys.executable)"
source install/setup.bash
```

生成节点的 shebang 应指向当前 venv。其他环境已有 venv 的 colcon 入口时可直接构建，
仍须核对入口和生成节点的解释器，详见[环境配置](docs/environment_setup.md#ros2-系统依赖方案)。

> 代码核对：ROS2 节点支持 P7；独立标定和生命周期脚本目前仍只支持 A7/A7lite。

无硬件 Docker 验证分别覆盖 Humble 和 Jazzy，入口与源码获取方式见
[docker/README.md](docker/README.md)。测试容器不透传 CAN 或其他设备。

## CAN 设备检测

使用内置检测脚本自动识别各机械臂连接的 CAN 接口：

```bash
# 首次使用需先编译检测程序
g++ scripts/detect_can.cpp -std=c++17 -o scripts/detect_can

# 运行检测（需要 sudo 权限以激活 CAN 接口）
bash scripts/detect_can.sh
```

脚本会自动完成以下步骤：
1. 激活所有 CAN 接口（设置波特率 1 Mbps）
2. 检测各 CAN 总线上连接的设备（灵巧手、机械臂、TA 主控臂）
3. 将检测结果生成到 `scripts/can_config.yaml`

> 如果 sudo 密码与默认值不同，可修改 `scripts/detect_can.sh` 中的 `PASSWORD` 变量，或通过环境变量传入：`PASSWORD=你的密码 bash scripts/detect_can.sh`

检测完成后，将 `scripts/can_config.yaml` 中的 `left_arm` 和 `right_arm` 值复制到 `config/arm_config.yaml`，然后启动双臂：

```bash
# 示例：检测到 left_arm 在 can1，right_arm 在 can2
# 修改 config/arm_config.yaml：
#   left_arm: "can1"
#   right_arm: "can2"

ros2 launch linker_arm_ros2 dual_arm.launch.py
```

## 配置

launch 使用的参数集中在 `config/arm_config.yaml` 中管理：

```yaml
# 机型选择
arm_type: "a7lite"        # a7 | a7lite | p7

# 启动行为
auto_enable: true         # 启动时自动使能电机
calibrate_zero: false     # 启动时标定零位（使能前执行，需确保机械臂在零位姿态）

# CAN 接口
left_arm: "can1"          # 左臂 CAN 接口
right_arm: "can0"         # 右臂 CAN 接口

# 运动参数
position_kp: 25.0        # 仅 A7lite 生效
publish_rate: 100.0       # 状态发布频率 (Hz)
feedback_timeout: 0.5     # 任一反馈字段超过此接收年龄则暂停状态发布 (秒)
cmd_timeout: 6.0          # 无指令超时回退到慢速 (秒)
slow_max_velocity: 0.5    # 慢速上限 (rad/s)
normal_max_velocity: 3.0  # 正常速度上限 (rad/s)
startup_delay: 2.0        # 首次指令后多久切到正常速度 (秒)
filter_window: 1          # 滑动平均滤波器窗口
```

以上 CAN 名为示例，请以实际配置为准。`world_frame` 和 `tcp_offset` 是节点参数，当前 launch 没有从 YAML 转发它们，使用节点默认值。

修改配置后重新启动；如果安装空间复制了配置文件，需要重新构建。

## 使用方法

### 双臂启动（推荐）

```bash
ros2 launch linker_arm_ros2 dual_arm.launch.py
```

所有参数（机型、CAN 接口、速度等）均从 `arm_config.yaml` 读取，无需 launch 参数。

### 单臂启动

```bash
# 启动左臂（默认）
ros2 launch linker_arm_ros2 single_arm.launch.py

# 启动右臂
ros2 launch linker_arm_ros2 single_arm.launch.py side:=right
```

`side` 是唯一的 launch 参数，其他参数均来自 `arm_config.yaml`。

### 通过服务控制

```bash
# 使能
ros2 service call /left_arm_node/enable std_srvs/srv/Trigger

# 失能
ros2 service call /left_arm_node/disable std_srvs/srv/Trigger

# 回零
ros2 service call /left_arm_node/home std_srvs/srv/Trigger

# 急停
ros2 service call /left_arm_node/emergency_stop std_srvs/srv/Trigger
```

## 节点生命周期

节点启动后自动执行以下流程（当 `auto_enable: true` 时）：

```
1. 创建 SDK 实例 → 自动检查 7 个电机通信
2. disable() → 清除旧状态
3. 等待 0.1s → 保留 disable 指令发送余量
4. enable() → 使能电机（内部自动 reset_error + set_control_mode(PP) + enable）
5. 等待 0.2s → 保留使能指令发送余量
6. set_velocities(slow) → 设置慢速
7. 后台执行可取消回零 → 任务完成后开放流式控制
8. 状态发布和服务在启动任务前就已建立，回零期间继续运行
9. 收到控制指令 → set_angles() 流式下发
10. Ctrl+C → 取消任务 → disable() → 等待退出及发送余量 → close()
```

> 步骤 3、5、10 保留发送等待余量，不等同于设备确认；适用于 A7、A7lite 和 P7。

### 速度管理策略

```
                    startup_delay
                    ├──────────┤
  ┌─────────────────┬──────────┬────────────────────┬──────────┐
  │   等待指令      │  慢速    │     正常速度       │ 超时回慢 │
  │ (slow_max_vel)  │(slow)    │ (normal_max_vel)   │ (slow)   │
  └─────────────────┴──────────┴────────────────────┴──────────┘
  ↑                 ↑          ↑                    ↑
  节点启动        首次指令   startup_delay后      cmd_timeout无指令
```

## Topic

| Topic | 类型 | 方向 | 说明 |
|-------|------|------|------|
| `left_arm_joint_state` | `sensor_msgs/JointState` | 发布 | 关节角度 (rad)、速度 (rad/s)、力矩 (Nm)，name=["61","62",...,"67"] |
| `right_arm_joint_state` | `sensor_msgs/JointState` | 发布 | 同上，name=["51","52",...,"57"] |
| `left_arm_joint_control` | `sensor_msgs/JointState` | 订阅 | 目标关节角度，position 字段 (7 个 float, rad) |
| `right_arm_joint_control` | `sensor_msgs/JointState` | 订阅 | 同上，右臂 |

**关节名称（JointState.name）与电机 CAN ID 一致**：
- 左臂：`["61", "62", "63", "64", "65", "66", "67"]`
- 右臂：`["51", "52", "53", "54", "55", "56", "57"]`

状态发布检查七关节的位置、速度和力矩；缺失、非有限、过期或 SDK 关闭/总线报错时暂停，
完整新反馈恢复后继续。重复缓存不会重新打上当前时间戳，
详见[反馈有效性与时间戳](docs/feedback.md)。

控制消息的 `position` 必须有七个有限角度。`name` 非空时必须恰好包含当前臂的七个
CAN ID 名称，每个出现一次；允许任意顺序，节点按名称将角度重排到关节顺序。
未知、重复、缺失名称或长度不一致会拒绝整条指令，不更新滤波历史和有效命令计时。
`name` 为空时保持上述固定位置顺序兼容。

## Service

所有服务使用 `std_srvs/srv/Trigger`，位于节点命名空间下。

| 服务 | 说明 |
|------|------|
| `~/enable` | 使能所有 7 个关节电机 + 慢速回零 |
| `~/disable` | 失能所有 7 个关节电机 |
| `~/home` | 可取消的慢速回零；完成后返回结果，期间其他服务和状态发布可执行 |
| `~/emergency_stop` | 取消当前回零任务并调用 SDK 软件停止；完成后暂停流式目标接收 |
| `~/reset_error` | 重置电机错误状态 |
| `~/calibrate_zero` | 零位标定：将当前位置设为零位（需先失能） |

生命周期任务执行期间，重复的使能/回零/标定请求返回 busy，不排队执行；流式目标暂不接受。
速度配置复用同一个 worker，此时普通服务也返回 busy，但流式指令会保留最新一条
通过关节名称、长度、有限值和滤波校验的待发目标。配置成功后再次经过 SDK 校验才提交，
被替换的目标不进入滤波历史。待发目标按主机单调时钟计算年龄，达到 `cmd_timeout` 即丢弃，
即使 ROS 时钟暂停也不会发送过期目标。
`disable` / `emergency_stop` 可以取消当前任务，被取消的原请求返回 `success=false`。
服务仍使用原来的 `Trigger` 类型，成功响应表示操作已返回，不是仅进入后台队列。
停止后，显式使能或回零成功才恢复流式控制。软件停止仍受 SDK、CAN 排队和驱动耗时影响。
停止会清除待发目标；已进入 SDK 的速度配置可能继续等待回执，停止响应仍需等待
SDK 调用及原 worker 退出，迟到的配置结果不会恢复节点运动状态或提交旧目标。
配套 A7lite SDK 停止也持续锁存，不再等待两秒自动恢复；必须显式 `enable()` 或
成功完成 `home()` / `home_cancellable()` 才重新接收目标。

启动或使能失败会尝试失能并关闭 SDK，记录具体错误；关闭连接后需重启节点。
回零的慢速配置部分失败时，服务返回原始 SDK 错误；后续目标只有在全部关节
重新配置为慢速后才可接收，并从新的滤波历史和启动延时开始。
可取消回零和反馈新鲜度依赖本仓库 `requirements/source-versions.txt` 指定的 arm/transport 源码，
仅有相同版本号不代表代码一致。旧 SDK 会在打开 CAN 前被拒绝，见[环境配置](docs/environment_setup.md)。

## 参数说明

所有参数在 `config/arm_config.yaml` 中配置，通过 launch 文件注入节点。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `arm_type` | string | `"a7"` | 机型：`"a7"`、`"a7lite"` 或 `"p7"` |
| `auto_enable` | bool | `true` | 启动时自动 disable → enable → 慢速回零 |
| `calibrate_zero` | bool | `false` | 启动时标定零位（使能前执行） |
| `left_arm` | string | `"can1"` | 左臂 CAN 接口 |
| `right_arm` | string | `"can0"` | 右臂 CAN 接口 |
| `publish_rate` | double | `100.0` | 状态发布频率 (Hz) |
| `feedback_timeout` | double | `0.5` | 任一关节位置/速度/力矩允许的最大主机接收年龄 (秒) |
| `cmd_timeout` | double | `6.0` | 无指令超时后回退到慢速 (秒) |
| `slow_max_velocity` | double | `0.5` | 慢速上限 (rad/s) |
| `normal_max_velocity` | double | `3.0` | 正常速度上限 (rad/s) |
| `startup_delay` | double | `2.0` | 首次指令后多久切换到正常速度 (秒) |
| `filter_window` | int | `1` | 滑动平均滤波器窗口大小 |

节点在创建 SDK 实例、打开 CAN 前统一校验参数。`side` 只接受 `left` / `right`，
`arm_type` 只接受已注册的三款型号，`world_frame` 为 `urdf` / `maestro`，CAN 接口名须非空。
`auto_enable` 和启动标定开关须为布尔值，`filter_window` 须为正整数；
`publish_rate` 须为有限正值且周期可表示为 ROS 纳秒定时器，`cmd_timeout` 须为有限正值，
`startup_delay` 须为有限非负值，`feedback_timeout` 须为有限正值。
`slow_max_velocity` 范围为 `(0, 50]` rad/s，用于使能后的回零；
`normal_max_velocity` 范围为 `[0, 50]` rad/s。`position_kp` 须有限、非负且可编码为 float32；
`tcp_offset` 必须是三个有限数值。零速配置不代替 SDK 对非零运动所需正速度的检查。

## 关节限位

### A7

| 关节 | URDF 名称 | 左臂 (rad) | 右臂 (rad) | 范围 (°) |
|------|----------|-----------|-----------|---------|
| J1 Shoulder Pitch | Shoulder_Pitch | [-2.97, 1.05] | [-1.05, 2.97] | 230° |
| J2 Shoulder Roll | Shoulder_Roll | [-0.35, 3.49] | [-3.49, 0.35] | 220° |
| J3 Shoulder Yaw | Shoulder_Yaw | [-2.79, 2.79] | [-2.79, 2.79] | 320° |
| J4 Elbow Pitch | Elbow_Pitch | [-0.21, 2.355] | [-0.21, 2.355] | 147° |
| J5 Wrist Yaw | Wrist_Yaw | [-2.79, 2.79] | [-2.79, 2.79] | 320° |
| J6 Wrist Pitch | Wrist_Pitch | [-1.57, 1.57] | [-1.57, 1.57] | 180° |
| J7 Wrist Roll | Wrist_Roll | [-1.57, 1.57] | [-1.57, 1.57] | 180° |

### A7 Lite

| 关节 | URDF 名称 | 左臂 (rad) | 右臂 (rad) | 范围 (°) |
|------|----------|-----------|-----------|---------|
| J1 | L/R1_JOINT | [-2.18, 3.75] | [-3.75, 2.18] | 340° |
| J2 | L/R2_JOINT | [-3.33, 0.19] | [-0.19, 3.33] | 202° |
| J3 | L/R3_JOINT | [-2.26, 2.26] | [-2.26, 2.26] | 259° |
| J4 | L/R4_JOINT | [-0.78, 1.74] | [-1.74, 0.78] | 144° |
| J5 | L/R5_JOINT | [-2.96, 2.96] | [-2.96, 2.96] | 339° |
| J6 | L/R6_JOINT | [-1.57, 1.57] | [-1.57, 1.57] | 180° |
| J7 | L/R7_JOINT | [-1.57, 1.57] | [-1.57, 1.57] | 180° |

> 限位数据来源：`linkerbot-arm/src/linkerbot_arm/arm/kinetix/urdf/`

## 架构设计

```
┌──────────────────────────────────────────────────────────────┐
│                      arm_node.py (ROS2)                       │
│  Publisher / Subscriber / Services / 速度管理                  │
│  set_angles() 流式控制 | 100Hz 状态发布                        │
│  只依赖 ArmProtocol 接口，不感知 SDK 实现                       │
└──────────────────┬───────────────────────────────────────────┘
                   │ create_arm()
┌──────────────────▼───────────────────────────────────────────┐
│                    arm_factory.py                              │
│  根据 arm_type 创建对应的 Adapter 实例                          │
└──────────────────┬───────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────┐
│              arm_protocol.py (ABC)                             │
│  enable / disable / set_angles / set_velocities               │
│  get_angles / get_velocities / get_torques / ...              │
└──────────────────┬───────────────────────────────────────────┘
                   │ 实现
┌──────────────────▼───────────────────────────────────────────┐
│             sdk_adapter.py                                    │
│  LinkerBotSDKAdapter — 调用独立 linkerbot_arm SDK           │
│  SDK 加载：已安装包 → 显式源码变量 → 独立 arm 仓库             │
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
| 用途 | 外部控制指令流（100 Hz） | 点到点运动 |
| 任务准入 | 节点门禁及 SDK 型号对应的检查 | SDK 点到点任务检查 |
| 运动任务 | 不启动点到点任务 | 按型号使用计时或轨迹任务 |
| 底层调用 | `_set_angles()`，P7 自动限幅 | SDK 规划/计时后的目标提交 |
| 控制模式 | SDK PP 接口；P7 J6/J7 为 PTM | SDK PP 接口；P7 J6/J7 为 PTM |

本节点使用 `set_angles()` 进行流式控制，`move_j()` 仅在 `home()` 内部使用。

配套 SDK 将 P7 外部流式目标按当前逐关节速度、加速度配置限幅，覆盖 J6/J7；
每次开始或恢复流式控制的首帧从测量位置建立状态并保持当前位置。
之后需要周期性发送外部控制指令，才能逐步趋近目标；单次消息不会完成点到点运动。
SDK 使用单调时钟，按相邻受理目标之间的实际时间间隔计算速度和加速度限制。
限幅约束的是提交的目标轨迹，不能代替实测速度或到位确认。

独立标定及生命周期脚本的检查边界和退出清理见[环境说明](docs/environment_setup.md#独立工具与检查边界)。

本文中的“外部控制指令”指外部程序发布到 `left_arm_joint_control` 或
`right_arm_joint_control` 的 `JointState` 消息，每条消息包含七个关节的目标角度。

## SDK 加载与过渡支持

适配器、标定和生命周期脚本共用 `sdk_loader.py`，加载顺序为：

1. 当前 Python 环境可导入的 `linkerbot_arm`（包括已安装包及已配置的 Python 搜索路径）。
2. `LINKERBOT_ARM_SRC=/path/to/linkerbot-arm-python/src`，也接受仓库根目录。
3. 未设置新变量时，兼容 `LINKERBOT_SDK_SRC`；其路径也必须提供新 `linkerbot_arm`，使用时输出迁移提示。
4. ROS2 仓库旁或祖先工作空间 `src/` 下的旧目录名 `linkerbot-arm`。

新目录名 `linkerbot-arm-python` 不在自动发现范围内，需安装到当前 Python 环境，
或显式设置上述 `LINKERBOT_ARM_SRC`。

节点和工具只加载 `linkerbot_arm`。新旧两个源码变量都只接受该命名空间，
不再解析旧完整 SDK 的 `linkerbot` 源码，也不将已安装的旧 `linkerbot` 作为回退来源。
当前节点仍会在打开 CAN 前检查新 SDK 的可取消回零能力。
显式路径无效或 SDK 缺少依赖时会报出对应错误，不会静默加载另一份源码。
环境变量不会覆盖已可导入的独立 arm 包；切换来源后重启 Python 进程。

ROS2 直接依赖 `linkerbot-arm>=0.6.0,<0.7.0`，无需聚合包或 hand 包。
独立包分别使用 `linkerbot_arm`、`linkerbot_hand`、`linkerbot_transport`，可以共存安装。

## 环境策略

使用与 ROS2 发行版匹配的 Python，SDK 安装、colcon 构建和节点运行使用同一个环境。
ROS2 系统 Pinocchio/NumPy 组合与 PyPI `kinetix` extra 的二进制依赖应分别配置。
Humble 和 Jazzy 都使用读取系统包的 venv；本仓库的
`constraints/ros-humble.txt` / `constraints/ros-jazzy.txt` 固定 NumPy 1.26.4、SciPy 1.13.1，
并限定兼容 colcon 的 setuptools >=77,<80。Pinocchio/eigenpy 由对应 ROS APT 包提供。

- `linkerbot-arm`：0.6.x，按源码清单安装配套反馈 SDK 的固定提交。
- `linkerbot-transport`：新组织仓库的 `main`，不固定版本号、tag 或旧提交。
- Pydantic：2.x。
- A7、A7lite、P7 构造均需要运动学，即使只使用关节控制也需要 Pinocchio。

安装命令、公司 transport 包源与无硬件检查见 [环境配置](docs/environment_setup.md)。

ROS2 安装基础 SDK，不带 `kinetix` extra；该 extra 只负责 pip 安装依赖，已有兼容
Pinocchio 的基础包同样提供运动学。SDK 保留的 `constraints/ros2.txt` 表示通用兼容范围，
安装本包使用本仓库的发行版 profile。当前旧完整 SDK 要求 NumPy >=2.2.6，
与上述 profile 不兼容；继续使用旧 SDK 时保留其独立环境。

## 文件结构

```
linkerbot-arm-ros2/
├── package.xml                  # ROS2 包清单
├── setup.py                     # Python 打包配置
├── setup.cfg                    # 安装脚本路径
├── README.md                    # 中文说明（默认）
├── README_EN.md                 # English documentation
├── resource/linker_arm_ros2     # ament 资源标记
├── constraints/                # Humble / Jazzy 的 pip 依赖约束
├── docker/                     # 两个发行版的无硬件构建与测试入口
│
├── config/
│   └── arm_config.yaml          # 统一配置文件（机型、CAN、运动参数）
│
├── linker_arm_ros2/             # Python 包
│   ├── __init__.py
│   ├── arm_protocol.py          # 抽象接口 (ABC)
│   ├── sdk_loader.py            # Shared SDK discovery
│   ├── sdk_adapter.py           # 独立 arm SDK 的 ArmProtocol 适配器
│   ├── arm_factory.py           # 工厂模式：创建 ArmProtocol 实例
│   └── arm_node.py              # ROS2 主节点
│
├── launch/
│   ├── single_arm.launch.py     # 单臂启动（从 arm_config.yaml 读取配置）
│   └── dual_arm.launch.py       # 双臂启动（从 arm_config.yaml 读取配置）
│
├── scripts/
│   ├── check_ros_environment.py # 发行版/Python/依赖与真实 URDF 检查（无 CAN）
│   ├── detect_can.cpp           # CAN 设备自动检测程序（需用 g++ 编译）
│   ├── detect_can.sh            # 检测脚本（自动激活 CAN 接口，sudo 执行）
│   └── test_lifecycle.py        # SDK 生命周期测试（enable/disable/home/stream/close）
│
└── docs/
    └── environment_setup.md     # 环境配置说明
```

## 扩展新机型

如需接入新品牌/型号的机械臂：

1. 编写新的适配器文件（如 `new_brand_adapter.py`）实现 `ArmProtocol`
2. 在 `arm_factory.py` 中根据 `arm_type` 添加分支
3. `arm_node.py` 和 launch 文件无需任何修改

## License

Apache-2.0
