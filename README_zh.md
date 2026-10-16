# LinkerBot Arm ROS2

[English](README.md) | 简体中文

通过 ROS2 话题和服务控制 LinkerBot A7、A7 Lite、P7 左右机械臂，基于独立 `linkerbot-arm` SDK。支持 Ubuntu 22.04 / Humble / Python 3.10 与 Ubuntu 24.04 / Jazzy / Python 3.12。

## 开始使用

1. [安装与构建](docs/INSTALLATION.md)：创建对应 ROS Python 环境并安装配套 SDK。
2. [连接与启动](docs/getting_started.md)：配置 CAN、选择型号、启动单臂或双臂。
3. [话题与关节控制](docs/topics.md)：读取状态、发送七关节目标。

完整说明见[开发者使用手册](docs/environment_setup.md)，包含配置、生命周期服务、反馈时间戳、标定、故障排查及[Docker 验证](docs/testing.md)。

ROS2 包和 Python 导入名保持 `linker_arm_ros2`。SDK/transport 按本仓库的[源码清单](requirements/source-versions.txt)安装；transport 使用当前 `main`，无版本或 tag 约束。默认配置启动后会自动使能并回零；首次使用按启动教程先关闭自动使能。

## 开发与验证

Humble/Jazzy 共用节点、launch 和配置。开发者检查入口见[测试与 Docker 验证](docs/testing.md)；无硬件测试不代表实机运动、停止或标定效果已验证。

源码：[linker-bot/linkerbot-arm-ros2-sdk](https://github.com/linker-bot/linkerbot-arm-ros2-sdk)。

## 贡献与许可证

欢迎用中文或英文参与贡献，请遵循[Linkerbot 贡献指南](https://github.com/linker-bot/.github/blob/main/CONTRIBUTING.md)。
安全问题请按[组织安全策略](https://github.com/linker-bot/.github/blob/main/SECURITY.md)私下报告。

本项目采用 [MIT 许可证](LICENSE)。
