"""YouTube / Perspective API 客户端（含无密钥占位降级）"""
from __future__ import annotations

import httpx

from config import get_active_keys


def _stable_num(seed: str, base: int, span: int) -> int:
    return base + (abs(hash(seed)) % span)


# ── YouTube Data API v3 ──

async def youtube_channel_stats(channel_handle: str) -> dict:
    """通过 @handle 或 channel_id 获取频道基础数据"""
    keys = get_active_keys()
    youtube_api_key = keys["youtube_api_key"]

    if not youtube_api_key:
        return {
            "channel_id": f"mock_{channel_handle}",
            "name": f"MockCreator_{channel_handle}",
            "handle": channel_handle.lstrip("@"),
            "subs": _stable_num(channel_handle, 50_000, 200_000),
            "total_views": _stable_num(channel_handle, 3_000_000, 20_000_000),
            "video_count": _stable_num(channel_handle, 80, 220),
            "country": "",
            "content_lang": "",
            "category": "",
            "avatar_url": "",
            "description": "[占位数据] YouTube API Key 未配置",
        }

    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "part": "statistics,snippet,brandingSettings",
        "forHandle": channel_handle,
        "key": youtube_api_key,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        data = r.json()

    if "items" not in data or not data["items"]:
        params2 = {
            "part": "statistics,snippet,brandingSettings",
            "id": channel_handle,
            "key": youtube_api_key,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r2 = await client.get(url, params=params2)
            data = r2.json()

    if "items" not in data or not data["items"]:
        return {"error": "频道未找到或 YouTube API 返回空结果"}

    ch = data["items"][0]
    stats = ch.get("statistics", {})
    snippet = ch.get("snippet", {})

    return {
        "channel_id": ch["id"],
        "name": snippet.get("title", ""),
        "handle": snippet.get("customUrl", channel_handle).lstrip("@"),
        "subs": int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "country": snippet.get("country", ""),
        "content_lang": snippet.get("defaultLanguage", ""),
        "category": "",
        "avatar_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
        "description": snippet.get("description", ""),
    }


async def youtube_video_list(channel_id: str, max_results: int = 200) -> list[dict]:
    """获取频道上传视频列表（仅元数据）"""
    keys = get_active_keys()
    youtube_api_key = keys["youtube_api_key"]

    if not youtube_api_key:
        n = min(max_results, 50)
        return [
            {
                "video_id": f"mock_{i}",
                "title": f"Mock video #{i}",
                "description": "[占位数据] 等待接入 YouTube API Key",
                "published_at": "",
                "thumbnails": {},
            }
            for i in range(1, n + 1)
        ]

    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {"part": "contentDetails", "id": channel_id, "key": youtube_api_key}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        data = r.json()

    if "items" not in data or not data["items"]:
        return []

    uploads_id = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos = []
    page_token = None
    url_pl = "https://www.googleapis.com/youtube/v3/playlistItems"

    while len(videos) < max_results:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": uploads_id,
            "maxResults": min(50, max_results - len(videos)),
            "key": youtube_api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url_pl, params=params)
            data = r.json()

        for item in data.get("items", []):
            sn = item["snippet"]
            videos.append(
                {
                    "video_id": sn["resourceId"]["videoId"],
                    "title": sn.get("title", ""),
                    "description": sn.get("description", ""),
                    "published_at": sn.get("publishedAt", ""),
                    "thumbnails": sn.get("thumbnails", {}),
                }
            )

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return videos


# ── Perspective API ──

async def perspective_analyze(text: str) -> dict:
    """调用 Perspective API 进行毒性分析"""
    keys = get_active_keys()
    perspective_api_key = keys["perspective_api_key"]

    if not perspective_api_key:
        return {
            "TOXICITY": 0.05,
            "SEVERE_TOXICITY": 0.01,
            "INSULT": 0.03,
            "IDENTITY_ATTACK": 0.02,
            "THREAT": 0.0,
            "PROFANITY": 0.04,
            "_note": "Perspective API Key 未配置，返回保守默认值",
        }

    url = f"https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key={perspective_api_key}"
    payload = {
        "comment": {"text": text[:3000]},
        "languages": ["en"],
        "requestedAttributes": {
            "TOXICITY": {},
            "SEVERE_TOXICITY": {},
            "INSULT": {},
            "IDENTITY_ATTACK": {},
            "THREAT": {},
            "PROFANITY": {},
        },
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=payload)
        data = r.json()

    if "error" in data:
        return {"error": data["error"].get("message", "Unknown error")}

    scores = {}
    for attr, val in data.get("attributeScores", {}).items():
        scores[attr] = round(val.get("summaryScore", {}).get("value", 0), 4)

    return scores
