#!/usr/bin/env python3
"""全平台矩阵发布脚本：围绕 social-auto-upload/sau 做超时、跳过、日志和 summary。"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import time
from typing import Iterable

DEFAULT_WORKDIR = pathlib.Path(os.getenv("SAU_WORKDIR", "~/social-auto-upload")).expanduser()
DEFAULT_SAU = pathlib.Path(os.getenv("SAU_BIN", str(DEFAULT_WORKDIR / ".venv/bin/sau"))).expanduser()
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
    videos = [x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in {".mp4", ".mov"}]
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


def command_for(platform: str, sau: pathlib.Path, account: str, video: pathlib.Path, title: str, desc: str, tags: str, headless: bool, tid: str) -> list[str]:
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


def run_cmd(name: str, cmd: list[str], cwd: pathlib.Path, log_path: pathlib.Path, timeout_sec: int) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timed_out = False
    rc = 1
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"START {now()}\n")
        f.write("CMD " + json.dumps(cmd, ensure_ascii=False) + "\n")
        f.flush()
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        deadline = time.time() + timeout_sec
        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                print(line, end="", flush=True)
                f.write(line)
                f.flush()
            if proc.poll() is not None:
                rc = proc.returncode
                break
            if time.time() > deadline:
                timed_out = True
                f.write(f"TIMEOUT_KILL {now()}\n")
                f.flush()
                print(f"[{name}] TIMEOUT_KILL", flush=True)
                proc.kill()
                rc = proc.wait()
                break
            if not line:
                time.sleep(0.2)
        f.write(f"END status={rc} {now()}\n")
    return {"platform": name, "status": "success" if rc == 0 else "failed", "rc": rc, "timeout": timed_out, "log": str(log_path)}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用 sau CLI 做全平台矩阵发布")
    parser.add_argument("--input", required=True, help="视频文件或素材文件夹")
    parser.add_argument("--title", required=True)
    parser.add_argument("--desc", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--platforms", default=",".join(DEFAULT_PLATFORMS), help="逗号分隔，例如 douyin,kuaishou,tencent,bilibili")
    parser.add_argument("--skip", default="", help="逗号分隔要跳过的平台，例如 xiaohongshu,baijiahao")
    parser.add_argument("--workdir", default=str(DEFAULT_WORKDIR))
    parser.add_argument("--sau", default=str(DEFAULT_SAU))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--timeout", type=int, default=360)
    parser.add_argument("--tid", default="208")
    parser.add_argument("--headed", action="store_true", help="非 B站平台不传 --headless")
    for platform, default in DEFAULT_ACCOUNTS.items():
        parser.add_argument(f"--account-{platform}", default=default)
    args = parser.parse_args(argv)

    workdir = pathlib.Path(args.workdir).expanduser().resolve()
    sau = pathlib.Path(args.sau).expanduser().resolve()
    if not sau.exists():
        raise FileNotFoundError(f"找不到 sau: {sau}")
    video = resolve_video(args.input)
    platforms = parse_csv(args.platforms)
    skipped = set(parse_csv(args.skip))
    outdir = pathlib.Path(args.output_dir).expanduser().resolve() if args.output_dir else workdir / "output" / ("matrix_publish_" + time.strftime("%Y%m%d_%H%M%S"))
    logdir = outdir / "logs"
    outdir.mkdir(parents=True, exist_ok=True)

    summary = {
        "video": str(video),
        "title": args.title,
        "desc": args.desc,
        "tags": args.tags,
        "started_at": now(),
        "platforms": [],
    }

    all_requested = platforms + [x for x in skipped if x not in platforms]
    for platform in all_requested:
        print(f"\n===== publishing {platform} =====", flush=True)
        if platform in skipped:
            item = {"platform": platform, "status": "skipped", "reason": "requested_skip"}
        elif platform == "baijiahao":
            item = {"platform": platform, "status": "skipped", "reason": "publish_button_disabled_recently"}
        elif platform not in DEFAULT_ACCOUNTS:
            item = {"platform": platform, "status": "skipped", "reason": "unsupported_platform"}
        else:
            account = getattr(args, "account_" + platform)
            cmd = command_for(platform, sau, account, video, args.title, args.desc, args.tags, not args.headed, args.tid)
            item = run_cmd(platform, cmd, workdir, logdir / f"{platform}.log", args.timeout)
        summary["platforms"].append(item)
        (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    summary["finished_at"] = now()
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nSUMMARY_JSON=" + str(outdir / "summary.json"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
