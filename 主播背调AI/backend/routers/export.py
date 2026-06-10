"""导出 API 路由 — 生成 Excel 报告并下载"""
from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from database import get_db
from export.excel_exporter import export_single_to_excel, export_batch_to_excel

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/screen/{screen_id}")
async def export_single(screen_id: str):
    """导出单条筛查结果为 Excel"""
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
                    d[field] = json.loads(d[field]) if isinstance(d[field], str) else d[field]
                else:
                    d[field] = []
            layers_data.append(d)

        result_data = {
            "id": sr["id"],
            "composite_score": sr["composite_score"],
            "verdict": sr["verdict"],
            "veto_flags": json.loads(sr["veto_flags"]) if sr.get("veto_flags") else [],
        }

        creator_data = {
            "name": cr.get("name", ""),
            "handle": cr.get("handle", ""),
            "platform": cr.get("platform", ""),
            "url": cr.get("url", ""),
            "subs": cr.get("subs"),
            "country": cr.get("country", ""),
        }

        filepath = export_single_to_excel(result_data, creator_data, layers_data)

        return FileResponse(
            path=filepath,
            filename=f"背调报告_{cr.get('handle', 'unknown')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    finally:
        db.close()


@router.post("/batch")
async def export_batch(items: list[str]):
    """导出多条筛查结果汇总为 Excel"""
    db = get_db()
    try:
        results = []
        for screen_id in items:
            sr = db.execute("SELECT * FROM screen_results WHERE id=?", (screen_id,)).fetchone()
            if not sr:
                continue
            sr = dict(sr)
            cr = db.execute("SELECT * FROM creators WHERE id=?", (sr["creator_id"],)).fetchone()
            cr = dict(cr) if cr else {}
            results.append({
                "id": sr["id"],
                "name": cr.get("name") or cr.get("handle", "Unknown"),
                "handle": cr.get("handle", ""),
                "platform": cr.get("platform", ""),
                "url": cr.get("url", ""),
                "subs": cr.get("subs"),
                "country": cr.get("country", ""),
                "composite_score": sr["composite_score"],
                "verdict": sr["verdict"],
                "status": sr["status"],
                "veto_flags": json.loads(sr["veto_flags"]) if sr.get("veto_flags") else [],
            })

        if not results:
            raise HTTPException(404, "未找到有效筛查记录")

        batch_id = f"batch_{len(results)}items"
        filepath = export_batch_to_excel(batch_id, results)

        return FileResponse(
            path=filepath,
            filename=f"批量背调报告_{len(results)}人.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    finally:
        db.close()
