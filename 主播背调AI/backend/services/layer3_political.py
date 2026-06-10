"""
Layer 3: 政治敏感信号检测 (三层递进方案)
① 关键词匹配 (L2已做) → ② Perspective API 深度确认 → ③ LLM 辅助
"""
from services.api_clients import perspective_analyze
from services.utils import load_json_file
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
KEYWORDS_POLITICAL_PATH = os.path.join(DATA_DIR, "keywords_political.json")


async def run_layer3(l2_signals: list, l2_risk_keywords: list, log: list) -> dict:
    """
    基于 L2 产出的风险信号, 用 Perspective API 做深度确认
    """
    log.append("[L3] 开始政治敏感信号检测...")

    critical_signals = []
    other_signals = []

    for s in l2_signals:
        text = s.get("text", "")
        # 分类信号级别
        if any(cat in text for cat in ["领土红线", "反华言论", "污名化", "geo_sensitive", "anti_china_narrative", "stigmatization", "🔴"]):
            critical_signals.append(s)
        else:
            other_signals.append(s)

    # 检查关键词
    political_kw = load_json_file(KEYWORDS_POLITICAL_PATH)
    fatal_categories = []
    for cat_key in ["geo_sensitive", "anti_china_narrative", "stigmatization"]:
        cat_data = political_kw.get(cat_key, {})
        if isinstance(cat_data, dict) and "keywords" in cat_data:
            fatal_categories.extend(cat_data["keywords"])
        elif isinstance(cat_data, list):
            fatal_categories.extend(cat_data)

    fatal_hits = [kw for kw in l2_risk_keywords
                  if kw.get("text", "") in fatal_categories]

    # Perspective API 深度分析 (对关键信号做二次确认)
    perspective_scores = {}
    for s in critical_signals[:5]:  # 最多分析5条
        text = s.get("text", "")
        # 提取上下文中的纯文本
        clean = text.split(": ", 1)[-1] if ": " in text else text
        clean = clean[:2000]  # API限制

        try:
            scores = await perspective_analyze(clean)
            if "error" not in scores:
                perspective_scores[clean[:50]] = scores
                log.append(f"[L3] Perspective API: TOXICITY={scores.get('TOXICITY', 0):.2f}")
        except Exception as e:
            log.append(f"[L3] Perspective API 调用失败: {e}")

    # 综合评分
    score = 100
    risk_tags = []
    signals = []

    if fatal_hits:
        # 致命红线命中 → 直接判定
        score = 0
        risk_tags.append({"text": "🚫 一票否决: 政治红线", "type": "critical"})
        for fh in fatal_hits:
            risk_tags.append({"text": f"检出: {fh.get('text', '')}", "type": "critical"})
        signals = critical_signals
    elif critical_signals:
        # 有关键信号但没有致命关键词, Perspective API 辅助判断
        max_toxicity = max(
            (s.get("TOXICITY", 0) for s in perspective_scores.values()),
            default=0,
        )
        if max_toxicity > 0.7:
            score = 20
            risk_tags.append({"text": f"Perspective TOXICITY={max_toxicity:.2f} (高)", "type": "critical"})
        elif max_toxicity > 0.5:
            score = 50
            risk_tags.append({"text": f"Perspective TOXICITY={max_toxicity:.2f} (中等)", "type": "warning"})
        else:
            score = 75
            risk_tags.append({"text": f"Perspective TOXICITY={max_toxicity:.2f} (低)", "type": "info"})
        signals = critical_signals + other_signals[:5]
    elif other_signals:
        score = 85
        risk_tags.append({"text": "低风险信号, 建议人工确认", "type": "info"})
        signals = other_signals[:10]
    else:
        risk_tags.append({"text": "政治安全 — 未检出敏感言论", "type": "info"})

    level = "low-risk" if score >= 70 else ("medium-risk" if score >= 40 else "high-risk")

    log.append(f"[L3] 完成 — 评分 {score}/100 — 等级 {level} — {len(signals)} 条信号")

    details = [
        {
            "section": "政治立场评估",
            "items": [
                {"label": "致命红线命中", "value": f"{len(fatal_hits)} 条", "cls": "bad" if fatal_hits else "good"},
                {"label": "关键信号", "value": f"{len(critical_signals)} 条", "cls": "bad" if critical_signals else "good"},
                {"label": "一般信号", "value": f"{len(other_signals)} 条", "cls": "warn" if other_signals else "good"},
                {"label": "Perspective API 确认", "value": f"{len(perspective_scores)} 条已分析", "cls": "good"},
            ],
        }
    ]

    return {
        "score": score,
        "level": level,
        "details": details,
        "signals": signals,
        "risk_keywords": risk_tags,
    }
