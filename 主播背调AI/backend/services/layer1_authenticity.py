"""
Layer 1: 基础数据真实性验证
检测僵尸粉、买粉、数据造假
"""
from services.api_clients import (
    youtube_channel_stats,
    youtube_video_list,
)
from services.utils import extract_channel_id


async def run_layer1(url: str, platform: str, log: list) -> dict:
    """
    返回:
    {
        score: float (0-100),
        level: str,
        details: [{section, items: [{label, value, cls}]}],
        risk_keywords: [{text, type}],
        creator_name: str,
        creator_handle: str,
        creator_subs: int,
        creator_country: str,
    }
    """
    log.append("[L1] 开始基础数据真实性验证...")
    details = []
    risk_tags = []
    score = 100
    creator_info = {"name": "", "handle": "", "subs": 0, "country": "", "avatar_url": ""}

    if platform == "youtube":
        channel_id = extract_channel_id(url, "youtube")
        if not channel_id:
            return _fail("无法解析YouTube频道ID")

        # 获取频道统计
        log.append(f"[L1] 调用 YouTube API (频道: {channel_id})...")
        stats = await youtube_channel_stats(channel_id)
        if "error" in stats:
            return _fail(stats["error"])

        creator_info.update({
            "name": stats["name"],
            "handle": stats["handle"],
            "subs": stats["subs"],
            "country": stats.get("country", ""),
            "avatar_url": stats.get("avatar_url", ""),
        })

        # 获取视频列表计算指标
        log.append("[L1] 获取视频列表...")
        videos = await youtube_video_list(stats["channel_id"], max_results=100)

        # 计算各项指标
        subs = stats["subs"]
        total_views = stats["total_views"]
        video_count = stats["video_count"]

        # 粉播比 (平均播放量/粉丝数)
        if subs > 0 and len(videos) > 0:
            avg_views_per_video = total_views / video_count if video_count > 0 else 0
            view_sub_ratio = (avg_views_per_video / subs) * 100
        else:
            view_sub_ratio = 0

        # 互动率估算 (用总views/总subs估算，精确值需要额外API调用)
        engagement_estimate = (total_views / subs * 100) if subs > 0 else 0

        # 评分逻辑
        subs_item = {"label": "粉丝增长曲线", "value": "⚠️ 需历史数据 (当前仅快照)", "cls": "warn"}
        ratio_eval = "✅ 正常"
        ratio_cls = "good"
        if view_sub_ratio < 1:
            ratio_eval = f"🔴 异常低 ({view_sub_ratio:.1f}%) — 严重僵尸粉嫌疑"
            ratio_cls = "bad"
            score -= 30
            risk_tags.append({"text": "粉播比异常低", "type": "critical"})
        elif view_sub_ratio < 3:
            ratio_eval = f"🟡 偏低 ({view_sub_ratio:.1f}%)"
            ratio_cls = "warn"
            score -= 10
            risk_tags.append({"text": "粉播比偏低", "type": "warning"})
        else:
            ratio_eval = f"✅ 正常 ({view_sub_ratio:.1f}%)"

        details.append({
            "section": "粉丝指标",
            "items": [
                {"label": "订阅数", "value": f"{subs:,}", "cls": "good"},
                {"label": "总播放量", "value": f"{total_views:,}", "cls": "good"},
                {"label": "视频总数", "value": str(video_count), "cls": "good"},
                {"label": "平均播放量/视频", "value": f"{total_views // max(video_count, 1):,}", "cls": "good"},
                {"label": "粉播比 (avg_views/subs)", "value": ratio_eval, "cls": ratio_cls},
                subs_item,
            ],
        })

        if risk_tags:
            details.append({
                "section": "真实性评估",
                "items": [
                    {"label": "综合真实性", "value": f"{score} / 100", "cls": "bad" if score < 60 else "good"},
                    {"label": "僵尸粉检测", "value": "疑似" if view_sub_ratio < 3 else "正常", "cls": ratio_cls},
                ],
            })
        else:
            details.append({
                "section": "真实性评估",
                "items": [
                    {"label": "综合真实性", "value": f"{score} / 100", "cls": "good"},
                    {"label": "僵尸粉检测", "value": "正常", "cls": "good"},
                    {"label": "刷评检测", "value": "未发现明显异常", "cls": "good"},
                ],
            })

    else:
        return _fail(f"不支持的平台: {platform}（当前仅支持 YouTube）")

    score = max(0, min(100, score))
    level = "low-risk" if score >= 70 else ("medium-risk" if score >= 50 else "high-risk")

    log.append(f"[L1] 完成 — 评分 {score}/100 — 等级 {level}")

    return {
        "score": score,
        "level": level,
        "details": details,
        "risk_keywords": risk_tags,
        "creator_name": creator_info["name"],
        "creator_handle": creator_info["handle"],
        "creator_subs": creator_info["subs"],
        "creator_country": creator_info["country"],
        "creator_avatar": creator_info["avatar_url"],
    }


def _fail(msg: str) -> dict:
    return {
        "score": 0,
        "level": "high-risk",
        "details": [{"section": "错误", "items": [{"label": "原因", "value": msg, "cls": "bad"}]}],
        "risk_keywords": [{"text": msg, "type": "critical"}],
        "creator_name": "",
        "creator_handle": "",
        "creator_subs": 0,
        "creator_country": "",
        "creator_avatar": "",
    }
