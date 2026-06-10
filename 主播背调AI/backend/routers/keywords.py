"""关键词库管理路由"""
import os

from fastapi import APIRouter, HTTPException

from services.utils import load_json_file, save_json_file

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


@router.get("/political")
async def get_political_keywords():
    """获取政治敏感关键词库"""
    path = os.path.join(DATA_DIR, "keywords_political.json")
    return load_json_file(path)


@router.put("/political")
async def update_political_keywords(data: dict):
    """更新政治敏感关键词库"""
    path = os.path.join(DATA_DIR, "keywords_political.json")
    save_json_file(path, data)
    return {"status": "updated", "categories": list(data.keys())}


@router.get("/competitor")
async def get_competitor_keywords():
    """获取竞品关键词库"""
    path = os.path.join(DATA_DIR, "keywords_competitor.json")
    return load_json_file(path)


@router.put("/competitor")
async def update_competitor_keywords(data: dict):
    """更新竞品关键词库"""
    path = os.path.join(DATA_DIR, "keywords_competitor.json")
    save_json_file(path, data)
    return {"status": "updated", "categories": list(data.keys())}
