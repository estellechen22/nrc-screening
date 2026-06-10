"""
工具函数: URL 解析、平台检测、命令行执行
"""
import asyncio
import concurrent.futures
import json
import os
import re
import subprocess
from typing import Optional

# 线程池，防止 subprocess 阻塞事件循环
_CMD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def run_cmd(cmd: str, timeout: int = 120, cwd: Optional[str] = None) -> dict:
    """在非阻塞的子进程中执行 shell 命令，返回 {success, stdout, stderr, returncode}"""
    def _run():
        return subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )

    try:
        future = _CMD_EXECUTOR.submit(_run)
        r = future.result(timeout=timeout + 30)
        return {
            "success": r.returncode == 0,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
            "returncode": r.returncode,
        }
    except concurrent.futures.TimeoutError:
        return {"success": False, "stdout": "", "stderr": "命令超时", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def load_json_file(path: str) -> dict:
    """安全加载JSON文件"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path: str, data: dict):
    """保存JSON文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def detect_platform(url: str) -> str:
    """根据URL自动检测平台（仅支持 YouTube）"""
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return "unknown"


def extract_channel_id(url: str, platform: str) -> Optional[str]:
    """从URL中提取频道ID/用户名"""
    if platform == "youtube":
        m = re.search(r"youtube\.com/@([\w\-\.]+)", url)
        if m:
            return m.group(1)
        m = re.search(r"youtube\.com/channel/([\w\-]+)", url)
        if m:
            return m.group(1)
    return None
