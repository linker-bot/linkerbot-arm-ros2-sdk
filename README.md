# linker_arm_ros2

[English](README_EN.md)

基于 [linkerbot-arm](https://gitea.linkerhub.work/zhuzhixiang/linkerbot-arm) 的 ROS2 机械臂控制包，支持 LinkerBot A7、A7 Lite 和 P7 三款 7 自由度机械臂。

本包提供统一的 ROS2 通信层，同时支持 A7、A7 Lite 和 P7 三款机械臂。SDK 内部已封装 CAN 总线通信、协议编解码、电机管理等底层功能，本包仅负责将 SDK API 桥接到标准的 ROS2 Topic 和 Service。

## 功能特性

- **统一驱动**：通过统一配置文件切换 A7 / A7 Lite / P7，无需两个独立仓库
- **集中配置**：launch 使用的参数集中在 `config/arm_config.yaml` 中管理，修改后重新 launch 即可生效
- **协议-适配器架构**：ROS2 通信层与 SDK 实现完全解耦，SDK 更新时无需修改 ROS2 节点代码
- **流式控制**：使用 `set_angles()` 高频下发目标角度（100Hz 遥操作），绕过 SDK 的 `move_j()` motion guard
- **关节状态发布**：以可配置频率（默认 100Hz）发布关节角度、速度、力矩
- **关节名称**：与电机 CAN ID 一致（左臂 61-67，右臂 51-57）
- **生命周期服务**：使能、失能、回零、急停、错误重置、零位标定
- **速度管理**：启动慢速 → 延迟后切换正常速度 → 超时无指令自动回退慢速
- **双臂支持**：同时启动左右臂，各自使用独立 CAN 接口
- **Topic 兼容**：与现有下游节点完全兼容，无需修改
- **系统依赖兼容**：支持 NumPy 1.x 与 ROS2 Pinocchio，安装方案见环境说明

## 前置条件

- ROS2 Jazzy（或 Humble）
- Python 3.10+（使用对应 ROS2 发行版的 Python）
- CAN 接口已配置并激活（如 `can0`、`can1`）
- `linkerbot-arm` 0.6.x（导入 `linkerbot_arm`），安装或源码部署方式见 [环境配置](docs/environment_setup.md)
- Pinocchio 与 NumPy 的二进制版本匹配，详见环境说明
- 同一 Python 环境已安装 SDK 依赖：NumPy、SciPy、Pydantic 及 `linkerbot-transport[can]==1.0.0`

## 构建

```bash
cd ~/linkerbot_data_collection/linkerhand_data_collection_ws

# 先按环境配置安装独立 arm SDK，使用同一 Python 环境中的 colcon。
# 源码部署时，也可将 linkerbot-arm 放到 src/linkerbot-arm。

# 构建
colcon build --packages-select linker_arm_ros2 --symlink-install
source install/setup.bash
```

> 代码核对：ROS2 节点支持 P7；独立标定和生命周期脚本目前仍只支持 A7/A7lite。

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
2. 检测各 CAN 总线上连接的设备（灵巧手、机械臂、TA 遥操臂）
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
3. 等待 0.1s → 确保电机处理完 disable 指令
4. enable() → 使能电机（内部自动 reset_error + set_control_mode(PP) + enable）
5. 等待 0.2s → 确保所有电机完成使能
6. set_velocities(slow) → 设置慢速
7. home(blocking=True) → 阻塞等待回零完成
8. 进入控制循环 → 100Hz 发布状态
9. 收到控制指令 → set_angles() 流式下发
10. Ctrl+C → disable() → 等待 0.5s → close()
```

> 步骤 3、5、10 的等待时间是为了确保 CAN 帧发送完成，避免因 ROS2 多线程环境导致的时序问题。
> 此策略同时适用于 A7 和 A7Lite 机械臂。

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

## Service

所有服务使用 `std_srvs/srv/Trigger`，位于节点命名空间下。

| 服务 | 说明 |
|------|------|
| `~/enable` | 使能所有 7 个关节电机 + 慢速回零 |
| `~/disable` | 失能所有 7 个关节电机 |
| `~/home` | 回零：慢速移动到零位（阻塞等待完成） |
| `~/emergency_stop` | 急停：立即停止运动，锁定当前位姿 |
| `~/reset_error` | 重置电机错误状态 |
| `~/calibrate_zero` | 零位标定：将当前位置设为零位（需先失能） |

## 参数说明

所有参数在 `config/arm_config.yaml` 中配置，通过 launch 文件注入节点。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `arm_type` | string | `"a7"` | 机型：`"a7"` 或 `"a7lite"` |
| `auto_enable` | bool | `true` | 启动时自动 disable → enable → 慢速回零 |
| `calibrate_zero` | bool | `false` | 启动时标定零位（使能前执行） |
| `left_arm` | string | `"can1"` | 左臂 CAN 接口 |
| `right_arm` | string | `"can0"` | 右臂 CAN 接口 |
| `publish_rate` | double | `100.0` | 状态发布频率 (Hz) |
| `cmd_timeout` | double | `6.0` | 无指令超时后回退到慢速 (秒) |
| `slow_max_velocity` | double | `0.5` | 慢速上限 (rad/s) |
| `normal_max_velocity` | double | `3.0` | 正常速度上限 (rad/s) |
| `startup_delay` | double | `2.0` | 首次指令后多久切换到正常速度 (秒) |
| `filter_window` | int | `1` | 滑动平均滤波器窗口大小 |

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
| 用途 | 流式遥操作（100Hz） | 点到点运动 |
| motion guard | 无 | 有（运动中禁止调用） |
| motion timer | 不启动 | 启动（估计运动完成时间） |
| 底层调用 | `_set_angles()` | `_set_angles()` + timer |
| 控制模式 | PP | PP |

本节点使用 `set_angles()` 进行流式控制，`move_j()` 仅在 `home()` 内部使用。

## SDK 加载与过渡支持

适配器、标定和生命周期脚本共用 `sdk_loader.py`，加载顺序为：

1. 当前 Python 环境可导入的 `linkerbot_arm`（包括已安装包及已配置的 Python 搜索路径）。
2. `LINKERBOT_ARM_SRC=/path/to/linkerbot-arm/src`，也接受仓库根目录。
3. 旧变量 `LINKERBOT_SDK_SRC` 显式指定的源码，保留一个过渡周期；使用时输出迁移提示。
4. ROS2 仓库旁或祖先工作空间 `src/` 下的 `linkerbot-arm`。

旧完整 SDK 目录不再自动查找，也不会自动改用环境中已安装的旧 `linkerbot`。
旧变量可临时指向旧完整 SDK 的源码；新变量只接受 `linkerbot_arm` 命名空间。
显式路径无效或 SDK 缺少依赖时会报出对应错误，不会静默加载另一份源码。
环境变量不会覆盖已可导入的独立 arm 包；切换来源后重启 Python 进程。

ROS2 直接依赖 `linkerbot-arm>=0.6.0,<0.7.0`，无需聚合包或 hand 包。
独立包分别使用 `linkerbot_arm`、`linkerbot_hand`、`linkerbot_transport`，可以共存安装。

## 环境策略

使用与 ROS2 发行版匹配的 Python，SDK 安装、colcon 构建和节点运行使用同一个环境。
ROS2 系统 Pinocchio/NumPy 组合与 PyPI `kinetix` extra 的二进制依赖应分别配置。

| 依赖 | 版本与来源 |
|------|------|
| linkerbot-arm | 0.6.x，固定已验证的发行版本或源码提交 |
| linkerbot-transport | 1.0.0，公司包源或固定源码提交 |
| NumPy / SciPy | 满足 SDK 最低版本，并匹配所选 Pinocchio 二进制依赖 |
| Pydantic | 2.x |
| Pinocchio | 三型号构造均需要，即使只使用关节控制 |

安装命令、公司 transport 包源与无硬件检查见 [环境配置](docs/environment_setup.md)。

## 文件结构

```
linker_arm_ros2/
├── package.xml                  # ROS2 包清单
├── setup.py                     # Python 打包配置
├── setup.cfg                    # 安装脚本路径
├── README.md                    # 中文说明（默认）
├── README_EN.md                 # English documentation
├── resource/linker_arm_ros2     # ament 资源标记
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
