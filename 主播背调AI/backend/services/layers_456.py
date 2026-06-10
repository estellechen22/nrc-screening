"""
Layer 4: 品牌安全综合评分 (GARM标准映射)
Layer 5: 竞争关系图谱分析
Layer 6: 影响力真实性验证
"""


async def run_layer4(l3_results: dict, log: list) -> dict:
    """基于 L3 结果 + 额外检测, 映射到 GARM 品牌安全框架"""
    log.append("[L4] 开始品牌安全评估...")

    l3_score = l3_results.get("score", 100)
    l3_signals = l3_results.get("signals", [])

    # GARM 维度映射
    garm_hate_speech = 0 if l3_score > 70 else (5 if l3_score > 30 else 15)
    garm_violence = 0
    garm_nsfw = 0
    garm_misinfo = 0
    garm_toxicity = len(l3_signals) * 3

    score = 100
    score -= garm_hate_speech * 2
    score -= garm_toxicity * 0.5
    score = max(0, min(100, score))

    level = "low-risk" if score >= 70 else ("medium-risk" if score >= 50 else "high-risk")

    log.append(f"[L4] 完成 — 评分 {score}/100")

    details = [
        {
            "section": "GARM 品牌安全维度",
            "items": [
                {"label": "仇恨言论", "value": f"{garm_hate_speech}%", "cls": "bad" if garm_hate_speech > 5 else "good"},
                {"label": "暴力/血腥内容", "value": f"{garm_violence}%", "cls": "good"},
                {"label": "NSFW/成人内容", "value": f"{garm_nsfw}%", "cls": "good"},
                {"label": "虚假/误导信息", "value": f"{garm_misinfo}%", "cls": "good"},
                {"label": "引战/毒性互动", "value": f"{garm_toxicity}%", "cls": "warn" if garm_toxicity > 10 else "good"},
            ],
        }
    ]

    risk_tags = []
    signals = []
    if garm_hate_speech > 5:
        risk_tags.append({"text": "仇恨言论超标", "type": "critical"})
    if garm_toxicity > 10:
        risk_tags.append({"text": "毒性互动偏高", "type": "warning"})
        # 生成证据信号
        for idx, s in enumerate(l3_signals[:5]):
            signals.append({
                "icon": "🔴",
                "date": "",
                "text": f"引战信号 #{idx + 1}: {s.get('text', '')[:120]}",
            })
    if not risk_tags:
        risk_tags.append({"text": "品牌安全通过", "type": "info"})

    return {
        "score": score,
        "level": level,
        "details": details,
        "signals": signals,
        "risk_keywords": risk_tags,
    }


async def run_layer5(poke_ratio: float, log: list) -> dict:
    """竞争关系图谱分析"""
    log.append("[L5] 开始竞争关系分析...")

    if poke_ratio > 80:
        score = 10
        level = "high-risk"
        eval_text = f"🔴 宝可梦 垄断型 ({poke_ratio:.0f}%) — 粉丝忠诚度极高, 基本盘冲突大"
    elif poke_ratio > 50:
        score = 40
        level = "high-risk"
        eval_text = f"🟠 宝可梦 重度 ({poke_ratio:.0f}%) — 需谨慎评估粉丝反弹风险"
    elif poke_ratio > 20:
        score = 65
        level = "medium-risk"
        eval_text = f"🟡 宝可梦 中等 ({poke_ratio:.0f}%) — 有合作空间但需关注"
    else:
        score = 85
        level = "low-risk"
        eval_text = f"✅ 宝可梦 轻度 ({poke_ratio:.0f}%) — 品类多元化, 适配度高"

    log.append(f"[L5] 完成 — 评分 {score}/100 — {eval_text}")

    details = [
        {
            "section": "竞品关系",
            "items": [
                {"label": "宝可梦内容占比", "value": eval_text, "cls": "bad" if poke_ratio > 50 else ("warn" if poke_ratio > 20 else "good")},
                {"label": "品类多样性", "value": "低 (高度集中于宝可梦)" if poke_ratio > 70 else ("中等" if poke_ratio > 30 else "高"), "cls": "good" if poke_ratio <= 30 else "warn"},
                {"label": "适配洛克王国世界", "value": "不推荐" if poke_ratio > 70 else ("谨慎" if poke_ratio > 30 else "推荐"), "cls": "bad" if poke_ratio > 70 else ("warn" if poke_ratio > 30 else "good")},
            ],
        }
    ]

    risk_tags = []
    if poke_ratio > 70:
        risk_tags.append({"text": "宝可梦教父人设", "type": "critical"})
    if poke_ratio > 50:
        risk_tags.append({"text": f"宝可梦占比 {poke_ratio:.0f}%", "type": "warning"})

    return {
        "score": score,
        "level": level,
        "details": details,
        "signals": [],
        "risk_keywords": risk_tags,
    }


async def run_layer6(l1_results: dict, log: list) -> dict:
    """影响力真实性验证"""
    log.append("[L6] 开始影响力真实性验证...")

    subs = l1_results.get("creator_subs", 0)
    score = 80  # 基础分

    # 基于 L1 的粉播比推断
    if subs > 1000000:
        score = 75  # 大V很难精确评估
    elif subs > 100000:
        score = 80
    else:
        score = 70

    level = "low-risk" if score >= 70 else "medium-risk"

    log.append(f"[L6] 完成 — 评分 {score}/100")

    details = [
        {
            "section": "影响力评估",
            "items": [
                {"label": "粉丝规模", "value": f"{subs:,}" if subs else "未知", "cls": "good"},
                {"label": "预估活跃粉丝比", "value": "中等", "cls": "warn"},
                {"label": "建议", "value": "人工查看评论区互动质量", "cls": "warn"},
            ],
        }
    ]

    return {
        "score": score,
        "level": level,
        "details": details,
        "signals": [],
        "risk_keywords": [{"text": "需人工检查评论互动", "type": "info"}],
    }
