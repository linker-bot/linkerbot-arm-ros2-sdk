# ROS2 与独立 arm SDK 环境配置

ROS2 直接依赖 `linkerbot-arm>=0.6.0,<0.7.0`，Python 导入为 `linkerbot_arm`。
无需完整 SDK 聚合包或 hand 包；三个独立包使用不同命名空间，可以共存安装。

## 获取 ROS2 源码

仓库已迁移到 [linker-bot/linkerbot-arm-ros2](https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2)，
默认分支为 `main`。以下以 `~/linkerbot_ws` 为工作空间，需要公司 Gitea 访问权限：

```bash
mkdir -p ~/linkerbot_ws/src
git clone --branch main https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2.git ~/linkerbot_ws/src/linkerbot-arm-ros2
```

已有 checkout 可保留原目录名，将 `origin` 更新为上述地址后切换、同步 `main`，
并按实际路径调整后续命令。仓库名为 `linkerbot-arm-ros2`，ROS2 包名仍为 `linker_arm_ros2`。
SDK 源码仓库名为 `linkerbot-arm-python`，发行包和导入仍为 `linkerbot-arm`、`linkerbot_arm`。

## 运行依赖

- A7、A7lite、P7 导入时需要 NumPy/SciPy，构造时均创建 `ArmKinetix` 并加载 Pinocchio。
- 即使只使用关节控制，也需要 Pinocchio；源码加载同样需要完整运行依赖。
- arm 依赖 `linkerbot-transport[can]`，不限制 transport 版本号或 tag；ROS2 无需维护另一份通信实现。
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

当前节点的可取消生命周期需要配套的 arm/transport 源码。本仓库的
[requirements/source-versions.txt](../requirements/source-versions.txt) 使用新组织下的地址，
arm 固定到已合并的安全及 transport 兼容修复提交，transport 从 `main` 安装，
不固定版本号、tag 或旧提交。源码清单通过 SSH 获取依赖，需要相应 SSH 权限。
arm checkout 也须使用清单中的提交，以使用配套的 Jazzy 部署锁。

```bash
# 从 ROS2 源码清单读取 arm 提交，使用同一版本提供的部署锁。
ARM_SOURCE_COMMIT=$(sed -n 's/^linkerbot-arm @ .*@//p' ~/linkerbot_ws/src/linkerbot-arm-ros2/requirements/source-versions.txt)
git clone --branch main https://gitea.linkerhub.work/linker-bot/linkerbot-arm-python.git /path/to/linkerbot-arm-python
git -C /path/to/linkerbot-arm-python checkout "$ARM_SOURCE_COMMIT"
python -m pip install --force-reinstall -c /path/to/linkerbot-arm-python/constraints/ros-jazzy.txt \
  -r ~/linkerbot_ws/src/linkerbot-arm-ros2/requirements/source-versions.txt
```

`--force-reinstall` 确保已有 transport 也从当前源码重新安装，不依赖其版本号变化。
也可将 transport 检出到当前 `main`、arm 检出到清单中的提交，在同一环境先后执行
`python -m pip install -e '/path/to/linkerbot-transport[can]'` 和
`python -m pip install -c /path/to/linkerbot-arm-python/constraints/ros-jazzy.txt -e /path/to/linkerbot-arm-python`。
节点在创建 SDK 对象前检查 `home_cancellable`，
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
cd ~/linkerbot_ws
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
export LINKERBOT_ARM_SRC=/path/to/linkerbot-arm-python/src
```

也接受仓库根目录。推荐将 SDK 安装到节点实际使用的 Python 环境。
新目录名 `linkerbot-arm-python` 需先安装或设置上述变量；自动发现仍只识别旧目录名
`linkerbot-arm`，支持并列仓库和以下 colcon 工作空间布局：

```text
workspace/src/linkerbot-arm-ros2/
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

节点在 SDK 实例创建前校验侧别、注册型号、坐标系、TCP 偏移和运行参数，
非法值不会进入打开 CAN 或使能流程。具名 `JointState` 必须包含当前臂的七个 CAN ID
名称且没有重复；顺序可不同，节点按名称重排。无名消息继续使用固定的七关节位置顺序。
长度错误、名称错误或非有限目标在准入前拒绝，不延长有效命令超时或修改滤波历史。

固定源码清单中的 A7lite SDK 将软件停止持续锁存，显式使能或成功回零后才恢复；ROS 节点同时保持
自己的流式准入门禁。P7 的外部流式目标受 SDK 的逐关节速度/加速度限幅，首帧保持测量
位置，后续必须周期输入才能推进目标。以上均是软件提交行为，不代表硬件速度或到位确认。

## 独立工具与检查边界

`scripts/calibrate_arm_zero.py` 在标定前查询当前 ROS domain 的节点图，识别
`arm_node`、`left_arm_node`、`right_arm_node`，包括任意 namespace 下的这些名称。
缺少 `ros2`、查询超时、执行异常或非零退出码时拒绝标定，不将查询失败视为控制器停止。
这只是节点图快照，不能识别任意改名的控制器、其他 domain 或独立 SDK 进程，也不是 CAN
设备互斥锁。标定前仍需由操作者停止所有可能控制该设备的程序。
标定角度必须全部有限，容差必须有限且为正；CLI 还校验速度、等待时间和失能次数，
NaN/Inf 不能得到验证成功。

`scripts/test_lifecycle.py` 仍只支持 A7/A7lite。SIGINT/SIGTERM 设置取消事件，使
`home_cancellable()` 退出等待和后续回零提交，再进入失能、关闭流程。
每个成功创建的 SDK 实例都会进入 `finally` 清理；第二只臂构造失败、测试阶段失败或
一只臂清理失败，均不会跳过其他已创建实例的失能和关闭。清理错误逐臂记录；
停止及发送等待仍不等同硬件确认。
本轮验证使用 fake/monkey SDK 与无硬件测试，未验证实际机械臂停止距离、速度或标定效果。

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
