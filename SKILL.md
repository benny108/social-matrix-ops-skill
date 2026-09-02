---
name: social-matrix-ops
description: 中文全平台自媒体矩阵运营与自动发布技能。Use when Codex needs to publish or schedule videos/notes across multiple Chinese content platforms using the local social-auto-upload `sau` CLI, including 抖音、快手、视频号、B站、小红书、百家号；also use for generating Chinese platform metadata, skipping unstable platforms, retrying expired cookies, recording summary.json/logs, and continuing matrix publishing from local folders.
---

# 全平台矩阵运营 Skill

本 Skill 用于把本地视频、图文素材或文件夹内容，通过本机已经安装的 `social-auto-upload` / `sau` CLI 发布到多个中文内容平台，并沉淀可追踪的运营结果。

> 重要：`sau` 的可执行文件和账号登录态属于同一个 `social-auto-upload` 项目。Codex 经常运行在临时 worktree 中；worktree 里即使有另一个 `.venv/bin/sau`，也可能没有用户真实的 `cookies/`。不要因为 `command -v sau` 没有输出就判断“没有安装”，也不要把 cookies 复制进 Skill 仓库。

## 默认原则

1. **先执行发布动作**：用户说“发布 / 全平台发布 / 继续发布”时，优先直接执行，不要停在解释。
2. **不让单平台阻塞全局**：某个平台卡住、限频、cookie 失效、按钮不可用时，记录失败或跳过，继续其它平台。
3. **不上传敏感文件**：永远不要提交或打印 cookies、tokens、私钥、二维码登录态。
4. **每次发布都落盘**：必须输出 `summary.json`，保存每个平台日志，方便复盘。
5. **默认中文运营文案**：标题、正文、标签优先写成自然中文，不要像机器模板。

## 运行时定位（必须先做）

### 1. 先定位共享运行环境

`command -v sau` 只能检查 PATH，不能证明本机是否有 CLI。按下面顺序解析，优先使用已经登录过的共享项目：

1. 用户显式配置的 `SAU_BIN` / `SAU_WORKDIR`。
2. `$HOME/Documents/Codex/social-auto-upload`。
3. `$HOME/social-auto-upload`。
4. 当前项目中确实存在且对应 `cookies/` 的 `.venv-sau312/bin/sau`、`.venv/bin/sau` 或 `venv/bin/sau`。

CLI 候选路径按以下顺序检查：

```text
$SAU_WORKDIR/.venv-sau312/bin/sau
$SAU_WORKDIR/.venv/bin/sau
$SAU_WORKDIR/venv/bin/sau
```

检查命令必须使用解析出的绝对路径，不要只运行 `sau`：

```bash
test -d "$SAU_WORKDIR"
test -f "$SAU_BIN"
"$SAU_BIN" --help
"$SAU_BIN" douyin --help
```

如果当前 Codex 工作目录是 `/.../work/...`，不要在该目录重新 clone 一份 `social-auto-upload` 后直接使用；先回到用户的共享项目目录。不同 worktree 的 `cookies/` 不共享，临时副本中的空 `cookies/` 不等于用户没有登录。

更完整的排查说明见 `references/runtime-bootstrap.md`。

### 2. 先检查账号，再决定是否登录

账号名是别名，不是平台用户名。账号文件通常位于：

```text
$SAU_WORKDIR/cookies/douyin_<account>.json
```

发布抖音前必须先执行：

```bash
"$SAU_BIN" douyin check --account "$SAU_ACCOUNT_DOUYIN"
```

只有检查失败、账号文件缺失或 cookie 过期时，才启动有头登录：

```bash
"$SAU_BIN" douyin login --account "$SAU_ACCOUNT_DOUYIN" --headed
```

登录时保持浏览器窗口可见，二维码/短信验证由用户完成。快手、视频号、小红书、B站也遵循同样的 `check → 必要时 login` 顺序。不要在日志、终端或 GitHub 中打印 cookie 文件内容。

### 3. 按媒体类型选择命令

- 视频（`.mp4`、`.mov` 等）：使用 `upload-video --file`。
- 海报/图片（`.png`、`.jpg`、`.webp` 等）：使用 `upload-note --images`，不要把图片路径塞给 `upload-video`。
- 输入文件夹时，默认优先选择主视频；只有文件夹没有视频时才按图文发布。

抖音图文示例：

```bash
"$SAU_BIN" douyin upload-note \
  --account "$SAU_ACCOUNT_DOUYIN" \
  --images "/absolute/path/1.png" "/absolute/path/2.png" \
  --title "标题" \
  --note "正文" \
  --tags "AI,副业,经验" \
  --headed
```

## 运行前检查

默认项目目录：

```bash
${SAU_WORKDIR:-$HOME/Documents/Codex/social-auto-upload}
```

默认 CLI：

```bash
${SAU_BIN:-$HOME/Documents/Codex/social-auto-upload/.venv-sau312/bin/sau}
```

默认账号：

| 平台 | account |
| --- | --- |
| 小红书 | `xhs-account` |
| 抖音 | `douyin-account` |
| 快手 | `kuaishou-account` |
| 视频号 | `tencent-account` |
| B站 | `bilibili-account` |

发布前先确认视频存在；如果用户给的是文件夹，优先选择命名包含 `collection`、`合集`、`cfr` 的主合集视频；否则选择目录下最大的 `.mp4`。

## 标准发布流程

1. 解析素材路径：单视频或文件夹。
2. 生成标题、正文、标签：参考 `references/content-template.md`。
3. 检查平台策略：参考 `references/platform-contract.md`。
4. 明确传入运行目录和 CLI 的绝对路径，再调用脚本。不要依赖 PATH：

```bash
python3 scripts/publish_matrix.py \
  --input "/absolute/path/to/video-or-folder" \
  --title "标题" \
  --desc "正文" \
  --tags "英语学习,AI教学,儿童英语" \
  --workdir "$SAU_WORKDIR" \
  --sau "$SAU_BIN" \
  --platforms douyin,kuaishou,tencent,bilibili \
  --skip xiaohongshu,baijiahao
```

若发布的是海报/图文，增加 `--media-type note`，并只传支持图文的 `douyin,kuaishou,xiaohongshu`；视频号和 B 站当前只走视频命令：

```bash
python3 scripts/publish_matrix.py \
  --input "/absolute/path/to/poster-folder" \
  --media-type note \
  --title "标题" \
  --desc "正文" \
  --tags "AI,副业" \
  --workdir "$SAU_WORKDIR" \
  --sau "$SAU_BIN" \
  --platforms douyin,kuaishou,xiaohongshu
```

只检查运行时而不发布：

```bash
python3 scripts/publish_matrix.py \
  --check-runtime \
  --workdir "$SAU_WORKDIR" \
  --sau "$SAU_BIN"
```

5. 等待命令完成；如有平台正在等待登录二维码，向用户展示二维码图片。
6. 汇报结果：成功平台、失败平台、跳过平台、summary 路径。

## 平台处理策略

- **抖音 / 快手 / 视频号**：优先发布，通常稳定。
- **抖音登录失败**：先排除 CLI 路径和 worktree 问题，再看 cookie。`command -v sau` 为空不代表 CLI 缺失；必须使用共享项目中的绝对路径执行 `douyin check`。检查失败后才运行有头 `douyin login`。
- **B站**：如果报 `missing field cookie_info`，说明 B站 cookie 文件格式损坏，需要重新登录：

```bash
"$SAU_BIN" bilibili login --account bilibili-account
```

- **小红书**：如果用户说“小红书先别管”，必须跳过；如果要尝试，必须加超时，避免无限卡在发布页。
- **百家号**：如果近期已知 `publish button disabled`，默认跳过并记录原因。

## 输出格式

完成后用简短中文汇报：

```text
已发布：抖音 ✅、快手 ✅、视频号 ✅
失败：B站 ❌ cookie 失效
跳过：小红书 ⏸️ 用户要求跳过、百家号 ⏸️ 发布按钮不可用
记录：/absolute/path/to/summary.json
```

## 需要读取的参考

- 平台命令、账号、故障处理：`references/platform-contract.md`
- 中文标题、正文、标签写法：`references/content-template.md`
