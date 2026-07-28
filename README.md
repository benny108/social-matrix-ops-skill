# Social Matrix Ops Skill｜全平台矩阵运营 Skill

一个面向 Codex / Agent 的中文自媒体矩阵运营 Skill，用于通过本地 [`social-auto-upload`](https://github.com/dreammis/social-auto-upload) 的 `sau` CLI，把本地视频或素材文件夹自动发布到多个中文内容平台，并统一记录发布结果。

> 适合场景：短视频矩阵运营、AI 教学视频分发、英语学习内容发布、素材文件夹批量分发、发布失败自动跳过与日志沉淀。

## 能做什么

- 从本地视频文件或素材文件夹中自动选择主视频
- 生成适合中文平台的标题、正文和标签
- 调用 `sau` CLI 发布到多平台
- 自动跳过不稳定平台，避免单个平台卡住整个发布任务
- 为每次发布生成 `summary.json` 和平台日志
- 处理常见问题：cookie 失效、B站登录、视频号二维码登录、小红书发布页卡住、百家号按钮不可用等

## 支持平台

| 平台 | 状态 | 说明 |
| --- | --- | --- |
| 抖音 | ✅ | 推荐优先发布 |
| 快手 | ✅ | 推荐优先发布 |
| 视频号 | ✅ | cookie 失效时需要重新扫码 |
| B站 | ✅/⚠️ | 可能需要重新登录修复 cookie 格式 |
| 小红书 | ⚠️ | 页面改版较频繁，建议设置超时或临时跳过 |
| 百家号 | ⚠️ | 发布按钮可能 disabled，建议记录并跳过 |

## 目录结构

```text
social-matrix-ops-skill/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── content-template.md
│   └── platform-contract.md
├── scripts/
│   └── publish_matrix.py
└── .gitignore
```

## 安装方式

把本仓库克隆到你的 Codex skills 目录，或者放到任意可被 Codex 读取的 skill 路径下：

```bash
git clone https://github.com/<your-github-user>/social-matrix-ops-skill.git ~/.codex/skills/social-matrix-ops
```

如果你想放在自定义目录：

```bash
git clone https://github.com/<your-github-user>/social-matrix-ops-skill.git /path/to/skills/social-matrix-ops
```

## 前置依赖

本 Skill 默认依赖本机已经安装并配置好的 `social-auto-upload`：

```text
/path/to/social-auto-upload
```

默认 CLI 路径：

```text
/path/to/social-auto-upload/.venv/bin/sau
```

如果你的路径不同，可以在执行脚本时传入：

```bash
--workdir /your/social-auto-upload/path \
--sau /your/social-auto-upload/.venv/bin/sau
```


## 配置方式

为避免把个人路径和账号名写进公开仓库，建议用环境变量或命令行参数配置：

```bash
export SAU_WORKDIR="/path/to/social-auto-upload"
export SAU_BIN="/path/to/social-auto-upload/.venv/bin/sau"
export SAU_ACCOUNT_DOUYIN="douyin-account"
export SAU_ACCOUNT_KUAISHOU="kuaishou-account"
export SAU_ACCOUNT_TENCENT="tencent-account"
export SAU_ACCOUNT_BILIBILI="bilibili-account"
export SAU_ACCOUNT_XHS="xhs-account"
```

也可以在执行脚本时通过 `--account-douyin`、`--account-kuaishou` 等参数覆盖。

## 快速使用

发布一个视频文件：

```bash
python scripts/publish_matrix.py \
  --input "/absolute/path/to/video.mp4" \
  --title "8个初中英语单词同音记忆动画" \
  --desc "把抽象单词变成小故事，先记画面，再记发音。" \
  --tags "英语学习,初中英语,英语单词,AI教学" \
  --platforms douyin,kuaishou,tencent,bilibili \
  --skip xiaohongshu,baijiahao
```

发布一个素材文件夹：

```bash
python scripts/publish_matrix.py \
  --input "/absolute/path/to/material-folder" \
  --title "像看动画一样背单词" \
  --desc "这一组内容适合英语启蒙、课堂导入和词汇复习。" \
  --tags "英语学习,儿童英语,趣味英语" \
  --platforms douyin,kuaishou,tencent,bilibili
```

当输入是文件夹时，脚本会优先选择文件名包含以下关键词的视频：

```text
collection / 合集 / cfr / final / main
```

否则会选择目录下体积最大的 `.mp4` 或 `.mov`。

## Codex 调用示例

在 Codex 中可以这样说：

```text
用 social-matrix-ops 把这个文件夹全平台发布，小红书和百家号先跳过。
```

或者：

```text
用 social-matrix-ops 发布这个视频到抖音、快手、视频号、B站，并记录 summary。
```

## 输出结果

每次发布会生成一个输出目录，包含：

```text
output/matrix_publish_YYYYMMDD_HHMMSS/
├── summary.json
└── logs/
    ├── douyin.log
    ├── kuaishou.log
    ├── tencent.log
    └── bilibili.log
```

`summary.json` 示例：

```json
{
  "video": "/absolute/path/to/video.mp4",
  "title": "8个初中英语单词同音记忆动画",
  "platforms": [
    {"platform": "douyin", "status": "success", "rc": 0},
    {"platform": "kuaishou", "status": "success", "rc": 0},
    {"platform": "xiaohongshu", "status": "skipped", "reason": "requested_skip"}
  ]
}
```

## 安全说明

本仓库不包含任何平台 cookie、账号 token、二维码、日志或发布产物。

`.gitignore` 已默认排除：

```text
cookies/
qrcode.png
*.log
output/
.env
.env.*
```

请不要把以下内容提交到公开仓库：

- 平台 cookie 文件
- 登录二维码
- GitHub token
- 私钥
- 平台后台截图中的敏感信息
- 用户私信、订单、手机号等个人信息

## 常见问题

### B站报 `missing field cookie_info`

说明 B站 cookie 文件格式损坏或过期，需要重新登录：

```bash
sau bilibili login --account bilibili-account
```

### 视频号提示 cookie 失效

重新扫码登录：

```bash
sau tencent login --account tencent-account --headed
```

### 小红书一直卡在发布中

小红书创作中心页面经常改版，旧选择器可能点不到真实发布按钮。建议：

- 临时跳过小红书
- 或给小红书发布命令加外层超时
- 单独修复小红书发布脚本后再纳入矩阵

### 百家号发布按钮不可用

常见原因包括描述超长、声明弹窗、平台质量检测、挂载项未选择等。矩阵任务中建议先跳过并记录：

```json
{"platform":"baijiahao","status":"skipped","reason":"publish_button_disabled_recently"}
```

## 适合的运营工作流

```text
素材文件夹
  ↓
选择主视频 / 合集视频
  ↓
生成中文标题、正文、标签
  ↓
多平台发布
  ↓
失败平台跳过或等待登录
  ↓
summary.json 记录结果
  ↓
下一轮复盘播放量、点击、评论、私信
```

## License

MIT
