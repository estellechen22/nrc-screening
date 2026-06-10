"""运行时配置路由（API Keys占位到正式切换）"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from config import check_config, get_active_keys, load_runtime_config, save_runtime_config, validate_admin_token

router = APIRouter(prefix="/api/runtime-config", tags=["runtime-config"])


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


@router.get("")
async def get_runtime_config(x_admin_token: str | None = Header(default=None)):
    ok, msg = validate_admin_token(x_admin_token)
    if not ok:
        raise HTTPException(status_code=401, detail=msg)

    cfg = load_runtime_config()
    active = get_active_keys()
    return {
        "config": {
            "youtube_api_key": _mask(cfg.get("youtube_api_key", "")),
            "perspective_api_key": _mask(cfg.get("perspective_api_key", "")),
        },
        "active": {
            "youtube_api_key_set": bool(active.get("youtube_api_key")),
            "perspective_api_key_set": bool(active.get("perspective_api_key")),
        },
        "missing": check_config(),
        "note": "保存后新任务会使用最新配置；历史任务结果不受影响。",
    }


@router.put("")
async def update_runtime_config(payload: dict, x_admin_token: str | None = Header(default=None)):
    ok, msg = validate_admin_token(x_admin_token)
    if not ok:
        raise HTTPException(status_code=401, detail=msg)

    saved = save_runtime_config(payload)
    active = get_active_keys()
    return {
        "status": "updated",
        "saved": {
            "youtube_api_key": _mask(saved.get("youtube_api_key", "")),
            "perspective_api_key": _mask(saved.get("perspective_api_key", "")),
        },
        "active": {
            "youtube_api_key_set": bool(active.get("youtube_api_key")),
            "perspective_api_key_set": bool(active.get("perspective_api_key")),
        },
        "missing": check_config(),
    }
