# downloaded-skills

本机已安装的 Agent Skills，打包成 Cursor 插件，供网页端和云端 Agent 使用。

## 在网页端或云端使用

Cursor 不会因为仓库里放了 `SKILL.md` 就自动装到所有云端会话。要从这个 GitHub 仓库使用，需要把它作为插件市场导入：

1. 打开 Cursor（桌面或 [网页端](https://cursor.com)）的 **Customize**。
2. 选择 **From GitHub Repository**，填入 `https://github.com/rooot185/downloaded-skills`。
3. 安装插件 **local-skills**。

安装后，这些 skill 会出现在 Customize 的 Skills 列表里。你自己启动的云端 Agent，以及网页端会话，都可以按 skill 的说明调用它们。

自动化任务（Automations）不会加载「同步到云端的个人 skill」。如果某次自动化也要用其中某个 skill，把对应目录复制到那个项目的 `.cursor/skills/`。

把**本仓库**交给云端 Agent 时，仓库根目录的 `.cursor/skills` 和 `.agents/skills` 指向同一份内容，不安装插件也会被发现。

## 目录

```text
.cursor-plugin/marketplace.json
plugins/local-skills/skills/<skill-name>/SKILL.md
.cursor/skills  -> ../plugins/local-skills/skills
.agents/skills  -> ../plugins/local-skills/skills
```

完整清单见 [SKILLS.md](SKILLS.md)。第三方 skill 仍使用各自目录中的许可证。

## 来源

| 本机目录 | 处理 |
| --- | --- |
| `~/.cursor/skills` | 已收录（空目录 `action-description` 除外） |
| `~/.agents/skills` | 只补充上面没有的：`modern-web-guidance`、`reverse-engineer-anything` |
| `~/.codex/skills/tushare-data` | 已收录 |
| `~/.cursor/skills-cursor` | 未收录。这些是 Cursor 自带 skill，网页端和云端已经提供 |

## 未包含的大文件

云端环境是 Linux，下面这些 Windows 可执行文件没有放进仓库（单个接近 100MB）：

- `gstack/bin/gstack-global-discover.exe`
- `gstack/browse/dist/browse.exe`
- `gstack/browse/dist/find-browse.exe`
- `impeccable/scripts/bin/windows-x64/impeccable.exe`

对应脚本和说明仍在。`__pycache__` 和 gstack 的本地运行目录 `.gstack` 也没有提交。
