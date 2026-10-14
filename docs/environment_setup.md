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

### 选择发行版

按操作系统选择官方二进制组合，同一套节点、launch 和配置支持两个发行版：

- Ubuntu 22.04：ROS2 **Humble**，系统 Python **3.10**，使用本仓库的
  [constraints/ros-humble.txt](../constraints/ros-humble.txt)。
- Ubuntu 24.04：ROS2 **Jazzy**，系统 Python **3.12**，使用本仓库的
  [constraints/ros-jazzy.txt](../constraints/ros-jazzy.txt)。新装 Ubuntu 24.04 时推荐 Jazzy。
- 已有 Humble 系统可继续使用 Humble，无需为了本包升级系统。
  其他 Ubuntu/ROS/Python 组合尚未验证；切换发行版时使用新终端和独立 venv、构建空间，
  不复用另一发行版的 `build/`、`install/`、`log/`。

先按 [Humble 官方安装说明](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)
或 [Jazzy 官方安装说明](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)
安装 ROS2，并配置对应 APT 源。以下命令假定 ROS2 已安装。

两个 profile 都使用 NumPy 1.26.4、SciPy 1.13.1，Pinocchio/eigenpy 由对应 ROS APT 包提供；
不通过 pip 的 `pin` 锁定运动学库。Humble 的系统 NumPy 1.21.5 低于 SDK 的最低要求，
必须在 venv 中安装 profile 中的 NumPy，不能仅依赖系统包。
SDK/transport 的构建要求 setuptools >=77，colcon 要求 <80，profile 同时限制这个范围。
构建工具同时升级 packaging >=24.2，避免系统旧版缺少 `packaging.licenses` 导致源码安装失败。

### 创建对应 Python 环境

下面只需修改第一行的 `humble` / `jazzy`，后续依赖约束从实际 `ROS_DISTRO` 自动选择。
每次在新终端使用时，都先 source 相应 ROS，再激活同一 venv。

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

环境检查在安装 SDK 前核对 Ubuntu、ROS、Python、venv 和真实 ROS 模块，
不匹配时返回错误；遇到错误应停止后续安装并修正环境。
不要用 Conda/自装 Python 替换 ROS 的系统 Python，也不要在同一终端叠加 source 两个发行版。

### 安装配套 SDK

当前节点的可取消生命周期与反馈新鲜度需要配套的 arm/transport 源码。
[requirements/source-versions.txt](../requirements/source-versions.txt) 将 arm 固定到已合入 `main`、
包含生命周期/速度配置物理发送回执和原始反馈接收时间的实际 Squash 合入提交（SDK #44），
同时保留安全修复和 `get_feedback()`；不能用旧反馈提交或旧安全基线代替。SDK 仓库为
[linker-bot/linkerbot-arm-python](https://gitea.linkerhub.work/linker-bot/linkerbot-arm-python)。
清单中的 arm SHA 已核实为 SDK 主分支上的实际合入提交；不以相同版本号代替源码匹配。
transport 从新组织仓库的 `main` 安装，不固定版本号、tag 或旧提交；清单中的源码依赖通过
SSH 获取，需要相应 SSH 权限。

```bash
python -m pip install --force-reinstall -c "$ARM_CONSTRAINTS" \
  -r "$ARM_ROS_SOURCE/requirements/source-versions.txt"
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
```

`--force-reinstall` 确保已有 transport 也从当前源码重新安装，不依赖其版本号变化。
也可将 transport 检出到当前 `main`，arm 检出到清单中的完整提交，在同一环境执行：

```bash
python -m pip install -c "$ARM_CONSTRAINTS" -e '/path/to/linkerbot-transport[can]'
python -m pip install -c "$ARM_CONSTRAINTS" -e /path/to/linkerbot-arm-python
```

源码安装不改变 loader 的查找顺序。
节点在创建 SDK 对象前检查 `home_cancellable` 和 `get_feedback`，
缺少时明确提示更新，不会打开 CAN，也不会用旧数组读取伪造新鲜反馈。
状态发布的暂停、恢复和时间戳语义见[反馈有效性](feedback.md)。

APT 包提供 `pinocchio` 模块，但没有 PyPI `pin` 发行元数据；上述安装使用基础 SDK，
不带 `kinetix` extra。该 extra 只负责 pip 安装依赖，不开关运动学功能，已有兼容
Pinocchio 的基础包同样提供运动学。SDK 中保留的 `constraints/ros2.txt` 是通用兼容范围，
部署本 ROS2 包时使用本仓库的发行版 profile。自行安装 Pinocchio wheel 的环境应使用与其
ABI 匹配的依赖，不能直接套用这些 profile。

### 构建节点

在 `--system-site-packages` 环境中，普通 `pip install colcon-common-extensions` 可能
直接使用已满足依赖的 APT 包，不会生成 venv 的 colcon 入口。Ubuntu 已有
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

独立 Python 应用可在专用环境安装 `linkerbot-arm[kinetix]`，由 PyPI 提供 Pinocchio 二进制依赖。
PyPI Pinocchio 的 NumPy >=2 依赖与上述部署 profile 不兼容。
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
可取消回零及反馈新鲜度能力。旧 `linkerbot-python-sdk` 不再自动查找，已安装的旧 `linkerbot` 也不作为回退来源。

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

配套 A7lite SDK 将软件停止持续锁存，显式使能或成功回零后才恢复；ROS 节点同时保持
自己的流式准入门禁。P7 的外部流式目标受 SDK 的逐关节速度/加速度限幅，首帧保持测量
位置，后续必须周期输入才能推进目标。以上均是软件提交行为，不代表硬件速度或到位确认。

配套 SDK 的速度配置会等待物理发送回执，ROS 节点将这类等待放在现有生命周期 worker，
避免占用单线程执行器。配置期间保留最新一条通过消息及滤波校验的目标，成功后再经 SDK
校验提交；年龄达到 `cmd_timeout` 的待发目标按主机单调时钟丢弃。
更新目标被 SDK 接受后也会清除旧待发目标，避免配置 worker 收尾期间的旧目标重放；
配置结束后若新消息校验或 SDK 准入失败，保留原待发目标。停止会清空待发目标，
迟到回执不会恢复节点状态；停止响应仍受 SDK 调用和原 worker 退出时间影响。
回零速度部分配置失败会保留原始 SDK 错误，并要求全臂慢速重试成功才重新提交目标。

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

安装完成后，在运行 ROS2 的同一 Python 环境执行以下检查。脚本打印依赖版本/来源、
检查配套 SDK 能力，并加载 A7、A7lite、P7 的左右臂六个真实 URDF 做有限值 FK 检查；不创建
SDK 设备实例、不打开 CAN。

```bash
python "$ARM_ROS_SOURCE/scripts/check_ros_environment.py"
python -m pip check
```

源码方式也可由公共 loader 完成加载检查：

```bash
python -c "from linker_arm_ros2.sdk_loader import load_sdk; sdk = load_sdk(); print(sdk.__name__, sdk.__file__)"
```

从 ROS2 仓库运行回归：

```bash
python -m pip install -c "$ARM_CONSTRAINTS" -e '.[test]'
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_timeout tests
```

测试使用真实 SDK 类的 autospec；ROS2 可用时使用真实 `rclpy`/消息类型和 launch 参数解析，
以 fake arm 验证调用，不连接 CAN 或执行物理机械臂动作。缺少 ROS2 时对应测试跳过。
关闭第三方 pytest 插件自动加载，显式启用超时插件，避免 ROS 系统插件干扰常规单元测试。
默认 pytest 只收集 `tests/`，不把 `scripts/test_lifecycle.py` 实机工具当作单元测试。

## Docker 验证

Humble、Jazzy 使用同一套构建和无硬件测试流程，安装对应发行版的 APT Pinocchio，
再用本地配套 SDK/transport 源码构建镜像。验证入口、源码获取方式和结果见
[Docker 说明](../docker/README.md)。Docker 验证不需要 CAN，也不会透传设备或启动机械臂。
