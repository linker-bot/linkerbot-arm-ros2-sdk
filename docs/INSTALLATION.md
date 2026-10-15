# 安装与构建

## 1. 选择 ROS2 发行版

Ubuntu 22.04 使用 **Humble / Python 3.10**；Ubuntu 24.04 使用 **Jazzy / Python 3.12**。先按 [Humble](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html) 或 [Jazzy](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) 官方教程安装 ROS2 并配置 APT 源。以下命令使用 Bash。

每个发行版使用独立终端、venv 和工作空间，不叠加 source 两个发行版，也不复用另一发行版的 `build/`、`install/`、`log/`。

## 2. 获取源码

```bash
mkdir -p ~/linkerbot_ws/src
git clone --branch main https://github.com/linker-bot/linkerbot-arm-ros2-sdk.git ~/linkerbot_ws/src/linkerbot-arm-ros2
```

后续命令假定这个工作空间路径。已有 checkout 可保留原目录名，将 `ARM_ROS_SOURCE` 改为实际路径。

## 3. 创建 Python 环境

```bash
ARM_ROS_DISTRO=humble  # Ubuntu 24.04 改为 jazzy
sudo apt update
sudo apt install python3-venv python3-pip python3-colcon-common-extensions "ros-${ARM_ROS_DISTRO}-pinocchio"
source "/opt/ros/${ARM_ROS_DISTRO}/setup.bash"
/usr/bin/python3 -m venv --system-site-packages "$HOME/.venvs/linkerbot-arm-${ROS_DISTRO}"
source "$HOME/.venvs/linkerbot-arm-${ROS_DISTRO}/bin/activate"

ARM_ROS_SOURCE="$HOME/linkerbot_ws/src/linkerbot-arm-ros2"
ARM_CONSTRAINTS=$(python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py" --print-constraints)
python -m pip install --upgrade -c "$ARM_CONSTRAINTS" 'pip<26' setuptools wheel 'packaging>=24.2'
```

环境检查会核对 Ubuntu、ROS、Python、venv 和真实 ROS 模块。返回错误时先修正环境，再继续安装。

两个发行版 profile 均使用 NumPy 1.26.4、SciPy 1.13.1、setuptools `>=77,<80`，Pinocchio/eigenpy 由对应 ROS APT 包提供。Humble 的系统 NumPy 低于 SDK 要求，须安装 profile 中的版本。

SDK 构造机械臂时需要 Pinocchio，即使只做关节控制也不能省略。此方案安装基础 SDK，**不加 `[kinetix]`**，避免 PyPI `pin` 与 APT 的数值库混用。

<a id="paired-sdk"></a>

## 4. 安装配套 SDK

ROS2 仓库的 [源码清单](https://github.com/linker-bot/linkerbot-arm-ros2-sdk/blob/main/requirements/source-versions.txt) 指定包含可取消回零、发送回执和反馈新鲜度的 SDK 提交。transport 始终从当前 `main` 安装，不限制版本号或 tag。

```bash
python -m pip install --force-reinstall -c "$ARM_CONSTRAINTS" \
  -r "$ARM_ROS_SOURCE/requirements/source-versions.txt"
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
```

清单通过 GitHub HTTPS 获取源码依赖。`--force-reinstall` 使已安装的 transport 也更新到当前源码，不依赖版本号变化。只有相同 SDK 版本号，不能保证包含所需能力。

如需可编辑安装，可先克隆 GitHub 源码；以下依赖目录须尚不存在：

```bash
mkdir -p ~/linkerbot-deps
git clone --branch main https://github.com/linker-bot/linkerbot-transport.git ~/linkerbot-deps/linkerbot-transport
git clone --branch main https://github.com/linker-bot/linkerbot-arm-python-sdk.git ~/linkerbot-deps/linkerbot-arm-python
ARM_SOURCE_COMMIT=$(sed -n 's/^linkerbot-arm @ .*@//p' "$ARM_ROS_SOURCE/requirements/source-versions.txt")
git -C ~/linkerbot-deps/linkerbot-arm-python checkout "$ARM_SOURCE_COMMIT"
python -m pip install -c "$ARM_CONSTRAINTS" -e "$HOME/linkerbot-deps/linkerbot-transport[can]"
python -m pip install -c "$ARM_CONSTRAINTS" -e "$HOME/linkerbot-deps/linkerbot-arm-python"
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
```

## 5. 构建 ROS2 包

```bash
cd ~/linkerbot_ws
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
head -n 1 install/linker_arm_ros2/lib/linker_arm_ros2/arm_node
python -c "import sys; print(sys.executable)"
source install/setup.bash
python "$(command -v ros2)" pkg prefix linker_arm_ros2
```

生成节点首行应指向当前 venv。激活 venv 不会改变 `/usr/bin/colcon` 的解释器，所以使用当前 `python` 执行其入口。构建不会替你安装配套 SDK。

## 新终端使用

```bash
ARM_ROS_DISTRO=humble  # 与安装时相同
source "/opt/ros/${ARM_ROS_DISTRO}/setup.bash"
source "$HOME/.venvs/linkerbot-arm-${ROS_DISTRO}/bin/activate"
source ~/linkerbot_ws/install/setup.bash
```

继续[连接与启动](getting_started.md)。加载到错误 SDK 时，见[故障排查](troubleshooting.md#sdk-source)。

[返回总览](environment_setup.md)
