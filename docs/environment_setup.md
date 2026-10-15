# 机械臂 ROS2 使用手册

`linker_arm_ros2` 将机械臂 Python SDK 接入 ROS2，提供七关节目标话题、关节状态话题和生命周期服务。支持 A7、A7 Lite、P7 的左臂与右臂。

## 快速开始

[安装与构建](INSTALLATION.md)：选择 Humble 或 Jazzy，安装配套 SDK，构建 ROS2 包。完成后先连接设备，再按型号阅读设备功能。

首次使用前请确认型号、左右臂和 CAN 接口。仓库默认 `auto_enable: true`，启动后会使能并慢速回零；[入门示例](getting_started.md)先关闭自动使能，再通过服务启动运动。

### 支持环境

| 系统 | ROS2 | Python |
| --- | --- | --- |
| Ubuntu 22.04 | Humble | 3.10 |
| Ubuntu 24.04 | Jazzy | 3.12 |

两者使用同一份节点和配置，虚拟环境及构建空间须分别创建。其他系统或 CPU 架构需自行验证。

## 连接设备

- [连接与启动](getting_started.md)：配置 CAN 接口，启动单臂或双臂，读取首条状态。
- [配置参数](configuration.md)：型号、接口、速度、滤波和反馈超时。

<a id="models"></a>

## 设备功能

选择对应型号，展开配置、关节控制、反馈、停止及型号差异；Humble 与 Jazzy 共用教程。

| 型号 | 功能教程 |
| --- | --- |
| [A7](tutorials/a7.md) | V1 电机 PP 点位控制、左右臂目标和反馈 |
| [A7 Lite](tutorials/a7lite.md) | PP 控制与位置 KP，说明 MIT / CSP 接口边界 |
| [P7](tutorials/p7.md) | V1 / V2 混合关节，持续目标与主机限幅 |

通用接口集中说明，型号教程引用它们：

- [话题与关节控制](topics.md)：目标格式、具名关节、速度切换和滤波。
- [生命周期服务](services.md)：使能、失能、回零、软件停止、错误重置和标定。
- [反馈有效性](feedback.md)：数据暂停、恢复和 `header.stamp` 的含义。

ROS2 当前不支持 H75，也没有暴露 SDK 的全部控制模式或笛卡尔运动学接口。

## 补充说明

- [标定与诊断工具](tools.md)：CAN 检测、零位标定及 SDK 生命周期检查。
- [测试与 Docker 验证](testing.md)：无硬件检查、Humble/Jazzy 测试和验证范围。
- [故障排查](troubleshooting.md)：安装、启动、数据读取和控制问题。
- [更新源码](sdk_update.md)：更新 ROS2、配套 SDK 和 transport。

### 项目名称

| 对象 | 名称 |
| --- | --- |
| ROS2 源码仓库 | [linkerbot-arm-ros2-sdk](https://github.com/linker-bot/linkerbot-arm-ros2-sdk) |
| ROS2 包 / Python 导入 | `linker_arm_ros2` |
| SDK 源码仓库 | [linkerbot-arm-python-sdk](https://github.com/linker-bot/linkerbot-arm-python-sdk) |
| SDK 发行包 / Python 导入 | `linkerbot-arm` / `linkerbot_arm` |
| 通信依赖 | [linkerbot-transport](https://github.com/linker-bot/linkerbot-transport) |

本包只依赖独立 arm SDK 和 transport，无需安装 hand SDK 或旧聚合 SDK。
