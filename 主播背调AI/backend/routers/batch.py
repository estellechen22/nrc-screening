"""批量筛查与导出路由"""
from __future__ import annotations

import csv
import io
import json
import uuid
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import PlainTextResponse

from database import get_db
from services.screen_engine import run_full_screening
from services.utils import detect_platform, extract_channel_id

router = APIRouter(prefix="/api", tags=["batch"])


@router.get("/batch/template")
async def download_batch_template():
    """下载批量筛查CSV模板"""
    content = "url\nhttps://www.youtube.com/@creator_one\nhttps://www.youtube.com/@creator_two\n"
    headers = {"Content-Disposition": "attachment; filename=batch_template.csv"}
    return PlainTextResponse(content=content, headers=headers, media_type="text/csv")


async def _run_and_update_batch(url: str, screen_id: str, creator_id: str, batch_id: str):
    """执行单条筛查并更新批次进度（独立数据库连接）"""
    db = get_db()
    try:
        try:
            await run_full_screening(url, db, screen_id, creator_id)
            db.execute(
                "UPDATE batch_jobs SET completed_count=completed_count+1 WHERE id=?",
                (batch_id,),
            )
        except Exception as e:
            db.execute(
                "UPDATE batch_jobs SET failed_count=failed_count+1 WHERE id=?",
                (batch_id,),
            )
            db.execute(
                "UPDATE screen_results SET status='failed', error_message=? WHERE id=?",
                (str(e), screen_id),
            )

        # 检查是否全部完成
        job = db.execute("SELECT * FROM batch_jobs WHERE id=?", (batch_id,)).fetchone()
        if job:
            job = dict(job)
            if job["completed_count"] + job["failed_count"] >= job["total_count"]:
                db.execute(
                    "UPDATE batch_jobs SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=?",
                    (batch_id,),
                )
        db.commit()
    finally:
        db.close()


@router.post("/batch")
async def start_batch(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """上传 CSV 批量筛查（第一列为 URL）"""
    content = await file.read()
    text = content.decode("utf-8-sig")

    urls = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if row and row[0].strip():
            url = row[0].strip()
            if url.startswith("http"):
                urls.append(url)

    if not urls:
        return {"error": "未找到有效URL"}

    db = get_db()
    try:
        batch_id = uuid.uuid4().hex[:12]

        db.execute(
            "INSERT INTO batch_jobs (id, file_name, total_count) VALUES (?, ?, ?)",
            (batch_id, file.filename, len(urls)),
        )

        # 逐个创建筛查记录
        tasks_meta = []
        for url in urls:
            platform = detect_platform(url)
            channel_id = extract_channel_id(url, platform)
            if not channel_id:
                channel_id = f"parsed_{uuid.uuid4().hex[:10]}"
            creator_id = uuid.uuid4().hex[:12]
            screen_id = uuid.uuid4().hex[:12]

            db.execute(
                "INSERT INTO creators (id, platform, url, channel_id) VALUES (?, ?, ?, ?)",
                (creator_id, platform, url, channel_id),
            )
            db.execute(
                "INSERT INTO screen_results (id, creator_id, status, batch_job_id) VALUES (?, ?, 'pending', ?)",
                (screen_id, creator_id, batch_id),
            )
            tasks_meta.append((url, screen_id, creator_id))

        db.commit()
    finally:
        db.close()

    # 异步批量执行（每条任务内部自行管理连接）
    if background_tasks:
        for url, screen_id, creator_id in tasks_meta:
            background_tasks.add_task(_run_and_update_batch, url, screen_id, creator_id, batch_id)

    return {
        "batch_id": batch_id,
        "total": len(urls),
        "message": f"已创建 {len(urls)} 个筛查任务, 正在后台执行",
    }


@router.get("/batch/{batch_id}")
async def get_batch_progress(batch_id: str):
    """获取批量任务进度"""
    db = get_db()
    try:
        job = db.execute("SELECT * FROM batch_jobs WHERE id=?", (batch_id,)).fetchone()
        if not job:
            return {"error": "批次未找到"}
        return dict(job)
    finally:
        db.close()


@router.get("/batch/{batch_id}/results")
async def get_batch_results(batch_id: str):
    """获取批次内筛查结果列表"""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT s.id as screen_id, s.status, s.composite_score, s.verdict, s.veto_flags, s.created_at, "
            "c.name, c.handle, c.platform, c.url, c.subs, c.country "
            "FROM screen_results s JOIN creators c ON s.creator_id=c.id "
            "WHERE s.batch_job_id=? ORDER BY s.created_at DESC",
            (batch_id,),
        ).fetchall()

        items = []
        for row in rows:
            d = dict(row)
            d["veto_flags"] = json.loads(d["veto_flags"]) if d.get("veto_flags") else []
            items.append(d)

        return {"batch_id": batch_id, "total": len(items), "items": items}
    finally:
        db.close()


@router.get("/batch/{batch_id}/export")
async def export_batch_excel(batch_id: str):
    """导出批量筛查结果为 Excel"""
    from fastapi.responses import FileResponse
    from export.excel_exporter import export_batch_to_excel

    db = get_db()
    try:
        # 获取批次信息
        job = db.execute("SELECT * FROM batch_jobs WHERE id=?", (batch_id,)).fetchone()
        if not job:
            return {"error": "批次未找到"}

        # 获取该批次所有筛查结果
        rows = db.execute(
            "SELECT s.*, c.name, c.handle, c.platform, c.url, c.subs, c.country "
            "FROM screen_results s JOIN creators c ON s.creator_id=c.id "
            "WHERE s.batch_job_id=? ORDER BY s.composite_score ASC",
            (batch_id,),
        ).fetchall()

        items = [dict(r) for r in rows]
    finally:
        db.close()

    filepath = export_batch_to_excel(batch_id, items)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"batch_{batch_id}.xlsx",
    )


@router.get("/screen/{screen_id}/export")
async def export_single_excel(screen_id: str):
    """导出单个筛查结果 Excel"""
    from fastapi.responses import FileResponse
    from export.excel_exporter import export_single_to_excel

    db = get_db()
    try:
        sr = db.execute("SELECT * FROM screen_results WHERE id=?", (screen_id,)).fetchone()
        if not sr:
            return {"error": "筛查未找到"}

        cr = db.execute("SELECT * FROM creators WHERE id=?", (sr["creator_id"],)).fetchone()
        layers = db.execute(
            "SELECT * FROM layer_results WHERE screen_result_id=? ORDER BY layer_number",
            (screen_id,),
        ).fetchall()

        sr_dict = dict(sr)
        sr_dict["veto_flags"] = json.loads(sr_dict["veto_flags"]) if sr_dict.get("veto_flags") else []

        filepath = export_single_to_excel(
            sr_dict,
            dict(cr) if cr else {},
            [dict(l) for l in layers],
        )

        file_name = f"{(cr['name'] if cr else None) or (cr['handle'] if cr else None) or screen_id}.xlsx"
    finally:
        db.close()

    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_name,
    )
