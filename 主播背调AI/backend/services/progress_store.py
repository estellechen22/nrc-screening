"""
筛查进度存储 — 内存共享，支持 SSE 实时推送
"""
import time

_progress_store: dict[str, dict] = {}


def update_progress(screen_id: str, **kwargs):
    """更新某条筛查的进度（从筛查引擎调用）"""
    if screen_id not in _progress_store:
        _progress_store[screen_id] = {"_last_log_len": 0}
    entry = _progress_store[screen_id]
    for k, v in kwargs.items():
        entry[k] = v
    entry["_updated_at"] = time.time()


def get_progress(screen_id: str) -> dict | None:
    """获取进度（从 SSE 端点调用）"""
    return _progress_store.get(screen_id)


def clear_progress(screen_id: str):
    """清理进度"""
    _progress_store.pop(screen_id, None)
