"""脚本生成助手服务：输入商品名 -> AI 分析 -> 生成脚本 -> 结构化校验 -> 保存回写。"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.core.llm import LLMClient
from app.core.logging_utils import get_logger
from app.db import database as db
from app.services import storage
from app.services.knowledge_service import get_prompt
from app.services.workflow_service import PRODUCT_COLUMNS, PRODUCTS_CSV

logger = get_logger("agent")

AGENT_OUTPUT_DIR = storage.OUTPUT_DIR / "agent_output"
SCRIPTS_CSV = storage.DATA_DIR / "scripts.csv"
SCRIPT_COLUMNS = [
    "id", "title", "product_id", "content_id", "duration_sec", "shot_table",
    "review_status", "owner", "priority", "updated_at", "remark",
]


def validate_input(name: str) -> str:
    """输入校验：商品名称不能为空、长度限制。"""
    if not name or not name.strip():
        raise ValueError("商品名称不能为空")
    if len(name) > 50:
        raise ValueError("商品名称过长（最多50字）")
    return name.strip()


def load_prompt(key: str) -> Optional[str]:
    """兼容旧接口：从知识库加载提示词。"""
    return get_prompt(key)


def validate_output(text: str) -> bool:
    """结构化校验：必须包含4个关键部分，缺失则重试。"""
    required = ["脚本分镜", "AI画面提示词", "剪辑要点", "发布标题"]
    missing = [k for k in required if k not in text]
    if missing:
        print(f"  [!] 输出缺少: {missing}，尝试重新生成...")
        return False
    return True


def ai_analyze_product(name: str, mock: Optional[bool] = None) -> str:
    """AI 自动分析商品的人群/场景/卖点/痛点。"""
    prompt = (
        f"你是一个短视频电商选品分析师。基于商品名称\"{name}\"，分析并输出：\n"
        "1. 目标人群：这类商品主要卖给谁？\n"
        "2. 使用场景：用户在什么场景下使用？\n"
        "3. 核心卖点：核心卖点有哪些？\n"
        "4. 用户痛点：解决了什么痛点？\n"
        "要求：贴合商品实际，简明扼要。"
    )
    return LLMClient(mock=mock).chat(
        [{"role": "user", "content": prompt}], temperature=0.7
    )


def generate_script(
    name: str,
    audience: str,
    scenario: str,
    sell: str,
    mock: Optional[bool] = None,
) -> str:
    """生成完整短视频脚本，缺失关键部分时自动重试一次。"""
    system_prompt = get_prompt("script_generation")
    if not system_prompt:
        system_prompt = (
            "你是一个专业的短视频脚本创作专家。你的职责：接收商品信息，"
            "分析卖点和人群，创作30-40秒短视频脚本。输出必须包含："
            "【脚本分镜表】| 时间 | 画面描述 | 旁白 | 字幕 | 镜头运动；"
            "【AI画面提示词】3条；【剪辑要点】3-5条；【发布标题】3个。"
            "知识库规则：完播率黄金3秒法则、电商转化结构（痛点->方案->展示->号召）、"
            "合规规则（禁止医疗功效、绝对化用语）。"
        )
    user_prompt = (
        f"商品名称：{name}\n目标人群：{audience}\n"
        f"使用场景：{scenario}\n核心卖点：{sell}\n\n请生成完整短视频脚本（30-40秒）"
    )
    llm = LLMClient(mock=mock)
    for _attempt in range(2):
        result = llm.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
        )
        if validate_output(result):
            return result
    raise RuntimeError("AI 输出多次缺少关键部分，请重试")


def run_agent(
    name: str,
    audience: Optional[str] = None,
    scenario: Optional[str] = None,
    sell: Optional[str] = None,
    mock: Optional[bool] = None,
) -> Dict:
    """完整智能体流程：分析 -> 生成 -> 校验 -> 保存 -> 回写数据表。"""
    name = validate_input(name)
    suggestion = ai_analyze_product(name, mock=mock)
    audience = audience or "(AI自动分析)"
    scenario = scenario or "(AI自动分析)"
    sell = sell or "(AI自动分析)"

    result = generate_script(name, audience, scenario, sell, mock=mock)
    saved = save_script_result(name, audience, scenario, sell, result, suggestion)
    logger.info("脚本助手回写 %s -> scripts.csv + ecommerce.db", saved["script_id"])

    return {
        "product_name": name,
        "suggestion": suggestion,
        "result": result,
        "script_id": saved["script_id"],
        "saved_to": saved["saved_to"],
    }


def save_script_result(
    name: str,
    audience: str,
    scenario: str,
    sell: str,
    result: str,
    suggestion: str = "",
) -> Dict:
    """保存脚本结果并回写 scripts.csv + SQLite，供 CLI 与 Web 共用。"""
    product_id = _ensure_product(name, audience, sell)
    AGENT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = AGENT_OUTPUT_DIR / f"{ts}_{storage.safe_name(name)}.txt"
    analysis_block = f"【AI商品分析】\n{suggestion}\n\n" if suggestion else ""
    storage.write_text(
        out,
        f"智能体名称：脚本生成助手 v2.0\n生成时间：{datetime.now()}\n"
        f"\n【输入】\n商品名称：{name}\n"
        f"目标人群：{audience}\n使用场景：{scenario}\n核心卖点：{sell}\n\n"
        f"{analysis_block}【智能体输出】\n{result}",
    )

    # 回写脚本表（CSV + SQLite 双写，形成真实数据闭环）
    script_id = storage.next_id("S", SCRIPTS_CSV)
    script_row = {
        "id": script_id,
        "title": f"{name}脚本(AI助手)",
        "product_id": product_id,
        "content_id": "",
        "duration_sec": "30",
        "shot_table": result[:200],
        "review_status": "待审核",
        "owner": "系统",
        "priority": "中",
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "remark": "由脚本生成助手生成",
    }
    storage.append_csv(SCRIPTS_CSV, SCRIPT_COLUMNS, script_row)
    # SQLite 外键：未关联内容拆解时 content_id 必须为 NULL，而不是空字符串
    db.insert("scripts", {**script_row, "content_id": None})
    return {"script_id": script_id, "saved_to": str(out)}


def _ensure_product(name: str, audience: str, sell: str) -> str:
    """商品不在库中时自动入库，保证外键闭环（对应开源项目的商品注册表）。"""
    for p in storage.load_csv("products.csv"):
        if p["name"] == name:
            return p["id"]

    product_id = storage.next_id("P", PRODUCTS_CSV)
    today = datetime.now().strftime("%Y-%m-%d")
    row = {
        "id": product_id,
        "name": name,
        "category": "AI助手录入",
        "price": "待定",
        "commission_pct": "",
        "heat_score": "0",
        "target_audience": audience if audience != "(AI自动分析)" else "",
        "selling_points": sell if sell != "(AI自动分析)" else "",
        "status": "待评估",
        "owner": "系统",
        "priority": "中",
        "updated_at": today,
        "remark": "由脚本生成助手自动入库",
    }
    storage.append_csv(PRODUCTS_CSV, PRODUCT_COLUMNS, row)
    db.insert("products", row)
    logger.info("新商品自动入库: %s (%s)", name, product_id)
    return product_id
