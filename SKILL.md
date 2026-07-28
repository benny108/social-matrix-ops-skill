---
name: social-matrix-ops
description: 中文全平台自媒体矩阵运营与自动发布技能。Use when Codex needs to publish or schedule videos/notes across multiple Chinese content platforms using the local social-auto-upload `sau` CLI, including 抖音、快手、视频号、B站、小红书、百家号；also use for generating Chinese platform metadata, skipping unstable platforms, retrying expired cookies, recording summary.json/logs, and continuing matrix publishing from local folders.
---

# 全平台矩阵运营 Skill

本 Skill 用于把本地视频、图文素材或文件夹内容，通过本机已经安装的 `social-auto-upload` / `sau` CLI 发布到多个中文内容平台，并沉淀可追踪的运营结果。

## 默认原则

1. **先执行发布动作**：用户说“发布 / 全平台发布 / 继续发布”时，优先直接执行，不要停在解释。
2. **不让单平台阻塞全局**：某个平台卡住、限频、cookie 失效、按钮不可用时，记录失败或跳过，继续其它平台。
3. **不上传敏感文件**：永远不要提交或打印 cookies、tokens、私钥、二维码登录态。
4. **每次发布都落盘**：必须输出 `summary.json`，保存每个平台日志，方便复盘。
5. **默认中文运营文案**：标题、正文、标签优先写成自然中文，不要像机器模板。

## 运行前检查

默认项目目录：

```bash
${SAU_WORKDIR:-/path/to/social-auto-upload}
```

默认 CLI：

```bash
${SAU_BIN:-/path/to/social-auto-upload/.venv/bin/sau}
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
4. 调用脚本：

```bash
python scripts/publish_matrix.py \
  --input "/absolute/path/to/video-or-folder" \
  --title "标题" \
  --desc "正文" \
  --tags "英语学习,AI教学,儿童英语" \
  --platforms douyin,kuaishou,tencent,bilibili \
  --skip xiaohongshu,baijiahao
```

5. 等待命令完成；如有平台正在等待登录二维码，向用户展示二维码图片。
6. 汇报结果：成功平台、失败平台、跳过平台、summary 路径。

## 平台处理策略

- **抖音 / 快手 / 视频号**：优先发布，通常稳定。
- **B站**：如果报 `missing field cookie_info`，说明 B站 cookie 文件格式损坏，需要重新登录：

```bash
sau bilibili login --account bilibili-account
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
