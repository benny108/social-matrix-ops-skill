# 平台发布契约

## CLI 总入口

优先使用：

```bash
cd /path/to/social-auto-upload
.venv-sau312/bin/sau <platform> <action> ...
```

如果当前环境 `sau` 已在 PATH，也可以直接用 `sau`。

## 平台命令

### 抖音

```bash
sau douyin upload-video \
  --account douyin-account \
  --file <video> \
  --title "<title>" \
  --desc "<desc>" \
  --tags "tag1,tag2" \
  --headless
```

### 快手

```bash
sau kuaishou upload-video \
  --account kuaishou-account \
  --file <video> \
  --title "<title>" \
  --desc "<desc>" \
  --tags "tag1,tag2" \
  --headless
```

### 视频号

```bash
sau tencent upload-video \
  --account tencent-account \
  --file <video> \
  --title "<title>" \
  --desc "<desc>" \
  --tags "tag1,tag2" \
  --headless
```

若 cookie 失效：

```bash
sau tencent login --account tencent-account --headed
```

出现二维码时，必须把二维码图片展示给用户扫码。

### B站

```bash
sau bilibili upload-video \
  --account bilibili-account \
  --file <video> \
  --title "<title>" \
  --desc "<desc>" \
  --tags "tag1,tag2" \
  --tid 208
```

常见失败：

```text
missing field `cookie_info`
```

处理：重新登录 B站。

```bash
sau bilibili login --account bilibili-account
```

B站登录通常要求 PTY/交互终端；如果二维码无法完整显示，打开 `qrcode.png` 给用户扫码。

### 小红书

```bash
sau xiaohongshu upload-video \
  --account xhs-account \
  --file <video> \
  --title "<title>" \
  --desc "<desc>" \
  --tags "tag1,tag2" \
  --headless
```

注意：小红书网页经常改版，旧版 CLI 可能卡在“冲刺发布视频”。如果用户说先跳过，就不要尝试；如果必须尝试，需要外层超时并记录失败。

### 百家号

近期常见问题：发布按钮 disabled。默认跳过：

```json
{"platform":"baijiahao","status":"skipped","reason":"publish_button_disabled_recently"}
```

## 失败处理

- cookie 失效：启动对应平台 login，并展示二维码。
- 平台限频：记录 `rate_limited`，不要重复轰炸。
- 按钮 disabled：记录失败/跳过，不要无限等待。
- CLI 超时：kill 子进程，写入 log 和 summary。
