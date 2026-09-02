# 运行环境与登录态排查

这份说明专门解决“别人可以发布，但当前 Codex 说没有 `sau` / 登录不了抖音”的问题。

## 根因

`command -v sau` 只会检查当前 shell 的 `PATH`。很多 Python 项目把 `sau` 安装在虚拟环境中，因此下面两件事可以同时成立：

- `command -v sau` 没有输出；
- `/path/to/social-auto-upload/.venv-sau312/bin/sau` 可以正常运行。

另外，Codex 的 worktree 可能有自己的 `.venv`，但没有共享项目中的 `cookies/`。登录态不在 Skill 仓库，也不会随着 worktree 自动复制。

## 解析共享项目

优先采用用户显式配置；没有配置时，按顺序尝试：

```bash
export SAU_WORKDIR="${SAU_WORKDIR:-$HOME/Documents/Codex/social-auto-upload}"

if [ -z "${SAU_BIN:-}" ]; then
  for candidate in \
    "$SAU_WORKDIR/.venv-sau312/bin/sau" \
    "$SAU_WORKDIR/.venv/bin/sau" \
    "$SAU_WORKDIR/venv/bin/sau" \
    "$HOME/Documents/Codex/social-auto-upload/.venv-sau312/bin/sau" \
    "$HOME/Documents/Codex/social-auto-upload/.venv/bin/sau" \
    "$HOME/social-auto-upload/.venv/bin/sau"; do
    if [ -f "$candidate" ]; then
      export SAU_BIN="$candidate"
      break
    fi
  done
fi

test -d "$SAU_WORKDIR"
test -f "$SAU_BIN"
"$SAU_BIN" --help
```

如果显式的 `SAU_WORKDIR` 中没有可用 CLI，应修正路径，而不是直接在当前 worktree 里重新生成一套空环境。`SAU_BIN` 和 `SAU_WORKDIR` 必须指向同一个 `social-auto-upload` 项目。

## 账号检查与抖音登录

账号别名由用户自己定义，例如 `creator`、`shop-main`；不要把平台显示昵称当作 `--account`。CLI 默认从下面的位置加载账号文件：

```text
$SAU_WORKDIR/cookies/douyin_<account>.json
```

先检查，不要无条件重新登录：

```bash
"$SAU_BIN" douyin check --account "$SAU_ACCOUNT_DOUYIN"
```

检查成功就直接进入发布；检查失败、账号文件不存在或 cookie 过期时，再使用有头模式：

```bash
"$SAU_BIN" douyin login --account "$SAU_ACCOUNT_DOUYIN" --headed
```

有头模式下用户在浏览器里完成扫码、短信验证码或二次验证。登录结束后再次检查：

```bash
"$SAU_BIN" douyin check --account "$SAU_ACCOUNT_DOUYIN"
```

不要把 `cookies/*.json`、验证码、二维码或日志中的敏感字段复制到这个仓库。排查时最多查看账号文件名，不要查看文件内容：

```bash
find "$SAU_WORKDIR/cookies" -maxdepth 1 -type f -name 'douyin_*.json' -print
```

## 发布前最小验证

```bash
"$SAU_BIN" douyin --help
"$SAU_BIN" douyin upload-video --help
"$SAU_BIN" douyin upload-note --help
```

图片/海报必须使用 `upload-note --images`；视频才使用 `upload-video --file`。如果是矩阵脚本，显式传：

```bash
python3 scripts/publish_matrix.py \
  --check-runtime \
  --workdir "$SAU_WORKDIR" \
  --sau "$SAU_BIN"
```

## 卡住时的处理

矩阵脚本对每个平台使用独立超时；超时会结束进程组、写入对应日志，并继续下一个平台。不要让一个平台的浏览器进程无限阻塞整个矩阵任务。

如果需要用户扫码或短信验证，应使用 `--headed`，并明确等待用户完成验证；不要在无头模式中反复重试登录。
