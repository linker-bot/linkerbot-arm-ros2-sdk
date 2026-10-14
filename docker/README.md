# Humble / Jazzy 无硬件 Docker 验证

镜像基于官方 ROS `humble-ros-base` / `jazzy-ros-base`（从公开 ECR 镜像源获取），
使用对应 APT 的 Pinocchio、`--system-site-packages` venv 和本仓库的发行版 constraints。
它验证 Python/ROS ABI、真实 ROS 导入、配套 SDK 能力、六个真实 URDF 的 FK、colcon
构建/节点解释器/包发现/launch 参数，以及 ROS2 和 SDK 的无硬件测试。
测试容器不使用网络、主机 CAN、设备透传或端口映射。镜像构建需要访问 APT/PyPI。

## 获取配套源码

需要 Docker daemon 的访问权限。先在宿主机获取 SDK 与 transport，仓库凭据不会复制到镜像。
arm 使用 `requirements/source-versions.txt` 指定的提交，transport 使用当前 `main`，
没有版本或 tag 约束。以下命令在 ROS2 仓库根目录执行，示例依赖目录需尚不存在：

```bash
mkdir -p ../arm-docker-deps
git clone --branch main https://gitea.linkerhub.work/linker-bot/linkerbot-arm-python.git ../arm-docker-deps/sdk
ARM_SOURCE_COMMIT=$(sed -n 's/^linkerbot-arm @ .*@//p' requirements/source-versions.txt)
git -C ../arm-docker-deps/sdk checkout "$ARM_SOURCE_COMMIT"
git clone --branch main https://gitea.linkerhub.work/linker-bot/linkerbot-transport.git ../arm-docker-deps/transport
```

## 执行验证

```bash
bash docker/verify.sh humble ../arm-docker-deps/sdk ../arm-docker-deps/transport
bash docker/verify.sh jazzy ../arm-docker-deps/sdk ../arm-docker-deps/transport
```

第四个参数可指定结果目录，默认 `docker/results/<发行版>/`（Git 已忽略）。
保留 `sources.log`、`build.log`、`tests.log`、ROS2/SDK JUnit XML 和 colcon 日志；
失败返回非零退出码，容器与临时构建目录自动清理，镜像保留以便复跑。
源码日志会记录宿主机 checkout 的提交和本地改动，transport 的日志提交仅是测试快照，
不是安装约束。

需要刷新 APT 依赖层或绕过损坏的 Docker 构建缓存时，可以在验证命令前设置
`ARM_DOCKER_NO_CACHE=1`；不会清理其他镜像或共享缓存。

## 验证范围

Docker 结果只覆盖构建、依赖、运动学和无硬件软件行为。
ROS2 测试使用真实 ROS 模块与 fake SDK，并包含 ROS 服务 → adapter → 真实 A7 SDK →
真实 transport 的集成回归，仅替换物理 CAN 驱动。覆盖部分速度写入失败、失能发送失败
及排队反馈的原始接收年龄。单线程执行器回归覆盖配置等待期间的状态发布、停止请求、
最新待发目标及其过期、取消和迟到回执。SDK 默认排除 `hardware` / `interactive`。
回归还覆盖速度 worker 收尾时的新旧指令交错，验证新目标被 SDK 接受后不会重放旧目标，
以及非法/拒绝消息保留原待发目标、停止清空待发槽的行为。
实机 CAN 通信、机械臂运动/停止效果需要单独实机验证。

当前验证平台为 Linux amd64。其他架构应在相应平台运行同样命令，不能由 amd64 结果
推断已通过。APT/镜像标签与 transport `main` 会更新，复跑时以日志中的实际版本为准。

## 已执行结果（2026-10-14）

- **Humble / Ubuntu 22.04**：Python 3.10.12，APT Pinocchio 4.0.0 / eigenpy 3.13.0。
- **Jazzy / Ubuntu 24.04**：Python 3.12.3，APT Pinocchio 4.1.0 / eigenpy 3.13.0。
- 两者均使用 NumPy 1.26.4、SciPy 1.13.1；真实 ROS 导入、SDK 能力、六个 URDF 的
  FK、`pip check`、colcon 构建、节点解释器、包发现与两个 launch 参数检查全部通过。
- 每个发行版的 ROS2 测试均为 **323 passed，0 skipped / failures / errors**；SDK 均为
  **1401 passed，38 deselected**，排除项为默认配置中的硬件/交互测试。

本次在已有验证镜像中只读挂载更新后的三仓库源码重跑完整验证，SDK 使用清单中已合入的
#44 提交，transport 使用测试时的 `main`。复跑入口 `verify.sh` 的实际源码记录在
`sources.log`，transport 记录仅用于说明测试快照。这些结果未覆盖真实机械臂或其他 CPU 架构。
