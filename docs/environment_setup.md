# linker_arm_ros2 环境配置说明

## 目录

- [问题背景](#问题背景)
- [依赖冲突分析](#依赖冲突分析)
- [解决方案: 系统 Python + SDK 源码](#解决方案-系统-python--sdk-源码)
- [部署到新机器](#部署到新机器)
- [验证步骤](#验证步骤)

---

## 问题背景

`linker_arm_ros2` 是一个 ROS2 功能包，同时依赖：
- **ROS2 生态** (rclpy, sensor_msgs 等) — 运行在系统 Python 环境中
- **linkerbot-python-sdk** (A7/A7Lite 机械臂控制) — 依赖 numpy>=2.2.6, scipy>=1.15.3

这两者存在 **numpy 版本冲突**。

---

## 依赖冲突分析

### 冲突链

```
ROS2 Jazzy (系统 apt 安装)
  └─ python3-pinocchio 3.x
       └─ 要求 numpy < 2.0 (系统 numpy 1.26.4)

linkerbot-py 0.4.2 (pip install)
  └─ 要求 numpy >= 2.2.6
  └─ 要求 scipy >= 1.15.3
```

### 为什么虚拟环境不能解决

| 方案 | 问题 |
|------|------|
| 在 venv 中 `pip install linkerbot-py` | venv 安装 numpy 2.x，ROS2 节点 import pinocchio 时报错 `numpy 1.x cannot run in numpy 2.x` |
| 在系统 `pip install linkerbot-py` | 覆盖系统 numpy 1.26.4 为 2.x，破坏 ROS2 所有功能 |
| venv 中 `pip install numpy<2.0 linkerbot-py` | linkerbot-py 的 pyproject.toml 要求 numpy>=2.2.6，pip 解析冲突拒绝安装 |

---

## 解决方案: 系统 Python + SDK 源码

**核心思路**：不通过 pip 安装 linkerbot-py，而是以源码形式引用 SDK。

```
系统 Python 3.12
├── numpy 1.26.4     ← apt (ROS2 兼容)
├── scipy 1.11.4     ← apt (ROS2 兼容)
├── pinocchio 3.x    ← apt (ROS2 运动学)
├── pydantic 2.x     ← pip --user (SDK 数据模型)
├── python-can 4.6.1 ← pip --user (CAN 通信)
└── linkerbot SDK    ← 源码 (git submodule, 运行时 sys.path 注入)
```

### 为什么这样可行

1. linkerbot-python-sdk 的核心代码 **本身不直接 import numpy/scipy** — 它们只在运动学模块 (`ArmKinetix`) 中使用
2. 系统 numpy 1.26.4 + scipy 1.11.4 **完全满足** pinocchio 和 SDK 运动学计算的需求
3. SDK 的 `pyproject.toml` 中 `numpy>=2.2.6` 是 pip 层面的版本约束，但源码引用绕过了 pip 的版本检查
4. 通过 `sdk_adapter.py` 中的 `sys.path.insert(0, SDK_SRC)` 动态加载 SDK

### 依赖安装位置

| 依赖 | 安装位置 | 安装方式 | 说明 |
|------|----------|----------|------|
| numpy 1.26.4 | `/usr/lib/python3/dist-packages/` | apt (随 ROS2) | 不要升级 |
| scipy 1.11.4 | `/usr/lib/python3/dist-packages/` | apt (随 ROS2) | 不要升级 |
| pinocchio | `/usr/lib/python3/dist-packages/` | apt (随 ROS2) | 运动学依赖 |
| pydantic 2.x | `~/.local/lib/python3.12/site-packages/` | `pip install --user` | SDK 数据模型 |
| python-can >=4.6.1 | `~/.local/lib/python3.12/site-packages/` | `pip install --user` | CAN 通信 |
| linkerbot SDK | `src/linkerbot-python-sdk/src/` | git submodule (源码) | **不用 pip install** |

### data_collection venv 的隔离

`~/.venv/data_collection` 是数据采集的主虚拟环境。`linker_arm_ros2` **不依赖此 venv**：
- `linker_arm_ros2` 通过 `ros2 launch` 启动，使用系统 Python
- `data_collection` venv 中不需要安装 `linkerbot-py`
- `requirements.txt` 中的 `linkerbot-py` 条目应删除（由 submodule 源码替代）

---

## 部署到新机器

目标机器已具备 ROS2 (Jazzy/Humble) 及其系统依赖（numpy, scipy, pinocchio, python-can, pydantic）。
只需拉取 SDK 源码并构建：

```bash
cd ~/linkerbot_data_collection/linkerhand_data_collection_ws

# 拉取 SDK 源码
git submodule update --init src/linkerbot-python-sdk

# 构建
colcon build --packages-select linker_arm_ros2 --symlink-install
```

### 配置

修改 `src/linker_arm_ros2/config/arm_config.yaml`，设置：
- `arm_type`：`"a7"` 或 `"a7lite"`
- `left_arm` / `right_arm`：对应的 CAN 接口（如 `"can0"`、`"can1"`）

### 启动

```bash
source install/setup.bash
ros2 launch linker_arm_ros2 dual_arm.launch.py
```

---

## 验证步骤

部署完成后，执行以下验证：

```bash
# 1. 系统 numpy 兼容 ROS2
python3 -c "import numpy; print('numpy:', numpy.__version__)"
# 预期: 1.26.4

# 2. pinocchio 可正常导入
python3 -c "import pinocchio; print('pinocchio OK')"

# 3. SDK submodule 源码可导入
PYTHONPATH=src/linkerbot-python-sdk/src:$PYTHONPATH python3 -c "from linkerbot import A7; print('SDK OK')"

# 4. colcon build 成功
colcon build --packages-select linker_arm_ros2 --symlink-install

# 5. ROS2 节点可启动
source install/setup.bash
ros2 launch linker_arm_ros2 dual_arm.launch.py
```
