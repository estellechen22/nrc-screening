"""L2 内容全量回溯：yt-dlp 批量下载字幕 → 关键词扫描 → 情感分析 → 检出风险信号"""
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from services.utils import run_cmd, load_json_file

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

# yt-dlp 路径自动检测（解决非标准安装路径问题）
_YT_DLP_CANDIDATES = [
    shutil.which("yt-dlp"),
    os.path.expanduser("~/.local/bin/yt-dlp"),
    os.path.expanduser("~/Library/Python/3.9/bin/yt-dlp"),
    "/usr/local/bin/yt-dlp",
    "/opt/homebrew/bin/yt-dlp",
]
YT_DLP = "yt-dlp"
for p in _YT_DLP_CANDIDATES:
    if p and os.path.isfile(p) and os.access(p, os.X_OK):
        YT_DLP = p
        break

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SUBTITLE_DIR = os.path.join(DATA_DIR, "subtitles")
KEYWORDS_POLITICAL_PATH = os.path.join(DATA_DIR, "keywords_political.json")
KEYWORDS_COMPETITOR_PATH = os.path.join(DATA_DIR, "keywords_competitor.json")

CUTOFF_MONTHS = 12  # 默认回溯月数（无日期参数时使用）


def _layer2_skip(reason: str) -> dict:
    """返回一个"跳过"结果（非致命，但标记为低分）"""
    return {
        "score": 50,
        "level": "medium",
        "signals": [{"icon": "⚠️", "date": "", "text": f"内容回溯跳过: {reason}"}],
        "risk_keywords": [],
        "details": [
            {"section": "执行状态", "items": [
                {"label": "内容回溯", "value": "已跳过", "cls": "warn"},
                {"label": "原因", "value": reason, "cls": "warn"},
            ]}
        ],
    }


def _layer2_fallback(reason: str) -> dict:
    """返回一个降级结果（部分成功）"""
    return {
        "score": 60,
        "level": "medium",
        "signals": [{"icon": "⚪", "date": "", "text": f"内容回溯降级: {reason}"}],
        "risk_keywords": [],
        "details": [
            {"section": "执行状态", "items": [
                {"label": "内容回溯", "value": "降级执行", "cls": "warn"},
                {"label": "原因", "value": reason, "cls": "warn"},
            ]}
        ],
    }


async def run_layer2(url: str, platform: str, log: list,
                     date_from: str | None = None,
                     date_to: str | None = None) -> dict:
    """
    yt-dlp 批量下载字幕 → 关键词扫描 → 情感分析 → 检出风险信号
    date_from / date_to: 可选，YYYYMMDD 格式，指定视频发布日期区间
    """
    log.append("[L2] 开始内容历史全量回溯...")

    if platform != "youtube":
        return _layer2_skip(f"暂不支持 {platform} 平台的内容回溯（当前仅支持 YouTube）")

    # 清理旧字幕
    os.makedirs(SUBTITLE_DIR, exist_ok=True)

    # ── 确定日期区间 ──
    if date_from:
        # 用户指定了起始日期
        date_after = date_from
        if date_to:
            date_before = date_to
        else:
            # 未指定截止日期，默认为起始 + 6 个月
            from_dt = datetime.strptime(date_from, "%Y%m%d")
            to_dt = from_dt + timedelta(days=180)
            date_before = to_dt.strftime("%Y%m%d")
        log.append(f"[L2] 日期区间: {date_after} ~ {date_before}（用户指定）")
    else:
        # 无日期参数，使用默认回溯月数
        date_after = (datetime.now() - timedelta(days=CUTOFF_MONTHS * 30)).strftime("%Y%m%d")
        date_before = datetime.now().strftime("%Y%m%d")
        log.append(f"[L2] 获取视频列表 (最近{CUTOFF_MONTHS}个月)...")

    # 获取视频ID列表（限制最多100条，避免超时）
    date_filter = f"--dateafter {date_after} --datebefore {date_before}"
    cmd = (
        f'{YT_DLP} --flat-playlist --playlist-end 100 {date_filter} '
        f'--print "%(id)s|||%(title)s|||%(upload_date)s" '
        f'"{url}/videos" 2>&1'
    )

    result = run_cmd(cmd, timeout=120)
    if not result["success"] or not result["stdout"]:
        return _layer2_skip("yt-dlp 获取视频列表失败, 请确认 yt-dlp 已安装 (brew install yt-dlp)")

    video_lines = result["stdout"].strip().split("\n")
    video_data = []
    for line in video_lines:
        parts = line.split("|||")
        if len(parts) >= 3:
            video_data.append({"id": parts[0], "title": parts[1], "date": parts[2]})

    log.append(f"[L2] 找到 {len(video_data)} 条视频, 开始下载字幕...")

    # 批量下载字幕 (只下载文本, 较快)
    video_ids = [v["id"] for v in video_data[:50]]  # 限制50条
    downloaded = 0
    no_caption_ids = []

    for vid in video_ids:
        # 检测是否已有字幕文件
        existing = glob.glob(f"{vid}*.srt") + glob.glob(f"{vid}*.vtt")
        if existing:
            downloaded += 1
            continue

        # 尝试多种方式获取字幕
        subtitle_found = False
        for attempt in range(3):
            if attempt == 0:
                # 方式1: 自动英文字幕
                cmd = (
                    f'{YT_DLP} --skip-download --write-auto-sub --sub-lang en --sub-format "vtt/srt" '
                    f'--no-check-certificate --extractor-retries 3 --ignore-errors '
                    f'-o "{vid}.%(ext)s" '
                    f'"https://www.youtube.com/watch?v={vid}" 2>&1'
                )
            elif attempt == 1:
                # 方式2: 手动英文字幕
                cmd = (
                    f'{YT_DLP} --skip-download --write-sub --sub-lang en --sub-format "vtt/srt" '
                    f'--no-check-certificate --extractor-retries 3 --ignore-errors '
                    f'-o "{vid}.%(ext)s" '
                    f'"https://www.youtube.com/watch?v={vid}" 2>&1'
                )
            else:
                # 方式3: 允许所有语言字幕
                cmd = (
                    f'{YT_DLP} --skip-download --write-auto-sub --sub-langs all --sub-format "vtt/srt" '
                    f'--no-check-certificate --extractor-retries 3 --ignore-errors '
                    f'-o "{vid}.%(ext)s" '
                    f'"https://www.youtube.com/watch?v={vid}" 2>&1'
                )

            r = run_cmd(cmd, timeout=60, cwd=SUBTITLE_DIR)

            # 检查是否真的下载了字幕文件
            new_files = glob.glob(os.path.join(SUBTITLE_DIR, f"{vid}*.srt")) + glob.glob(os.path.join(SUBTITLE_DIR, f"{vid}*.vtt"))
            if new_files:
                subtitle_found = True
                break

        if subtitle_found:
            downloaded += 1
        else:
            no_caption_ids.append(vid)

    log.append(f"[L2] 成功下载 {downloaded}/{len(video_ids)} 条字幕")

    # 读取字幕内容（支持 .srt 和 .vtt）
    all_texts = {}  # vid -> [text, ...]
    sub_files = glob.glob(os.path.join(SUBTITLE_DIR, "*.srt")) + glob.glob(os.path.join(SUBTITLE_DIR, "*.vtt"))
    for sub_path in sub_files:
        vid = os.path.basename(sub_path).split(".")[0]
        try:
            with open(sub_path, "r", errors="ignore") as f:
                content = f.read()
            # 移除时间轴/序号/WebVTT头部行
            lines = []
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.isdigit() or "-->" in line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
                    continue
                lines.append(line)
            all_texts[vid] = lines
        except:
            continue

    # === 关键词扫描 ===
    political_kw = load_json_file(KEYWORDS_POLITICAL_PATH)
    competitor_kw = load_json_file(KEYWORDS_COMPETITOR_PATH)

    keyword_hits = {}
    risk_keywords = set()

    for vid, vid_title in [(v["id"], v["title"]) for v in video_data]:
        lines = all_texts.get(vid, [])
        clean_text = " ".join(lines).lower() if lines else ""

        # 扫描政治关键词
        for cat_key, cat_data in political_kw.items():
            if not isinstance(cat_data, dict) or "keywords" not in cat_data:
                continue
            keywords = cat_data["keywords"]
            for kw in keywords:
                search_text = (clean_text + " " + vid_title).lower()
                # 使用词边界匹配，避免 "jew" 误配 "jewelry"
                pattern = re.compile(r'\b' + re.escape(kw.lower()) + r'\b', re.IGNORECASE)
                if pattern.search(search_text):
                    key = f"{cat_key}:{kw}"
                    if key not in keyword_hits:
                        keyword_hits[key] = []
                    idx = search_text.lower().find(kw.lower())
                    ctx = search_text[max(0, idx - 60):idx + len(kw) + 60]
                    keyword_hits[key].append({"video_id": vid, "title": vid_title, "context": f"...{ctx}..."})

                    critical_categories = {"geo_sensitive", "anti_china_narrative", "stigmatization", "religious_sensitivity"}
                    risk_keywords.add((kw, "critical" if cat_key in critical_categories else "warning"))

        # 扫描竞品关键词
        for cat_key, cat_data in competitor_kw.items():
            if not isinstance(cat_data, dict) or "keywords" not in cat_data:
                continue
            keywords = cat_data["keywords"]
            for kw in keywords:
                pattern = re.compile(r'\b' + re.escape(kw.lower()) + r'\b', re.IGNORECASE)
                if pattern.search(clean_text + " " + vid_title):
                    risk_keywords.add((kw, "info"))

    # 生成风险信号
    signals = []
    for key, hits in keyword_hits.items():
        category, kw = key.split(":", 1)
        critical_cats = {"geo_sensitive", "anti_china_narrative", "stigmatization", "religious_sensitivity"}
        for h in hits[:5]:
            signals.append({
                "icon": "🔴" if category in critical_cats else "🟡",
                "date": "",
                "text": f'[{category}] 视频 "{h["title"]}" 中检出 "{kw}": {h["context"]}',
            })

    # 转 risk_keywords 为前端格式
    risk_tags = []
    seen = set()
    for kw, rtype in risk_keywords:
        if kw not in seen:
            risk_tags.append({"text": kw, "type": rtype})
            seen.add(kw)

    # === 情感分析（TextBlob） ===
    sentiment_metrics = {"polarity": 0.0, "subjectivity": 0.0, "positive_pct": 0, "negative_pct": 0, "neutral_pct": 0, "lines_analyzed": 0}
    sentiment_negative_vids = []
    if HAS_TEXTBLOB:
        all_polarities = []
        all_subjectivities = []
        polarity_buckets = {"positive": 0, "negative": 0, "neutral": 0}
        for vid, lines in all_texts.items():
            text = " ".join(lines)
            if len(text.strip()) < 20:
                continue
            try:
                blob = TextBlob(text[:5000])  # 限制5000字符/视频
                polarity = blob.sentiment.polarity
                subjectivity = blob.sentiment.subjectivity
                all_polarities.append(polarity)
                all_subjectivities.append(subjectivity)
                if polarity > 0.1:
                    polarity_buckets["positive"] += 1
                elif polarity < -0.1:
                    polarity_buckets["negative"] += 1
                else:
                    polarity_buckets["neutral"] += 1
                # 记录极端负面视频 (polarity < -0.5)
                if polarity < -0.5:
                    sentiment_negative_vids.append({"vid": vid, "polarity": round(polarity, 2)})
            except:
                continue
        total = len(all_polarities)
        if total > 0:
            sentiment_metrics = {
                "polarity": round(sum(all_polarities) / total, 2),
                "subjectivity": round(sum(all_subjectivities) / total, 2),
                "positive_pct": round(polarity_buckets["positive"] / total * 100),
                "negative_pct": round(polarity_buckets["negative"] / total * 100),
                "neutral_pct": round(polarity_buckets["neutral"] / total * 100),
                "lines_analyzed": total,
            }
            # 如果有极端负面视频，生成信号
            for nv in sorted(sentiment_negative_vids, key=lambda x: x["polarity"])[:3]:
                signals.append({
                    "icon": "🔴",
                    "date": "",
                    "text": f'[情感分析] 视频 {nv["vid"]} 情感极性 {nv["polarity"]}（极端负面）',
                })
        log.append(f"[L2] 情感分析完成: {total} 段字幕, 平均极性 {sentiment_metrics['polarity']}")

    # 计算分数
    phrase_count = len(keyword_hits)
    if phrase_count == 0:
        score = 90
        level = "low"
    elif phrase_count <= 3:
        score = 70
        level = "low"
    elif phrase_count <= 10:
        score = 50
        level = "medium"
    elif phrase_count <= 30:
        score = 30
        level = "high"
    else:
        score = 10
        level = "critical"

    # 有红线命中时降分
    critical_hits = sum(1 for k in keyword_hits if any(c in k for c in ["geo_sensitive", "anti_china_narrative", "stigmatization", "religious_sensitivity"]))
    if critical_hits > 0:
        score = max(5, score - 25)
        if level == "low":
            level = "medium"

    details = [
        {"section": "扫描结果", "items": [
            {"label": "视频总数", "value": str(len(video_data)), "cls": "good"},
            {"label": "发布时间区间", "value": f"{date_after} ~ {date_before}", "cls": "info"},
            {"label": "字幕下载", "value": f"{downloaded}/{len(video_ids)}", "cls": "good" if downloaded > len(video_ids) * 0.7 else "warn"},
            {"label": "关键词命中", "value": str(phrase_count), "cls": "bad" if phrase_count > 10 else ("warn" if phrase_count > 0 else "good")},
            {"label": "红线命中", "value": str(critical_hits), "cls": "bad" if critical_hits > 0 else "good"},
            {"label": "无字幕视频", "value": str(len(no_caption_ids)), "cls": "info"},
        ]},
        {"section": "关键词扫描", "items": [
            {"label": "政治关键词命中", "value": f"{sum(len(v) for k, v in keyword_hits.items() if any(c in k for c in ['geo_sensitive','anti_china_narrative','stigmatization','religious_sensitivity','war_conflict','gender_issues']))} 次", "cls": "bad" if keyword_hits else "good"},
            {"label": "一般敏感命中", "value": f"{sum(len(v) for k, v in keyword_hits.items() if not any(c in k for c in ['geo_sensitive','anti_china_narrative','stigmatization','religious_sensitivity','war_conflict','gender_issues']))} 次", "cls": "warn" if keyword_hits else "good"},
            {"label": "字幕覆盖率", "value": f"{downloaded/(len(video_ids))*100:.0f}%", "cls": "good" if downloaded > len(video_ids) * 0.7 else "warn"},
        ]},
        {"section": "情感分析", "items": [
            {"label": "分析引擎", "value": "TextBlob (NLP)" if HAS_TEXTBLOB else "TextBlob 未安装", "cls": "good" if HAS_TEXTBLOB else "warn"},
            {"label": "字幕段数", "value": f'{sentiment_metrics["lines_analyzed"]} 段', "cls": "good" if sentiment_metrics["lines_analyzed"] > 10 else "info"},
            {"label": "情感极性", "value": f'{sentiment_metrics["polarity"]} (范围 -1~1)', "cls": "bad" if sentiment_metrics["polarity"] < -0.3 else ("good" if sentiment_metrics["polarity"] > 0.1 else "info")},
            {"label": "主观性", "value": f'{sentiment_metrics["subjectivity"]} (0~1)', "cls": "info"},
            {"label": "积极占比", "value": f'{sentiment_metrics["positive_pct"]}%', "cls": "good" if sentiment_metrics["positive_pct"] > 50 else "warn"},
            {"label": "消极占比", "value": f'{sentiment_metrics["negative_pct"]}%', "cls": "bad" if sentiment_metrics["negative_pct"] > 20 else "good"},
            {"label": "中性占比", "value": f'{sentiment_metrics["neutral_pct"]}%', "cls": "info"},
            {"label": "极端负面视频", "value": str(len(sentiment_negative_vids)), "cls": "bad" if sentiment_negative_vids else "good"},
        ]},
    ]

    log.append(f"[L2] 完成内容回溯, 得分 {score}/{level}")
    return {
        "score": score,
        "level": level,
        "signals": signals,
        "risk_keywords": risk_tags,
        "details": details,
    }
