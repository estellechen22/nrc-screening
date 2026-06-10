from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import check_config
from database import get_db, init_db
from routers import batch, keywords, runtime_config, screen
from routers.export import router as export_router

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
STATIC_DIR = PROJECT_ROOT / "static"


app = FastAPI(
    title="主播风险筛查系统",
    description="六层筛查后端服务（Step 6 收口阶段）",
    version="0.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(screen.router)
app.include_router(batch.router)
app.include_router(keywords.router)
app.include_router(runtime_config.router)
app.include_router(export_router)


def _ensure_placeholder_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    placeholder_political = {
        "_note": "正式词库请在 data/keywords_political.json 中补充。以下为框架占位，不会产生虚假匹配。",
        "geo_sensitive": [],
        "anti_china_narrative": [],
        "stigmatization": [],
        "discrimination": [],
        "brand_safety": [],
    }

    placeholder_competitor = {
        "_note": "正式词库请在 data/keywords_competitor.json 中补充。",
        "primary_competitors": ["pokemon", "palworld", "temtem"],
        "negative_comparison_terms": ["clone", "copy", "ripoff"],
    }

    files = {
        DATA_DIR / "keywords_political.json": placeholder_political,
        DATA_DIR / "keywords_competitor.json": placeholder_competitor,
    }

    for path, default_data in files.items():
        if not path.exists():
            path.write_text(json.dumps(default_data, ensure_ascii=False, indent=2), encoding="utf-8")
            continue

        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # 发现损坏文件时回退到占位内容，后续可由你提供正式词库替换
            path.write_text(json.dumps(default_data, ensure_ascii=False, indent=2), encoding="utf-8")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    _ensure_placeholder_files()


@app.get("/api/health")
def health() -> dict:
    missing = check_config()

    db_ok = True
    db_error = ""
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
    except Exception as exc:
        db_ok = False
        db_error = str(exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "missing_config": missing,
        "db_ok": db_ok,
        "db_error": db_error,
        "phase": "step-6-hardening", 
    }


@app.get("/api/config-status")
def config_status() -> dict:
    missing = check_config()
    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "note": "API Keys 暂未配置时，筛查会以占位逻辑运行；配置接口需携带 X-Admin-Token。"
    }


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    dashboard = STATIC_DIR / "index.html"
    if dashboard.exists():
        return FileResponse(str(dashboard))
    return {
        "message": "后端已启动。当前还未放置前端首页文件。",
        "next": "请在 static/index.html 放置前端页面。"
    }
