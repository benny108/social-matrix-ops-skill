#!/usr/bin/env python3
"""全平台矩阵发布脚本：围绕 social-auto-upload/sau 做超时、跳过、日志和 summary。"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import queue
import shutil
import subprocess
import threading
import time
from typing import Iterable

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
NOTE_PLATFORMS = {"douyin", "kuaishou", "xiaohongshu"}
PLACEHOLDER_ACCOUNTS = {
    "xhs-account",
    "douyin-account",
    "kuaishou-account",
    "tencent-account",
    "bilibili-account",
}


def default_workdir() -> pathlib.Path:
    """优先使用用户已有的共享 social-auto-upload，而不是当前 Codex worktree 副本。"""
    configured = os.getenv("SAU_WORKDIR")
    if configured:
        return pathlib.Path(configured).expanduser()

    candidates = [
        pathlib.Path.home() / "Documents" / "Codex" / "social-auto-upload",
        pathlib.Path.home() / "social-auto-upload",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def default_sau(workdir: pathlib.Path) -> pathlib.Path:
    """按常见虚拟环境命名寻找 sau；PATH 只作为最后兜底。"""
    configured = os.getenv("SAU_BIN")
    if configured:
        return pathlib.Path(configured).expanduser()

    candidates = [
        workdir / ".venv-sau312" / "bin" / "sau",
        workdir / ".venv" / "bin" / "sau",
        workdir / "venv" / "bin" / "sau",
        pathlib.Path.home() / "Documents" / "Codex" / "social-auto-upload" / ".venv-sau312" / "bin" / "sau",
        pathlib.Path.home() / "Documents" / "Codex" / "social-auto-upload" / ".venv" / "bin" / "sau",
        pathlib.Path.home() / "social-auto-upload" / ".venv" / "bin" / "sau",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    on_path = shutil.which("sau")
    if on_path:
        return pathlib.Path(on_path)
    return candidates[0]


DEFAULT_WORKDIR = default_workdir()
DEFAULT_SAU = default_sau(DEFAULT_WORKDIR)
DEFAULT_ACCOUNTS = {
    "xiaohongshu": os.getenv("SAU_ACCOUNT_XHS", "xhs-account"),
    "douyin": os.getenv("SAU_ACCOUNT_DOUYIN", "douyin-account"),
    "kuaishou": os.getenv("SAU_ACCOUNT_KUAISHOU", "kuaishou-account"),
    "tencent": os.getenv("SAU_ACCOUNT_TENCENT", "tencent-account"),
    "bilibili": os.getenv("SAU_ACCOUNT_BILIBILI", "bilibili-account"),
}
DEFAULT_PLATFORMS = ["douyin", "kuaishou", "tencent", "bilibili"]


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def parse_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def resolve_video(input_path: str) -> pathlib.Path:
    p = pathlib.Path(input_path).expanduser().resolve()
    if p.is_file():
        return p
    if not p.is_dir():
        raise FileNotFoundError(str(p))
    videos = [x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in VIDEO_EXTS]
    if not videos:
        raise FileNotFoundError(f"目录下没有视频: {p}")

    def score(x: pathlib.Path) -> tuple[int, int]:
        name = x.name.lower()
        bonus = 0
        for key in ["collection", "合集", "cfr", "final", "main"]:
            if key in name:
                bonus += 100
        if x.name == "episode.mp4":
            bonus -= 10
        return bonus, x.stat().st_size

    return sorted(videos, key=score, reverse=True)[0]


def resolve_media(input_path: str, media_type: str) -> tuple[str, list[pathlib.Path]]:
    """返回 (video|note, 文件列表)。文件夹默认优先选视频，避免误把素材图当成发布内容。"""
    p = pathlib.Path(input_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(str(p))

    if p.is_file():
        if p.suffix.lower() in IMAGE_EXTS:
            if media_type == "video":
                raise ValueError(f"输入是图片，不能按视频发布: {p}")
            return "note", [p]
        if p.suffix.lower() in VIDEO_EXTS:
            if media_type == "note":
                raise ValueError(f"输入是视频，不能按图文发布: {p}")
            return "video", [p]
        raise ValueError(f"不支持的媒体格式: {p.suffix}")

    if not p.is_dir():
        raise FileNotFoundError(str(p))

    videos = [x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in VIDEO_EXTS]
    images = sorted(
        (x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in IMAGE_EXTS),
        key=lambda x: str(x).lower(),
    )
    if media_type in {"auto", "video"} and videos:
        # 与旧版兼容：文件夹仍按主视频评分选择。
        return "video", [resolve_video(str(p))]
    if media_type == "video":
        raise FileNotFoundError(f"目录下没有视频: {p}")
    if not images:
        raise FileNotFoundError(f"目录下没有图片: {p}")
    return "note", images


def resolve_account(workdir: pathlib.Path, platform: str, account: str) -> str:
    """示例账号名未配置时，自动复用共享 workdir 中唯一的已登录账号。"""
    cookie_dir = workdir / "cookies"
    configured_file = cookie_dir / f"{platform}_{account}.json"
    if configured_file.is_file() or account not in PLACEHOLDER_ACCOUNTS:
        return account

    matches = sorted(
        x for x in cookie_dir.glob(f"{platform}_*.json")
        if x.is_file() and not x.name.endswith((".bak", ".tmp"))
    )
    if len(matches) == 1:
        prefix = f"{platform}_"
        return matches[0].stem[len(prefix):]
    if len(matches) > 1:
        names = ", ".join(x.stem.split("_", 1)[1] for x in matches)
        raise RuntimeError(
            f"检测到多个 {platform} 账号 ({names})，请显式传入 --account-{platform}；不要猜账号。"
        )
    return account


def command_for(
    platform: str,
    sau: pathlib.Path,
    account: str,
    media_type: str,
    media_files: list[pathlib.Path],
    title: str,
    desc: str,
    tags: str,
    headless: bool,
    tid: str,
) -> list[str]:
    if media_type == "note":
        if platform not in NOTE_PLATFORMS:
            raise ValueError(f"{platform} 不支持当前 CLI 的图文发布")
        base = [
            str(sau),
            platform,
            "upload-note",
            "--account",
            account,
            "--images",
            *[str(x) for x in media_files],
            "--title",
            title,
        ]
        if desc:
            base += ["--note", desc]
    else:
        video = media_files[0]
        base = [str(sau), platform, "upload-video", "--account", account, "--file", str(video), "--title", title]
        if desc:
            base += ["--desc", desc]
    if tags:
        base += ["--tags", tags]
    if platform == "bilibili":
        base += ["--tid", tid]
    elif headless:
        base += ["--headless"]
    return base


def _write_line(line: str, log_file) -> None:
    print(line, end="", flush=True)
    log_file.write(line)
    log_file.flush()


def _terminate_process(proc: subprocess.Popen[str]) -> None:
    """超时时优先结束进程组，避免浏览器子进程把任务悬住。"""
    try:
        if os.name == "posix":
            import signal

            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            if os.name == "posix":
                import signal

                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass


def run_cmd(name: str, cmd: list[str], cwd: pathlib.Path, log_path: pathlib.Path, timeout_sec: int) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timed_out = False
    rc = 1
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"START {now()}\n")
        f.write("CMD " + json.dumps(cmd, ensure_ascii=False) + "\n")
        f.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=(os.name == "posix"),
        )
        lines: queue.Queue[str | None] = queue.Queue()

        def read_output() -> None:
            if proc.stdout is None:
                lines.put(None)
                return
            for line in iter(proc.stdout.readline, ""):
                lines.put(line)
            lines.put(None)

        reader = threading.Thread(target=read_output, name=f"read-{name}", daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout_sec
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 and proc.poll() is None:
                timed_out = True
                f.write(f"TIMEOUT_KILL {now()}\n")
                f.flush()
                print(f"[{name}] TIMEOUT_KILL", flush=True)
                _terminate_process(proc)
                rc = proc.returncode if proc.returncode is not None else 124
                break
            try:
                line = lines.get(timeout=min(0.2, max(remaining, 0.01)))
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            if line is not None:
                _write_line(line, f)
                continue
            if proc.poll() is not None:
                break
        # 等待读取线程收尾，并把已经进入队列的尾部输出落盘。
        reader.join(timeout=2)
        while True:
            try:
                line = lines.get_nowait()
            except queue.Empty:
                break
            if line:
                _write_line(line, f)
        if not timed_out and proc.returncode is not None:
            rc = proc.returncode
        f.write(f"END status={rc} {now()}\n")
    return {"platform": name, "status": "success" if rc == 0 else "failed", "rc": rc, "timeout": timed_out, "log": str(log_path)}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用 sau CLI 做全平台矩阵发布")
    parser.add_argument("--input", default="", help="视频/图片文件或素材文件夹")
    parser.add_argument("--title", default="")
    parser.add_argument("--desc", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--media-type", choices=("auto", "video", "note"), default="auto", help="auto 会按输入自动判断；文件夹有视频时优先视频")
    parser.add_argument("--platforms", default=",".join(DEFAULT_PLATFORMS), help="逗号分隔，例如 douyin,kuaishou,tencent,bilibili")
    parser.add_argument("--skip", default="", help="逗号分隔要跳过的平台，例如 xiaohongshu,baijiahao")
    parser.add_argument("--workdir", default=str(DEFAULT_WORKDIR))
    parser.add_argument("--sau", default=str(DEFAULT_SAU))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--tid", default="208")
    parser.add_argument("--headed", action="store_true", help="非 B站平台不传 --headless")
    parser.add_argument("--check-runtime", action="store_true", help="只检查已解析的 workdir/sau，不执行发布")
    for platform, default in DEFAULT_ACCOUNTS.items():
        parser.add_argument(f"--account-{platform}", default=default)
    args = parser.parse_args(argv)

    workdir = pathlib.Path(args.workdir).expanduser().resolve()
    sau = pathlib.Path(args.sau).expanduser().resolve()
    if not sau.is_file():
        raise FileNotFoundError(
            f"找不到 sau: {sau}。不要只用 command -v sau 判断，请设置 SAU_BIN 或 --sau 指向虚拟环境中的 sau。"
        )
    if not workdir.is_dir():
        raise FileNotFoundError(f"找不到 sau workdir: {workdir}")
    if args.check_runtime:
        try:
            probe = subprocess.run(
                [str(sau), "--help"],
                cwd=str(workdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(json.dumps({"workdir": str(workdir), "sau": str(sau), "error": str(exc)}, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps({"workdir": str(workdir), "sau": str(sau), "sau_help_rc": probe.returncode}, ensure_ascii=False, indent=2))
        if probe.returncode != 0:
            print(probe.stdout, end="")
        return probe.returncode
    if not args.input:
        parser.error("发布时必须传 --input；仅检查运行时请使用 --check-runtime")
    if not args.title:
        parser.error("发布时必须传 --title")

    media_type, media_files = resolve_media(args.input, args.media_type)
    platforms = parse_csv(args.platforms)
    skipped = set(parse_csv(args.skip))
    outdir = pathlib.Path(args.output_dir).expanduser().resolve() if args.output_dir else workdir / "output" / ("matrix_publish_" + time.strftime("%Y%m%d_%H%M%S"))
    logdir = outdir / "logs"
    outdir.mkdir(parents=True, exist_ok=True)

    summary = {
        "media_type": media_type,
        "media_files": [str(x) for x in media_files],
        "video": str(media_files[0]) if media_type == "video" else None,
        "title": args.title,
        "desc": args.desc,
        "tags": args.tags,
        "started_at": now(),
        "platforms": [],
    }

    all_requested = platforms + [x for x in parse_csv(args.skip) if x not in platforms]
    for platform in all_requested:
        print(f"\n===== publishing {platform} =====", flush=True)
        if platform in skipped:
            item = {"platform": platform, "status": "skipped", "reason": "requested_skip"}
        elif platform == "baijiahao":
            item = {"platform": platform, "status": "skipped", "reason": "publish_button_disabled_recently"}
        elif platform not in DEFAULT_ACCOUNTS:
            item = {"platform": platform, "status": "skipped", "reason": "unsupported_platform"}
        elif media_type == "note" and platform not in NOTE_PLATFORMS:
            item = {"platform": platform, "status": "skipped", "reason": "unsupported_media_type_note"}
        else:
            try:
                account = resolve_account(workdir, platform, getattr(args, "account_" + platform))
                cmd = command_for(
                    platform,
                    sau,
                    account,
                    media_type,
                    media_files,
                    args.title,
                    args.desc,
                    args.tags,
                    not args.headed,
                    args.tid,
                )
                item = run_cmd(platform, cmd, workdir, logdir / f"{platform}.log", args.timeout)
            except (OSError, RuntimeError, ValueError) as exc:
                item = {"platform": platform, "status": "failed", "reason": str(exc)}
        summary["platforms"].append(item)
        (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    summary["finished_at"] = now()
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nSUMMARY_JSON=" + str(outdir / "summary.json"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
