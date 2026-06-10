"""
筛查核心引擎: 编排六层筛查流程
"""
import json
from datetime import datetime
from services.utils import detect_platform
from services.layer1_authenticity import run_layer1
from services.layer2_content import run_layer2
from services.layer3_political import run_layer3
from services.layers_456 import run_layer4, run_layer5, run_layer6
from services.progress_store import update_progress


async def run_full_screening(url: str, db_conn, screen_id: str, creator_id: str,
                              date_from: str | None = None,
                              date_to: str | None = None) -> dict:
    """
    执行完整的六层筛查, 实时更新数据库状态
    返回: {success, screen_result, layers, creator}
    """
    log = []
    platform = detect_platform(url)

    # 更新数据库状态 → running
    _update_status(db_conn, screen_id, "running", started_at=datetime.now())
    update_progress(screen_id, status="running", log=["[引擎] 启动筛查流程..."])

    try:
        # ── L1: 基础数据真实性 ──
        update_progress(screen_id, current_step=1, step_name="基础数据真实性验证",
                        detail="正在获取频道数据并验证粉丝真实性...", log=log.copy())
        l1 = await run_layer1(url, platform, log)
        _save_layer(db_conn, screen_id, 1, "基础数据真实性验证", l1, "\n".join(log[-5:]))
        update_progress(screen_id, current_step=1, step_name="基础数据真实性验证",
                        detail="✓ 完成", log=log.copy())

        # 提取 L1 的创作者信息
        creator_name = l1.get("creator_name", "")
        creator_handle = l1.get("creator_handle", "")
        creator_subs = l1.get("creator_subs", 0)
        creator_country = l1.get("creator_country", "")
        creator_avatar = l1.get("creator_avatar", "")

        # 更新创作者信息
        db_conn.execute(
            "UPDATE creators SET name=?, handle=?, subs=?, country=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (creator_name, creator_handle, creator_subs, creator_country, creator_id),
        )

        # ── L2: 内容历史全量回溯 ──
        update_progress(screen_id, current_step=2, step_name="内容历史全量回溯",
                        detail="正在获取视频列表并下载字幕...", log=log.copy())
        l2 = await run_layer2(url, platform, log, date_from, date_to)
        _save_layer(db_conn, screen_id, 2, "内容历史全量回溯", l2, "\n".join(log[-8:]))
        update_progress(screen_id, current_step=2, step_name="内容历史全量回溯",
                        detail="✓ 完成", log=log.copy())

        # 提取宝可梦占比供 L5 使用（从竞品关键词匹配中计算）
        update_progress(screen_id, current_step=2, step_name="内容历史全量回溯",
                        detail="正在分析竞品关键词占比...", log=log.copy())
        poke_ratio = 0
        for d in l2.get("details", []):
            for item in d.get("items", []):
                if "宝可梦" in item.get("label", ""):
                    try:
                        poke_ratio = float(item["value"].replace("%", ""))
                    except (ValueError, KeyError):
                        poke_ratio = 0
        # 如果 L2 details 中没有"宝可梦"指标，从风险关键词中推算
        if poke_ratio == 0:
            l2_kws = l2.get("risk_keywords", [])
            pokemon_kws = [kw for kw in l2_kws if any(p in kw.get("text", "").lower() for p in ["pokemon", "pokémon", "poké", "宝可梦"])]
            total_competitor_kws = len([kw for kw in l2_kws if kw.get("type") == "info"])
            if total_competitor_kws > 0:
                poke_ratio = len(pokemon_kws) / total_competitor_kws * 100
            # 如果有宝可梦关键词但占比推算为0，至少设为1%表示有命中
            if poke_ratio == 0 and pokemon_kws:
                poke_ratio = 10

        # ── L3: 政治敏感信号检测 ──
        update_progress(screen_id, current_step=3, step_name="政治敏感信号检测",
                        detail="正在扫描政治敏感关键词...", log=log.copy())
        l3 = await run_layer3(
            l2.get("signals", []),
            l2.get("risk_keywords", []),
            log,
        )
        _save_layer(db_conn, screen_id, 3, "政治敏感信号检测", l3, "\n".join(log[-5:]))
        update_progress(screen_id, current_step=3, step_name="政治敏感信号检测",
                        detail="✓ 完成", log=log.copy())

        # ── L4: 品牌安全 ──
        update_progress(screen_id, current_step=4, step_name="品牌安全综合评分",
                        detail="正在评估内容分级与品牌关联...", log=log.copy())
        l4 = await run_layer4(l3, log)
        _save_layer(db_conn, screen_id, 4, "品牌安全综合评分", l4, "\n".join(log[-3:]))
        update_progress(screen_id, current_step=4, step_name="品牌安全综合评分",
                        detail="✓ 完成", log=log.copy())

        # ── L5: 竞争关系 ──
        update_progress(screen_id, current_step=5, step_name="竞争关系图谱分析",
                        detail="正在分析竞品绑定度与受众兼容性...", log=log.copy())
        l5 = await run_layer5(poke_ratio, log)
        _save_layer(db_conn, screen_id, 5, "竞争关系图谱分析", l5, "\n".join(log[-3:]))
        update_progress(screen_id, current_step=5, step_name="竞争关系图谱分析",
                        detail="✓ 完成", log=log.copy())

        # ── L6: 影响力 ──
        update_progress(screen_id, current_step=6, step_name="影响力真实性验证",
                        detail="正在验证粉丝真实性与影响力指标...", log=log.copy())
        l6 = await run_layer6(l1, log)
        _save_layer(db_conn, screen_id, 6, "影响力真实性验证", l6, "\n".join(log[-3:]))
        update_progress(screen_id, current_step=6, step_name="影响力真实性验证",
                        detail="✓ 完成", log=log.copy())

        # ── 综合评分 ──
        update_progress(screen_id, current_step=7, step_name="综合评分",
                        detail="正在计算加权评分与一票否决判定...", log=log.copy())
        weights = {1: 0.10, 2: 0.25, 3: 0.25, 4: 0.15, 5: 0.15, 6: 0.10}
        layers_map = {1: l1, 2: l2, 3: l3, 4: l4, 5: l5, 6: l6}
        composite = sum(
            weights[i] * layers_map[i].get("score", 50) for i in range(1, 7)
        )
        composite = round(composite, 1)

        # ── 判定 + 一票否决 ──
        veto_flags = _check_veto(l3, l2, l5)
        if veto_flags:
            verdict = "reject"
        elif composite >= 80:
            verdict = "approve"
        elif composite >= 60:
            verdict = "review"
        else:
            verdict = "reject"

        # 更新数据库 → completed
        db_conn.execute(
            "UPDATE screen_results SET status='completed', composite_score=?, verdict=?, "
            "veto_flags=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
            (composite, verdict, json.dumps(veto_flags, ensure_ascii=False), screen_id),
        )
        db_conn.commit()

        log.append(f"[DONE] 综合评分 {composite}/100 — 判定: {verdict}")

        update_progress(screen_id, status="completed", current_step=8, step_name="完成",
                        detail=f"综合评分 {composite}/100 · 判定: {verdict}",
                        log=log.copy())

        # 构建返回
        from models import ScreenResponse, CreatorInfo, LayerResultData, FullScreenResult

        cursor = db_conn.execute("SELECT * FROM screen_results WHERE id=?", (screen_id,))
        sr = dict(cursor.fetchone())

        cursor = db_conn.execute("SELECT * FROM creators WHERE id=?", (creator_id,))
        cr = dict(cursor.fetchone())

        cursor = db_conn.execute(
            "SELECT * FROM layer_results WHERE screen_result_id=? ORDER BY layer_number",
            (screen_id,),
        )
        layers = [_layer_row_to_dict(row) for row in cursor.fetchall()]

        return {
            "success": True,
            "result": {
                "id": sr["id"],
                "creator_id": sr["creator_id"],
                "status": sr["status"],
                "composite_score": sr["composite_score"],
                "verdict": sr["verdict"],
                "veto_flags": json.loads(sr["veto_flags"]) if sr["veto_flags"] else [],
            },
            "creator": {
                "id": cr["id"],
                "platform": cr["platform"],
                "url": cr["url"],
                "name": cr["name"],
                "handle": cr["handle"],
                "subs": cr["subs"],
                "country": cr["country"],
                "content_lang": cr["content_lang"],
                "category": cr["category"],
                "avatar_url": cr.get("avatar_url", ""),
            },
            "layers": layers,
            "log": log,
        }

    except Exception as e:
        log.append(f"[ERROR] {e}")
        update_progress(screen_id, status="failed", current_step=-1,
                        step_name="出错", detail=str(e), log=log.copy())
        db_conn.execute(
            "UPDATE screen_results SET status='failed', error_message=? WHERE id=?",
            (str(e), screen_id),
        )
        db_conn.commit()
        return {"success": False, "error": str(e), "log": log}


def _check_veto(l3: dict, l2: dict, l5: dict) -> list[dict]:
    """检查一票否决条件"""
    flags = []

    # 政治红线
    if l3.get("score", 100) <= 20:
        for kw in l3.get("risk_keywords", []):
            if "一票否决" in kw.get("text", "") or "critical" == kw.get("type", ""):
                flags.append({"icon": "🚫", "text": f"【致命-政治红线】{kw.get('text', '')}"})

    # 反华/种族歧视
    for kw in l2.get("risk_keywords", []):
        text = kw.get("text", "")
        if kw.get("type") == "critical" and any(
            w in text.lower() for w in ["china", "chinese", "wuhan", "virus", "trash from"]
        ):
            flags.append({"icon": "🚫", "text": f"【致命-反华歧视】{text}"})

    # 宝可梦极端忠诚度 (占用 > 80%)
    if l5.get("score", 100) <= 15:
        flags.append({"icon": "⚠️", "text": "【高风险】宝可梦内容占比 > 80%, 粉丝基本盘严重冲突"})

    return flags


def _save_layer(db_conn, screen_id: str, num: int, name: str, data: dict, log_text: str):
    """保存单层结果到数据库"""
    import uuid

    db_conn.execute(
        "INSERT INTO layer_results (id, screen_result_id, layer_number, layer_name, "
        "score, level, details, signals, risk_keywords, log_output) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            uuid.uuid4().hex[:12],
            screen_id,
            num,
            name,
            data.get("score"),
            data.get("level"),
            json.dumps(data.get("details", []), ensure_ascii=False),
            json.dumps(data.get("signals", []), ensure_ascii=False),
            json.dumps(data.get("risk_keywords", []), ensure_ascii=False),
            log_text,
        ),
    )


def _update_status(db_conn, screen_id: str, status: str, **kwargs):
    """更新筛查状态"""
    set_clause = "status=?"
    params = [status]
    if "started_at" in kwargs:
        set_clause += ", started_at=CURRENT_TIMESTAMP"
    db_conn.execute(
        f"UPDATE screen_results SET {set_clause} WHERE id=?", (*params, screen_id)
    )
    db_conn.commit()


def _layer_row_to_dict(row) -> dict:
    """将数据库行转为字典"""
    d = dict(row)
    for field in ("details", "signals", "risk_keywords"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        else:
            d[field] = []
    return d
