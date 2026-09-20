# ROS2 与独立 arm SDK 环境配置

ROS2 直接依赖 `linkerbot-arm>=0.6.0,<0.7.0`，Python 导入为 `linkerbot_arm`。
无需完整 SDK 聚合包或 hand 包；三个独立包使用不同命名空间，可以共存安装。

## 运行依赖

- A7、A7lite、P7 导入时需要 NumPy/SciPy，构造时均创建 `ArmKinetix` 并加载 Pinocchio。
- 即使只使用关节控制，也需要 Pinocchio；源码加载同样需要完整运行依赖。
- arm 固定依赖 `linkerbot-transport[can]==1.0.0`；ROS2 无需维护另一份通信实现。
- SDK 基础依赖要求 NumPy >=1.24、SciPy >=1.10、Pydantic 2.x、python-can >=4.6.1。

## ROS2 系统依赖方案

使用对应 ROS2 发行版的 Python，例如 Jazzy 的系统 Python 3.12。系统 Pinocchio 已可用时，
安装基础 SDK，不额外安装 PyPI 的 `pin`。需要系统依赖时可执行：

```bash
sudo apt install python3-numpy python3-scipy python3-venv ros-jazzy-pinocchio
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 -m venv --system-site-packages /path/to/ros-arm-venv
source /path/to/ros-arm-venv/bin/activate
```

当前节点的可取消生命周期需要配套的 arm/transport 源码。使用已有 SSH 权限安装本仓库
`requirements/source-versions.txt` 固定的提交；版本号相同的旧 wheel 可能不包含所需能力。

```bash
# arm checkout 提供与系统 ROS2 二进制库匹配的约束文件。
git clone ssh://git@git.linkerhub.work:12222/zhuzhixiang/linkerbot-arm.git /path/to/linkerbot-arm
git -C /path/to/linkerbot-arm checkout d6d9fc0937e93aa2a77486671fef8de3120b7e6c
python -m pip install -c /path/to/linkerbot-arm/constraints/ros2.txt \
  -r /path/to/linker_arm_ros2/requirements/source-versions.txt
python -m pip install colcon-common-extensions
```

也可将 transport 和 arm 分别检出到清单中的提交，在同一 Python 环境先后执行
`pip install -e /path/to/linkerbot-transport` 和 `pip install -e /path/to/linkerbot-arm`，
并使用适合当前 ROS2 二进制环境的约束。节点在创建 SDK 对象前检查 `home_cancellable`，
缺少时明确提示更新，不会打开 CAN 或尝试旧的不可取消回零。

`constraints/ros2.txt` 将 NumPy 限制为 1.x、SciPy 限制为兼容区间，供采用 NumPy 1.x
系统二进制库的部署使用。自行安装 Pinocchio wheel 的环境应使用与其 ABI 匹配的依赖；
实际兼容性须由下方导入和模型检查确认。本轮不要求发版。

在当前环境中用 colcon 构建，生成的节点入口才会使用该环境的 Python：

```bash
cd /path/to/ros-workspace
colcon build --packages-select linker_arm_ros2 --symlink-install
source install/setup.bash
```

系统 `/usr/bin/colcon` 使用系统 Python，激活 venv 不会自动改变其 shebang。
`colcon build`/rosdep 不负责从公司 Python 包源安装 SDK，先完成上述依赖安装。
Humble 应使用对应 Python 3.10，并单独确认依赖版本与二进制兼容性。

独立 Python 应用可在专用环境安装 `linkerbot-arm[kinetix]`，由 PyPI 提供 Pinocchio 二进制依赖。
该 extra 可能要求 NumPy 2，应与既有 ROS2 系统 NumPy/Pinocchio 方案分开配置。

## 源码发现与旧环境变量

所有运行依赖已经安装时，可以设置：

```bash
export LINKERBOT_ARM_SRC=/path/to/linkerbot-arm/src
```

也接受仓库根目录。自动发现支持并列仓库和 colcon 工作空间布局：

```text
workspace/src/linker_arm_ros2/
workspace/src/linkerbot-arm/
```

优先级为：可导入的 `linkerbot_arm` → `LINKERBOT_ARM_SRC` → 旧变量
`LINKERBOT_SDK_SRC` → 附近的独立 `linkerbot-arm` 仓库。

旧变量保留一个过渡周期，使用时输出迁移提示。它可以指向新的独立 arm 源码，或临时显式
指定旧完整 SDK 源码供 loader 解析；当前节点仍要求可取消回零能力，未同步该能力的旧 SDK
会被拒绝。推荐改为新变量并指向清单中的独立 arm 源码。
旧 `linkerbot-python-sdk` 不再自动查找，环境中已安装的旧 `linkerbot` 也不作为自动回退来源。

显式路径无效时直接报错；SDK 内部缺少依赖时保留原始异常。环境变量不会覆盖已经可导入的
独立 arm 包，修改 SDK 来源后应重新启动 Python 进程。

## 实际控制调用

- 流式控制保持 `ArmNode → LinkerBotSDKAdapter.set_angles → SDK._set_angles`。
- ROS2 适配器支持 A7、A7lite、P7；标定与生命周期工具仍只开放 A7/A7lite。
- `world_frame`、`tcp_offset` 是节点参数，当前 launch 不从 YAML 转发；默认分别为 `urdf` 和零偏移。
- `position_kp` 在节点中只应用于 A7lite。

## 无硬件检查

安装完成后，在运行 ROS2 的同一 Python 环境执行：

```bash
python -c "import numpy, scipy, pinocchio; print(numpy.__version__, scipy.__version__, pinocchio.__version__)"
python -c "import linkerbot_arm; from linkerbot_arm import A7, A7lite, P7; print(linkerbot_arm.__file__)"
python -c "from linkerbot_arm.arm.kinetix import ArmKinetix; print(ArmKinetix.from_builtin('a7', 'left').forward_kinematics([0.0]*7))"
python -m pip check
```

源码方式也可由公共 loader 完成加载检查：

```bash
python -c "from linker_arm_ros2.sdk_loader import load_sdk; sdk = load_sdk(); print(sdk.__name__, sdk.__file__)"
```

从 ROS2 仓库运行回归：

```bash
python -m pip install -e '.[test]'
source /opt/ros/jazzy/setup.bash
python -m pytest tests
```

测试使用真实 SDK 类的 autospec；ROS2 可用时使用真实 `rclpy`/消息类型和 launch 参数解析，
以 fake arm 验证调用，不连接 CAN 或执行物理机械臂动作。缺少 ROS2 时对应测试跳过。
