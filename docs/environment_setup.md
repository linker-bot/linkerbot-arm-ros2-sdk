# ROS2 与独立 arm SDK 环境配置

ROS2 直接依赖 `linkerbot-arm>=0.6.0,<0.7.0`，Python 导入为 `linkerbot_arm`。
无需完整 SDK 聚合包或 hand 包；三个独立包使用不同命名空间，可以共存安装。

## 运行依赖

- A7、A7lite、P7 导入时需要 NumPy/SciPy，构造时均创建 `ArmKinetix` 并加载 Pinocchio。
- 即使只使用关节控制，也需要 Pinocchio；源码加载同样需要完整运行依赖。
- arm 固定依赖 `linkerbot-transport[can]==1.0.0`；ROS2 无需维护另一份通信实现。
- SDK 基础依赖要求 NumPy >=1.24、SciPy >=1.10、Pydantic 2.x、python-can >=4.6.1。

## ROS2 系统依赖方案

使用对应 ROS2 发行版的 Python。当前已验证的 Jazzy 组合为 Ubuntu 24.04、Python 3.12、
NumPy 1.26.4、SciPy 1.13.1，以及 APT 提供的 Pinocchio 4.1.0 / eigenpy 3.13.0。
Ubuntu 系统 SciPy 是 1.11.4；已验证 venv 使用 1.13.1，两者不是同一环境。
配套 arm 提供 `constraints/ros-jazzy.txt`，固定 NumPy、SciPy；APT 的运动学版本在此记录，
不通过 pip `pin` 项锁定。系统 Pinocchio 已可用时，
安装基础 SDK，不额外安装 PyPI 的 `pin`。需要系统依赖时可执行：

```bash
sudo apt install python3-numpy python3-scipy python3-venv ros-jazzy-pinocchio
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 -m venv --system-site-packages /path/to/ros-arm-venv
source /path/to/ros-arm-venv/bin/activate
```

当前节点的可取消生命周期需要配套的 arm/transport 源码。使用已有 SSH 权限安装本仓库
[requirements/source-versions.txt](../requirements/source-versions.txt) 固定的提交；
版本号相同的旧 wheel 可能不包含所需能力。arm checkout 也须使用清单中的提交，
确保包含对应的 Jazzy 部署锁与安装诊断。

```bash
# 从 ROS2 的固定源码清单读取 arm 提交，使用同一版本提供的部署锁。
ARM_SOURCE_COMMIT=$(sed -n 's/^linkerbot-arm @ .*@//p' /path/to/linker_arm_ros2/requirements/source-versions.txt)
git clone ssh://git@git.linkerhub.work:12222/zhuzhixiang/linkerbot-arm.git /path/to/linkerbot-arm
git -C /path/to/linkerbot-arm checkout "$ARM_SOURCE_COMMIT"
python -m pip install -c /path/to/linkerbot-arm/constraints/ros-jazzy.txt \
  -r /path/to/linker_arm_ros2/requirements/source-versions.txt
```

也可将 transport 和 arm 分别检出到清单中的提交，在同一 Python 环境先后执行
`pip install -e /path/to/linkerbot-transport` 和 `pip install -e /path/to/linkerbot-arm`，
并使用适合当前 ROS2 二进制环境的约束。节点在创建 SDK 对象前检查 `home_cancellable`，
缺少时明确提示更新，不会打开 CAN 或尝试旧的不可取消回零。

APT 包提供 `pinocchio` 模块，但没有 PyPI `pin` 发行元数据；上述安装使用基础 SDK，
不带 `kinetix` extra。该 extra 只负责 pip 安装依赖，不开关运动学功能，已有兼容
Pinocchio 的基础包同样提供运动学。
保留的 `constraints/ros2.txt` 表示已测 NumPy 1.x / SciPy <1.14 范围，
不是全部 ROS2 版本的硬性要求。自行安装 Pinocchio wheel 的环境应使用与其 ABI 匹配的依赖；
实际兼容性须由下方导入和模型检查确认。本轮不要求发版。

在 `--system-site-packages` 环境中，普通 `pip install colcon-common-extensions` 可能
直接使用已满足依赖的 APT 包，不会生成 venv 的 colcon 入口。Ubuntu Jazzy 已有
`/usr/bin/colcon` 时，在激活上述 venv 后，从工作空间用当前 Python 执行该入口：

```bash
cd /path/to/ros-workspace
python /usr/bin/colcon build --packages-select linker_arm_ros2 --symlink-install
head -n 1 install/linker_arm_ros2/lib/linker_arm_ros2/arm_node
python -c "import sys; print(sys.executable)"
source install/setup.bash
```

生成节点首行应指向当前 venv。其他环境已有 venv 的 colcon 入口时可直接构建，
也须核对入口和生成节点的解释器；激活 venv 不会自动改变系统入口的 shebang。
`colcon build`/rosdep 不负责从公司 Python 包源安装 SDK，先完成上述依赖安装。
Humble 需使用其 Python 3.10，完整二进制依赖组合尚未验证；
不能直接沿用 Jazzy 的 Python 3.12 环境或声称上述部署锁已验证 Humble。

独立 Python 应用可在专用环境安装 `linkerbot-arm[kinetix]`，由 PyPI 提供 Pinocchio 二进制依赖。
当前 PyPI Pinocchio 4.1.0 依赖 cmeel-boost 1.90，其 NumPy >=2 要求与 Jazzy 部署锁无交集。
已有兼容 Pinocchio 的独立环境也可安装基础 SDK。
新旧 SDK 命名空间不同，同环境共存仍要求依赖兼容；当前旧完整 SDK 要求 NumPy >=2.2.6、
SciPy >=1.15.3，与上述部署锁无交集，需要继续使用时保留其独立环境。

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

未设置新变量时，旧变量作为兼容别名保留并输出迁移提示。两个变量都只接受含
`linkerbot_arm` 的新 SDK 源码；loader 不再解析旧完整 SDK 的 `linkerbot` 命名空间。
推荐改为新变量并指向清单中的独立 arm 源码。当前节点仍在打开 CAN 前检查新 SDK 的
可取消回零能力。旧 `linkerbot-python-sdk` 不再自动查找，已安装的旧 `linkerbot` 也不作为回退来源。

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
python - <<'PY'
import sys
from importlib.metadata import version
print("Python:", sys.version, sys.executable)
import numpy, scipy, pinocchio, eigenpy, linkerbot_arm, linkerbot_transport
for module in (numpy, scipy, pinocchio, eigenpy):
    print(module.__name__, module.__version__, module.__file__)
for name, module in (("linkerbot-arm", linkerbot_arm), ("linkerbot-transport", linkerbot_transport)):
    print(name, version(name), module.__file__)
PY
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
