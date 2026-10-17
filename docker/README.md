# Humble / Jazzy 无硬件 Docker 验证

获取 SDK 和 Transport 的最新 `main` 分支、运行验证、查看结果及验证边界见[测试与 Docker 验证](../docs/testing.md)。

English: [Testing and Docker Validation](../docs/en/testing.md).

从 ROS2 仓库根目录运行，依赖 checkout 使用最新 `main`：

```bash
bash docker/verify.sh humble /path/to/sdk /path/to/transport
bash docker/verify.sh jazzy /path/to/sdk /path/to/transport
```

第四个参数可指定结果目录，默认 `docker/results/<发行版>/`。镜像构建使用 APT/PyPI 网络；测试容器无网络、设备透传或端口映射，结束时自动清理。
