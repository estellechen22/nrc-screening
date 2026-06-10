"""筛查 API 路由"""
from __future__ import annotations

import asyncio
import json
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from database import get_db
from models import ScreenRequest
from services.screen_engine import run_full_screening
from services.utils import detect_platform, extract_channel_id
from services.progress_store import update_progress, get_progress, clear_progress

router = APIRouter(prefix="/api", tags=["screen"])


async def _run_single_screening_task(url: str, screen_id: str, creator_id: str,
                                      date_from: str | None = None,
                                      date_to: str | None = None) -> None:
    """后台执行单条筛查（独立数据库连接，避免跨请求复用）"""
    db = get_db()
    try:
        await run_full_screening(url, db, screen_id, creator_id, date_from, date_to)
    finally:
        db.close()


@router.post("/screen", response_model=dict)
async def start_screening(req: ScreenRequest, background_tasks: BackgroundTasks):
    """提交单个筛查任务"""
    platform = req.platform or detect_platform(req.url)
    channel_id = extract_channel_id(req.url, platform)
    if not channel_id:
        channel_id = f"parsed_{uuid.uuid4().hex[:10]}"  # URL解析失败时使用唯一标识

    db = get_db()
    try:
        creator_id = uuid.uuid4().hex[:12]
        screen_id = uuid.uuid4().hex[:12]

        db.execute(
            "INSERT INTO creators (id, platform, url, channel_id) VALUES (?, ?, ?, ?)",
            (creator_id, platform, req.url, channel_id),
        )
        db.execute(
            "INSERT INTO screen_results (id, creator_id, status) VALUES (?, ?, 'pending')",
            (screen_id, creator_id),
        )
        db.commit()
    finally:
        db.close()

    # 异步启动筛查（内部自行创建数据库连接）
    background_tasks.add_task(_run_single_screening_task, req.url, screen_id, creator_id,
                              req.date_from, req.date_to)

    # 初始化进度 — 前端立即可见
    update_progress(screen_id, screen_id=screen_id, status="pending", current_step=0,
                    step_name="等待调度", detail="任务已提交，等待执行引擎启动...", log=[])

    return {
        "screen_id": screen_id,
        "creator_id": creator_id,
        "status": "pending",
        "message": "筛查任务已提交, 请轮询 GET /api/screen/{id} 查看进度",
    }


@router.get("/screen/{screen_id}", response_model=dict)
async def get_screening_result(screen_id: str):
    """获取筛查结果 (含六层详情)"""
    db = get_db()
    try:
        sr = db.execute("SELECT * FROM screen_results WHERE id=?", (screen_id,)).fetchone()
        if not sr:
            raise HTTPException(404, "筛查记录未找到")

        sr = dict(sr)

        cr = db.execute("SELECT * FROM creators WHERE id=?", (sr["creator_id"],)).fetchone()
        cr = dict(cr) if cr else {}

        layers = db.execute(
            "SELECT * FROM layer_results WHERE screen_result_id=? ORDER BY layer_number",
            (screen_id,),
        ).fetchall()

        layers_data = []
        for row in layers:
            d = dict(row)
            for field in ("details", "signals", "risk_keywords"):
                if d.get(field):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        d[field] = []
                else:
                    d[field] = []
            layers_data.append(d)

        return {
            "result": {
                "id": sr["id"],
                "creator_id": sr["creator_id"],
                "status": sr["status"],
                "composite_score": sr["composite_score"],
                "verdict": sr["verdict"],
                "veto_flags": json.loads(sr["veto_flags"]) if sr["veto_flags"] else [],
                "started_at": sr["started_at"],
                "completed_at": sr["completed_at"],
                "error_message": sr["error_message"],
            },
            "creator": {
                "id": cr.get("id", ""),
                "platform": cr.get("platform", ""),
                "url": cr.get("url", ""),
                "name": cr.get("name", ""),
                "handle": cr.get("handle", ""),
                "subs": cr.get("subs"),
                "country": cr.get("country", ""),
                "content_lang": cr.get("content_lang", ""),
                "category": cr.get("category", ""),
                "avatar_url": cr.get("avatar_url", ""),
            },
            "layers": layers_data,
        }
    finally:
        db.close()


@router.get("/screen/{screen_id}/progress")
async def stream_progress(screen_id: str):
    """SSE 实时进度推送"""

    async def event_generator():
        last_log_len = 0
        sent_done = False
        while True:
            prog = get_progress(screen_id)
            if not prog:
                yield f"data: {json.dumps({'status': 'waiting', 'detail': '等待进度数据...'})}\n\n"
                await asyncio.sleep(1)
                continue

            # 已完成/失败 — 发送最终状态后断开
            if prog.get("status") in ("completed", "failed") and not sent_done:
                yield f"data: {json.dumps(prog)}\n\n"
                sent_done = True
                break

            # 有新日志 — 推送
            log = prog.get("log", [])
            if len(log) > last_log_len:
                yield f"data: {json.dumps(prog)}\n\n"
                last_log_len = len(log)

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/history", response_model=dict)
async def get_history(search: str = "", verdict: str = "", page: int = 1, limit: int = 20):
    """查询历史筛查记录"""
    db = get_db()
    try:
        offset = (page - 1) * limit

        where = ["1=1"]
        params = []
        if search:
            where.append("(c.name LIKE ? OR c.handle LIKE ? OR c.url LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if verdict:
            where.append("s.verdict = ?")
            params.append(verdict)

        count_row = db.execute(
            f"SELECT COUNT(*) FROM screen_results s JOIN creators c ON s.creator_id=c.id "
            f"WHERE {' AND '.join(where)}",
            params,
        ).fetchone()
        total = count_row[0]

        rows = db.execute(
            f"SELECT s.*, c.name, c.handle, c.platform, c.url, c.subs, c.country FROM screen_results s "
            f"JOIN creators c ON s.creator_id=c.id "
            f"WHERE {' AND '.join(where)} "
            f"ORDER BY s.created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        items = []
        for row in rows:
            d = dict(row)
            items.append(
                {
                    "id": d["id"],
                    "creator_name": d["name"] or d["handle"] or "Unknown",
                    "creator_handle": d["handle"] or "",
                    "platform": d["platform"],
                    "url": d["url"],
                    "subs": d["subs"],
                    "country": d.get("country", ""),
                    "status": d["status"],
                    "composite_score": d["composite_score"],
                    "verdict": d["verdict"],
                    "veto_flags": json.loads(d["veto_flags"]) if d.get("veto_flags") else [],
                    "created_at": d["created_at"],
                    "completed_at": d["completed_at"],
                }
            )

        return {"total": total, "page": page, "items": items}
    finally:
        db.close()


@router.delete("/screen/{screen_id}")
async def delete_screening(screen_id: str):
    """删除某条筛查记录"""
    db = get_db()
    try:
        db.execute("DELETE FROM layer_results WHERE screen_result_id=?", (screen_id,))
        sr = db.execute("SELECT creator_id FROM screen_results WHERE id=?", (screen_id,)).fetchone()
        if sr:
            db.execute("DELETE FROM creators WHERE id=?", (sr["creator_id"],))
            db.execute("DELETE FROM screen_results WHERE id=?", (screen_id,))
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()
