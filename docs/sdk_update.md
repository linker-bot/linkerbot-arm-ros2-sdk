# 更新源码

更新前停止机械臂节点及其他控制程序，保留未提交的本地改动。以下命令切换到 `main` 并快进更新；出现分叉或本地修改冲突时先处理，不使用强制重置。

## 更新 ROS2 与依赖

```bash
ARM_ROS_SOURCE="$HOME/linkerbot_ws/src/linkerbot-arm-ros2"
git -C "$ARM_ROS_SOURCE" remote set-url origin https://github.com/linker-bot/linkerbot-arm-ros2-sdk.git
git -C "$ARM_ROS_SOURCE" status --short --branch
git -C "$ARM_ROS_SOURCE" switch main
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

源码清单会重新安装 SDK 和 Transport 的最新 `main` 分支。HTTPS 可编辑安装用户先更新已有依赖目录：

```bash
git -C "$HOME/linkerbot-deps/linkerbot-transport" switch main
git -C "$HOME/linkerbot-deps/linkerbot-transport" pull --ff-only origin main
git -C "$HOME/linkerbot-deps/linkerbot-arm-python" switch main
git -C "$HOME/linkerbot-deps/linkerbot-arm-python" pull --ff-only origin main
```

然后按[安装说明](INSTALLATION.md#paired-sdk)重新执行可编辑安装并检查环境。

## 更换发行版

Humble 与 Jazzy 分别创建新 venv 和工作空间，按[安装与构建](INSTALLATION.md)重新安装，不复用旧发行版的构建结果。更新后核对实际 SDK 来源、节点解释器和配置文件，再[启动设备](getting_started.md)。

[返回总览](environment_setup.md)
