# 协作流程（linkerbot-arm-ros2）

> 面向本仓库贡献者的日常使用说明。所有改动都通过 **Issue → 分支 → PR → 审批合并** 完成，**禁止直接向 `main` 推送**。

## 本仓库特点

- 仓库地址为 [linker-bot/linkerbot-arm-ros2](https://gitea.linkerhub.work/linker-bot/linkerbot-arm-ros2)，ROS2 包名仍为 `linker_arm_ros2`。
- **长期分支为 `main`**（默认分支），没有下游定制分支。
- **PR 的目标分支(base)为 `main`**。
- **暂无 CI**（自动检查待补充）。

---

## 1. 分支命名

格式：`<类型>/<issue编号>-<简短英文描述>`

```
feat/12-p7-slave-arm
fix/15-j2-limit
config/18-a7lite-scale
```

| 前缀 | 用途 |
|------|------|
| `feat/` | 新功能 |
| `fix/` | 修复 bug |
| `config/` | 配置、参数调整 |
| `refactor/` | 重构，不改变行为 |
| `docs/` | 文档 |
| `chore/` | 杂务（依赖、构建、脚本等） |
| `hotfix/` | 线上紧急修复 |
| `wip/` | 进行中 / 试验性，尚未成熟 |

规则：

- **带上 issue 编号**，方便双向追溯（历史遗留分支可豁免）。
- 描述用小写英文 + 连字符，简短达意。
- 工作分支是短生命周期，**合并后删除**。

---

## 2. 提交信息

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<类型>(<范围>): <简短描述>

<可选正文：说明动机、做法>

<可选页脚：Refs #N>
```

- **类型**与分支前缀一致：`feat` `fix` `config` `refactor` `docs` `chore` 等。
- **范围**(scope) 可选，标出模块，如 `p7`、`a7`、`a7lite`、`can`、`ik`、`urdf`。
- 描述简短、祈使句，中英文均可（与仓库现有风格一致）。

示例：

```
feat(p7): register A7V2 in SDK adapter
fix(can): swap J6+J7 probe order to match P7 wiring
config(a7lite): 调整零位标定参数
```

---

## 3. 完整流程

### 步骤 1 · 创建 Issue

在 Gitea 上新建 issue，写清：背景、涉及改动、验收标准。拿到 issue 编号 `#N`。

### 步骤 2 · 从 main 切工作分支

```bash
git checkout main && git pull --ff-only
git checkout -b feat/N-简短描述          # 例: feat/12-p7-slave-arm
```

### 步骤 3 · 开发与提交

```bash
git add -p
git commit -m "feat(p7): 增加 P7 从臂关节限位"
```

### 步骤 4 · 推送并开 PR

```bash
git push -u origin feat/N-简短描述
```

在 Gitea 上开 PR：

- **base(目标分支)** 选 `main`。
- 标题遵循提交信息规范。
- 正文写 **`Closes #N`**，合并后 Gitea 自动关闭对应 issue。正文模板：

  ```markdown
  Closes #N

  ## 变更
  - 做了什么，涉及哪些文件

  ## 测试 / 验证
  - 如何验证（实机外部指令控制、编译通过等）
  ```

若开发中途想提前收集反馈但尚未就绪，把 PR 标题加前缀 `WIP:`，Gitea 会阻止其被合并。

### 步骤 5 · 审批与合并

- 需 **至少 1 个同事 Approve** 才能合并（PR 作者不能审批自己）。
- 有人 "Request changes" 会阻止合并，直到问题解决。
- 推了新提交后，旧的批准会作废、需重新审批。
- 审批通过后点 **合并**，方式选 **Squash**（把工作分支的多个提交压成一个干净提交进 main）。
  - ⚠️ 审批 ≠ 自动合并。批准只解锁合并按钮，仍需有人点合并；或在 PR 上开启 "Auto Merge"。
- 合并后 **删除工作分支**。

### 分支落后于 main 时

若开着 PR 期间 `main` 前进了，先把 main 同步进你的分支再合并：

```bash
git checkout feat/N-简短描述
git pull origin main        # 解决冲突后提交
git push
```

（同步后按上面的规则需要重新获得审批。）

---

## 4. 常见错误对照

| 错误做法 | 正确做法 |
|----------|----------|
| 直接 `git push` 到 `main` | 一律走 PR，main 禁止直接推送 |
| PR 里堆一堆零碎提交直接 merge | 用 Squash 合并，保持 main 历史干净 |
| 忘记在 PR 写 `Closes #N` | 写上，合并后自动关闭 issue |
| 分支不带 issue 编号、命名随意 | 按 `<类型>/<issue编号>-<描述>` 命名 |
| 合并后不删工作分支 | 合并后删除，避免分支堆积 |
