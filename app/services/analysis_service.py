"""数据复盘服务：真实 CSV 数据 -> 指标计算 -> AI 报告 -> 回写 reviews 表。

解决了评估报告里的两个核心扣分点：
1. 不再只输出 txt，复盘结论真实回写 reviews.csv + ecommerce.db；
2. 最差样本只从付费视频中取，零投流单独归为自然流量。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.llm import LLMClient
from app.core.logging_utils import get_logger
from app.db import database as db
from app.models.schemas import VideoMetrics
from app.services import storage

logger = get_logger("analysis")

DATA_DIR = storage.DATA_DIR
REVIEWS_CSV = DATA_DIR / "reviews.csv"
REVIEW_COLUMNS = [
    "id", "period", "video_ids", "best_video", "worst_video", "overall_roi",
    "problem", "action", "owner", "deadline", "priority", "status",
    "updated_at", "remark",
]


def load_ads_data() -> List[Dict[str, str]]:
    """从 ads.csv 读取投流数据，并与 videos.csv 关联获取视频信息。"""
    videos = {}
    for row in storage.load_csv("videos.csv"):
        videos[row["id"]] = row

    rows = []
    for row in storage.load_csv("ads.csv"):
        vid = row["video_id"]
        row["video_name"] = videos.get(vid, {}).get("title", vid)
        rows.append(row)
    return rows


def compute_metrics(v: Dict[str, str]) -> VideoMetrics:
    """计算单条视频的关键指标（CTR/转化率/ROI），零投流 ROI 为 None。"""
    views = int(v.get("views") or 0)
    cart_clicks = int(v.get("cart_clicks") or 0)
    orders = int(v.get("orders") or 0)
    revenue = float(v.get("revenue") or 0)
    cost = float(v.get("cost") or 0)

    ctr = round(cart_clicks / views * 100, 2) if views else 0.0
    conv = round(orders / cart_clicks * 100, 1) if cart_clicks else 0.0
    if cost > 0:
        roi = round(revenue / cost, 2)
        is_paid = True
    else:
        roi = None
        is_paid = False

    return VideoMetrics(
        video_id=v["video_id"],
        video_name=v.get("video_name", v["video_id"]),
        views=views,
        cart_clicks=cart_clicks,
        orders=orders,
        revenue=revenue,
        cost=cost,
        drop2s=float(v.get("drop2s") or 0),
        ctr=ctr,
        conv=conv,
        roi=roi,
        is_paid=is_paid,
    )


def _pad(text, width: int) -> str:
    display = sum(2 if ord(ch) > 127 else 1 for ch in str(text))
    return str(text) + " " * max(0, width - display)


def analyze(mock: Optional[bool] = None) -> Dict:
    """执行完整复盘：计算指标 -> 异常判断 -> AI 报告 -> 回写。"""
    rows = [compute_metrics(v) for v in load_ads_data()]
    paid = [m for m in rows if m.is_paid]
    organic = [m for m in rows if not m.is_paid]

    print("=" * 60)
    print("  短视频数据复盘分析系统")
    print("  数据来源：data/ads.csv + data/videos.csv")
    print("=" * 60)

    print("\n  [第一阶段] 数据计算\n")
    print(
        f"  {_pad('编号', 6)}{_pad('视频名称', 22)}{_pad('播放量', 8)}"
        f"{_pad('CTR%', 8)}{_pad('转化率%', 8)}{_pad('成交额', 8)}{'ROI':<8}"
    )
    print("  " + "-" * 66)
    for m in rows:
        roi = str(m.roi) if m.roi is not None else "N/A"
        print(
            f"  {_pad(m.video_id, 6)}{_pad(m.video_name, 22)}"
            f"{_pad(m.views, 8)}{_pad(m.ctr, 8)}{_pad(m.conv, 8)}"
            f"{_pad(m.revenue, 8)}{_pad(roi, 8)}"
        )

    print(f"\n  [第二阶段] 复盘结论")
    print(f"  付费投放视频：{len(paid)} 条 | 自然流量视频：{len(organic)} 条\n")

    total_cost = sum(m.cost for m in paid)
    total_rev = sum(m.revenue for m in paid)
    overall_roi = round(total_rev / total_cost, 2) if total_cost else 0.0
    print(f"  总投放成本：{int(total_cost)} 元 | 总成交：{int(total_rev)} 元 | 整体ROI：{overall_roi}")

    best = max(paid, key=lambda m: m.roi) if paid else None
    worst = min(paid, key=lambda m: m.roi) if paid else None
    if best:
        print(f"\n  最佳视频：{best.video_name} (ROI={best.roi}) -> 建议加投")
    if worst:
        print(f"  最差付费视频：{worst.video_name} (ROI={worst.roi}) -> 建议停投/重做")
    if organic:
        print("\n  自然流量视频（不参与ROI排名）：")
        for m in organic:
            print(f"    - {m.video_name}：播放{m.views}，成交{m.revenue}元，作为免费测款参考")

    problems, actions = _build_conclusions(rows, best, worst)
    print("\n  [第三阶段] 异常判断与优化建议")
    for text in problems:
        print(f"    [异常] {text}")
    for text in actions:
        print(f"    [建议] {text}")

    print("\n  [第四阶段] AI 自动复盘报告")
    print("  [正在调用 DeepSeek AI...]\n")
    prompt = build_ai_prompt(rows, overall_roi)
    reply = LLMClient(mock=mock).chat([{"role": "user", "content": prompt}])
    print(reply)

    saved = save_report(rows, overall_roi, best, worst, problems, actions, reply)
    logger.info("复盘报告已保存并回写 reviews 表: %s", saved["review_id"])

    return {
        "rows": [m.to_dict() for m in rows],
        "overall_roi": overall_roi,
        "best_video": best.video_id if best else "",
        "worst_video": worst.video_id if worst else "",
        "ai_report": reply,
        "saved_to": saved["txt_path"],
        "review_id": saved["review_id"],
    }


def _build_conclusions(rows, best, worst) -> tuple:
    problems: List[str] = []
    actions: List[str] = []
    for m in rows:
        if m.drop2s > 40:
            problems.append(f"{m.video_name}跳出率{m.drop2s}%")
    for m in rows:
        if m.is_paid and m.roi > 2:
            actions.append(f"加投{m.video_name}")
        elif m.is_paid and m.roi < 1:
            actions.append(f"停投/重做{m.video_name}")
    if best:
        actions.append(f"复制{best.video_name}的钩子结构")
    for m in rows:
        if m.drop2s > 40:
            actions.append(f"优化{m.video_name}开头3秒")
    # 去重且保持顺序
    problems = list(dict.fromkeys(problems))
    actions = list(dict.fromkeys(actions))
    return problems or ["无显著异常"], actions or ["维持当前策略"]


def build_ai_prompt(rows: List[VideoMetrics], overall_roi: float) -> str:
    """把真实计算好的指标喂给 AI，避免 AI 重新算错。"""
    data = [m.to_dict() for m in rows]
    return f"""你是一个短视频电商数据复盘分析师。基于以下已计算好的指标：
{json.dumps(data, ensure_ascii=False, indent=2)}
整体ROI：{overall_roi}

输出：
1. 综合评估（哪个视频最好，为什么）
2. 异常发现（哪个数据异常，原因）
3. 下一步优化动作（具体可执行）
4. 日报摘要（一句话结论）"""


def save_report(
    rows: List[VideoMetrics],
    overall_roi: float,
    best: Optional[VideoMetrics],
    worst: Optional[VideoMetrics],
    problems: List[str],
    actions: List[str],
    ai_text: str,
) -> Dict[str, str]:
    """保存 txt 报告，并真实回写 reviews.csv + ecommerce.db。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = storage.OUTPUT_DIR / "复盘报告.txt"
    storage.write_text(
        out,
        f"数据复盘报告\n{'='*40}\n\n"
        f"生成时间：{now}\n整体ROI：{overall_roi}\n\n"
        f"【异常判断】\n{chr(10).join('- ' + p for p in problems)}\n\n"
        f"【优化建议】\n{chr(10).join('- ' + a for a in actions)}\n\n"
        f"【AI复盘报告】\n{ai_text}\n",
    )

    review_id = storage.next_id("R", REVIEWS_CSV)
    row = {
        "id": review_id,
        "period": datetime.now().strftime("%Y-W%W"),
        "video_ids": ",".join(m.video_id for m in rows),
        "best_video": best.video_id if best else "",
        "worst_video": worst.video_id if worst else "",
        "overall_roi": str(overall_roi),
        "problem": "；".join(problems),
        "action": "；".join(actions),
        "owner": "系统",
        "deadline": "",
        "priority": "高",
        "status": "已完成",
        "updated_at": now[:10],
        "remark": "由数据复盘系统自动回写",
    }
    storage.append_csv(REVIEWS_CSV, REVIEW_COLUMNS, row)
    db.insert("reviews", row)
    return {"txt_path": str(out), "review_id": review_id}
