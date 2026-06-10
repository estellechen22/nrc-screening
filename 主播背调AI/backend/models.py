from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ── Request Models ──

class ScreenRequest(BaseModel):
    url: str
    platform: Optional[str] = None  # 可自动检测
    date_from: Optional[str] = None  # 起始日期 YYYYMMDD，可选
    date_to: Optional[str] = None    # 截止日期 YYYYMMDD，可选，默认自动计算


class ScreenResponse(BaseModel):
    id: str
    creator_id: str
    status: str
    composite_score: Optional[float] = None
    verdict: Optional[str] = None
    veto_flags: Optional[list] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class CreatorInfo(BaseModel):
    id: str
    platform: str
    url: str
    name: Optional[str] = None
    handle: Optional[str] = None
    subs: Optional[int] = None
    country: Optional[str] = None
    content_lang: Optional[str] = None
    category: Optional[str] = None
    avatar_url: Optional[str] = None


class LayerResultData(BaseModel):
    id: str
    layer_number: int
    layer_name: str
    score: Optional[float] = None
    level: Optional[str] = None
    details: Optional[list] = None
    signals: Optional[list] = None
    risk_keywords: Optional[list] = None
    log_output: Optional[str] = None


class FullScreenResult(BaseModel):
    result: ScreenResponse
    creator: CreatorInfo
    layers: list[LayerResultData]


class BatchJobInfo(BaseModel):
    id: str
    file_name: Optional[str] = None
    total_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    status: str = "running"
    created_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    missing_config: list[str] = []
    db_ok: bool = False
