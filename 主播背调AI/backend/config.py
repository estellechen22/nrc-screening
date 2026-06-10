from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_CONFIG_PATH = DATA_DIR / "runtime_config.json"


def _normalize_db_path(path_value: str) -> str:
    if not path_value:
        path_value = "./data/screening.db"
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
PERSPECTIVE_API_KEY = os.getenv("PERSPECTIVE_API_KEY", "")

DATABASE_PATH = _normalize_db_path(os.getenv("DATABASE_PATH", "./data/screening.db"))
PORT = int(os.getenv("PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _default_runtime_config() -> dict[str, Any]:
    return {
        "youtube_api_key": YOUTUBE_API_KEY,
        "perspective_api_key": PERSPECTIVE_API_KEY,
        "notes": "运行时配置。若为空则回落到 .env。",
    }


def load_runtime_config() -> dict[str, Any]:
    import json

    if not RUNTIME_CONFIG_PATH.exists():
        cfg = _default_runtime_config()
        RUNTIME_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return cfg

    try:
        cfg = json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        cfg = _default_runtime_config()
        RUNTIME_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    # 防止字段缺失
    base = _default_runtime_config()
    base.update(cfg)
    return base


def save_runtime_config(data: dict[str, Any]) -> dict[str, Any]:
    import json

    cfg = load_runtime_config()
    for k in ["youtube_api_key", "perspective_api_key"]:
        if k in data:
            cfg[k] = (data.get(k) or "").strip()

    RUNTIME_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def get_active_keys() -> dict[str, str]:
    cfg = load_runtime_config()
    return {
        "youtube_api_key": cfg.get("youtube_api_key") or YOUTUBE_API_KEY,
        "perspective_api_key": cfg.get("perspective_api_key") or PERSPECTIVE_API_KEY,
    }


def check_config() -> list[str]:
    """检查必要配置是否齐全, 返回缺失项列表"""
    keys = get_active_keys()
    missing = []
    if not keys["youtube_api_key"]:
        missing.append("YOUTUBE_API_KEY (YouTube Data API v3)")
    if not keys["perspective_api_key"]:
        missing.append("PERSPECTIVE_API_KEY (Perspective API)")
    if not ADMIN_TOKEN:
        missing.append("ADMIN_TOKEN (配置接口保护口令)")
    return missing


def validate_admin_token(token: str | None) -> tuple[bool, str]:
    """校验配置接口口令"""
    if not ADMIN_TOKEN:
        return False, "服务端未配置 ADMIN_TOKEN，请先在 .env 设置后重启服务。"
    if not token:
        return False, "缺少 X-Admin-Token 请求头。"
    if token != ADMIN_TOKEN:
        return False, "X-Admin-Token 不正确。"
    return True, "ok"
