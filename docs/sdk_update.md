# 更新源码

更新前停止机械臂节点及其他控制程序，保留未提交的本地改动。以下示例假定 ROS2 checkout 在 `main` 且可快进；出现分叉或本地修改冲突时先处理，不使用强制重置。

## 更新 ROS2 与依赖

```bash
ARM_ROS_SOURCE="$HOME/linkerbot_ws/src/linkerbot-arm-ros2"
git -C "$ARM_ROS_SOURCE" remote set-url origin https://github.com/linker-bot/linkerbot-arm-ros2-sdk.git
git -C "$ARM_ROS_SOURCE" status --short --branch
git -C "$ARM_ROS_SOURCE" pull --ff-only origin main

ARM_ROS_DISTRO=humble  # 与已安装环境相同
source "/opt/ros/${ARM_ROS_DISTRO}/setup.bash"
source "$HOME/.venvs/linkerbot-arm-${ROS_DISTRO}/bin/activate"
ARM_CONSTRAINTS=$(python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py" --print-constraints)
python -m pip install --force-reinstall -c "$ARM_CONSTRAINTS" \
  -r "$ARM_ROS_SOURCE/requirements/source-versions.txt"
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
cd ~/linkerbot_ws
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
source install/setup.bash
```

SDK 按 ROS2 清单更新，不自行替换为任意同版本包；transport 从当前 `main` 重新安装，不添加版本、tag 或 SHA 安装约束。HTTPS 可编辑安装用户按[安装说明](INSTALLATION.md#paired-sdk)更新 transport `main` 和清单指定的 SDK checkout 后重装。

## 更换发行版

Humble 与 Jazzy 分别创建新 venv 和工作空间，按[安装与构建](INSTALLATION.md)重新安装，不复用旧发行版的构建结果。更新后核对实际 SDK 来源、节点解释器和配置文件，再[启动设备](getting_started.md)。

[返回总览](environment_setup.md)
