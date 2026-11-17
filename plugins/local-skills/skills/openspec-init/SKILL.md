---
name: openspec-init
description: >-
  Initialize OpenSpec in a software project and install Cursor skills/commands
  via `openspec init --tools cursor`. Use at the start of every new project,
  when bootstrapping a repo, when OpenSpec skills are missing, or when the user
  asks to set up or init OpenSpec.
---

# OpenSpec 项目初始化

在每个软件项目开始开发前，先初始化 OpenSpec，为 Cursor 安装 spec-driven 工作流所需的 skills 与 slash commands。

## 何时执行

满足任一条件即执行本 skill（无需用户再次提醒）：

- 首次在该仓库中开始开发
- 用户新建或克隆了一个软件项目
- `.cursor/skills/openspec-propose/` 不存在
- 用户明确要求初始化 / 安装 OpenSpec

## 工作流

复制并跟踪进度：

```
OpenSpec Init:
- [ ] Step 1: 确认项目根目录
- [ ] Step 2: 检查 openspec CLI
- [ ] Step 3: 运行 openspec init --tools cursor
- [ ] Step 4: 验证安装结果
- [ ] Step 5: 告知用户后续步骤
```

### Step 1: 确认项目根目录

在包含源码或 `package.json` / `pyproject.toml` / `go.mod` 等工程文件的目录执行。若用户尚未创建项目结构，先完成最小脚手架再 init。

### Step 2: 检查 openspec CLI

```bash
openspec --version
```

若命令不存在，先安装 CLI（优先全局安装）：

```bash
npm install -g @fission-ai/openspec
```

安装后再次验证 `openspec --version`。若无法全局安装，可用：

```bash
npx @fission-ai/openspec init --tools cursor
```

代替 Step 3 中的 `openspec init`。

### Step 3: 运行初始化

在项目根目录执行：

```bash
openspec init --tools cursor
```

说明：

- `--tools cursor`：非交互式安装 Cursor 所需的 5 个 skills 与 5 个 slash commands
- 已初始化过的项目可安全重复执行，CLI 会刷新 skills/commands
- 仅在用户明确要求覆盖本地自定义且 CLI 提示冲突时，才考虑 `--force`

### Step 4: 验证安装结果

确认以下路径存在：

| 路径 | 说明 |
|------|------|
| `.cursor/skills/openspec-propose/SKILL.md` | 提案 skill |
| `.cursor/skills/openspec-apply-change/SKILL.md` | 实施 skill |
| `.cursor/skills/openspec-explore/SKILL.md` | 探索 skill |
| `.cursor/skills/openspec-archive-change/SKILL.md` | 归档 skill |
| `.cursor/skills/openspec-sync-specs/SKILL.md` | 同步 spec skill |
| `.cursor/commands/opsx-propose.md` | `/opsx:propose` 命令 |
| `openspec/changes/` | 变更目录 |
| `openspec/specs/` | 规格目录 |

若缺少任一关键文件，读取 CLI 输出排查错误并重试 Step 3。

### Step 5: 告知用户后续步骤

初始化成功后，简要告知：

1. 重启 Cursor 以使 slash commands 生效
2. 开始第一个变更：`/opsx:propose "你的想法"`
3. 可选：编辑 `openspec/config.yaml` 添加项目上下文与 artifact 规则

## 注意事项

- 必须在 Shell 中实际执行命令，不要仅口头说明
- init 会写入 `.cursor/` 与 `openspec/`，提交前确认这些目录符合团队的 git 策略
- 本 skill 只负责安装 OpenSpec 工具链；具体变更规划请使用 `openspec-propose` 等已安装的 skills
