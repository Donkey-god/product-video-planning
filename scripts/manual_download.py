#!/usr/bin/env python3
"""
即梦任务人工触发脚本

功能：
1. 从 run 目录读取 dreamina_task.json
2. 查询 submit_id 最新状态
3. 若成功则下载 full_video.mp4
4. 回写 dreamina_task.json 状态信息
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_task_file(task_file: Path) -> dict:
    if not task_file.exists():
        raise FileNotFoundError(f"未找到任务文件: {task_file}")
    with task_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("dreamina_task.json 内容格式错误，应为 JSON 对象")
    return data


def write_task_file(task_file: Path, data: dict) -> None:
    with task_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def detect_status(text: str) -> str:
    t = text.lower()

    # 常见成功信号
    if "gen_status=success" in t or '"gen_status":"success"' in t or '"gen_status": "success"' in t:
        return "success"
    if re.search(r"\bsuccess\b", t) and ("gen_status" in t or "status" in t):
        return "success"

    # 常见失败信号
    if "gen_status=failed" in t or '"gen_status":"failed"' in t or '"gen_status": "failed"' in t:
        return "failed"
    if re.search(r"\bfailed\b", t) and ("gen_status" in t or "status" in t):
        return "failed"

    # 常见排队/处理中信号
    queue_signals = ["queue", "排队", "等待", "pending"]
    processing_signals = ["processing", "处理中", "running", "generating"]
    if any(s in t for s in queue_signals):
        return "queueing"
    if any(s in t for s in processing_signals):
        return "processing"

    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="即梦任务人工触发查询与下载")
    parser.add_argument("--run-dir", required=True, help="run_NNN 目录路径")
    parser.add_argument(
        "--dreamina-bin",
        default=os.path.expanduser("~/.local/bin/dreamina"),
        help="dreamina 可执行文件路径",
    )
    parser.add_argument("--submit-id", default="", help="可选，覆盖 task 文件中的 submit_id")
    parser.add_argument("--output-name", default="full_video.mp4", help="下载文件名，默认 full_video.mp4")
    parser.add_argument("--query-only", action="store_true", help="仅查询状态，不执行下载")
    args = parser.parse_args()

    run_dir = Path(os.path.expanduser(args.run_dir)).resolve()
    task_file = run_dir / "dreamina_task.json"
    output_path = run_dir / args.output_name

    task = read_task_file(task_file)
    submit_id = args.submit_id.strip() or str(task.get("submit_id", "")).strip()
    if not submit_id:
        raise ValueError("未提供 submit_id，且 dreamina_task.json 中也不存在 submit_id")

    query_cmd = [args.dreamina_bin, "query_result", "--submit_id", submit_id]
    query_code, query_output = run_cmd(query_cmd)
    status = detect_status(query_output)

    task["submit_id"] = submit_id
    task["last_checked_at"] = now_iso()
    task["last_query_exit_code"] = query_code
    task["last_query_output"] = query_output
    task["status"] = status

    if query_code != 0:
        task["note"] = "query_result 执行失败，请检查 dreamina CLI 或 submit_id"
        write_task_file(task_file, task)
        raise RuntimeError(f"query_result 执行失败（exit={query_code}）:\n{query_output}")

    if args.query_only:
        task["note"] = "仅查询模式，未触发下载"
        write_task_file(task_file, task)
        print(f"查询完成，当前状态: {status}")
        return

    if status != "success":
        task["note"] = "当前尚未成功，未触发下载；请稍后重试"
        write_task_file(task_file, task)
        print(f"当前状态为 {status}，未下载。")
        return

    download_cmd = [
        args.dreamina_bin,
        "download",
        "--submit_id",
        submit_id,
        "--output_path",
        str(output_path),
    ]
    dl_code, dl_output = run_cmd(download_cmd)
    task["last_download_exit_code"] = dl_code
    task["last_download_output"] = dl_output
    task["last_checked_at"] = now_iso()

    if dl_code != 0:
        task["status"] = "success"
        task["note"] = "状态已成功，但下载失败，请重试"
        write_task_file(task_file, task)
        raise RuntimeError(f"download 执行失败（exit={dl_code}）:\n{dl_output}")

    task["status"] = "downloaded"
    task["downloaded_at"] = now_iso()
    task["download_path"] = str(output_path)
    task["note"] = "人工触发下载成功"
    write_task_file(task_file, task)
    print(f"下载成功: {output_path}")


if __name__ == "__main__":
    main()
