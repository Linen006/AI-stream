"""AI 工作流服务：商品 -> 卖点 -> 内容角度 -> 脚本分镜 -> 质检 -> 真实回写。

设计参考 MoneyPrinterTurbo 的控制器/服务分层：CLI 与 Web 共用同一套服务，
每步输出落盘，最后把内容拆解与脚本回写进 CSV 和 SQLite。
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.llm import LLMClient
from app.core.logging_utils import get_logger
from app.db import database as db
from app.services import storage

logger = get_logger("workflow")

PRODUCTS_CSV = storage.DATA_DIR / "products.csv"
SCRIPTS_CSV = storage.DATA_DIR / "scripts.csv"
CONTENTS_CSV = storage.DATA_DIR / "contents.csv"

PRODUCT_COLUMNS = [
    "id", "name", "category", "price", "commission_pct", "heat_score",
    "target_audience", "selling_points", "status", "owner", "priority",
    "updated_at", "remark",
]
SCRIPT_COLUMNS = [
    "id", "title", "product_id", "content_id", "duration_sec", "shot_table",
    "review_status", "owner", "priority", "updated_at", "remark",
]
CONTENT_COLUMNS = [
    "id", "title", "hook", "target_audience", "structure",
    "conversion_point", "product_id", "status", "owner", "priority",
    "updated_at", "remark",
]


def load_products() -> List[Dict[str, str]]:
    """从商品库读取全部商品。"""
    return storage.load_csv("products.csv")


def find_product(product_id: str) -> Optional[Dict[str, str]]:
    for product in load_products():
        if product["id"] == product_id:
            return product
    return None


def next_id(prefix: str, csv_path: Path) -> str:
    """兼容旧测试：生成下一个业务编号。"""
    return storage.next_id(prefix, csv_path)


def append_csv(csv_path: Path, columns: List[str], row: Dict[str, str]) -> None:
    """兼容旧测试：向 CSV 追加一行。"""
    storage.append_csv(csv_path, columns, row)


def save_step(folder: Path, title: str, content: str) -> Path:
    """保存单步生成结果到工作流目录。"""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{title}.txt"
    path.write_text(f"{title}\n{'='*40}\n\n{content}", encoding="utf-8")
    print(f"  [OK] 已保存: {path.name}")
    return path


def _ask(
    llm: LLMClient,
    label: str,
    prompt: str,
    temperature: float,
    auto_approve: bool,
) -> str:
    """执行一步 AI 生成；auto_approve=False 时保留人工审核停顿。"""
    print(f"\n  [步骤] {label}")
    print("  [AI生成中...]")
    content = llm.chat([{"role": "user", "content": prompt}], temperature=temperature)
    print(content)
    if not auto_approve:
        input("  [人工审核] 确认无误按 Enter 继续...")
    return content


def run_workflow(
    product: Dict[str, str],
    auto_approve: bool = True,
    mock: Optional[bool] = None,
) -> Dict:
    """对单个商品执行完整工作流，并把结果真实回写数据表。"""
    llm = LLMClient(mock=mock)
    name = product["name"]
    out_dir = storage.OUTPUT_DIR / f"{storage.now_stamp()}_{storage.safe_name(name)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    steps: List[Dict] = []

    print(f"\n  【已选择】{name}（{product['price']}）")

    # 步骤1：卖点分析
    p1 = (
        f"你是短视频电商选品分析师。分析商品：{name}，价格{product['price']}，"
        f"目标用户{product['target_audience']}，卖点{product['selling_points']}。"
        "输出：【三大核心卖点+呈现方式】【三类目标人群+痛点需求】【三条内容禁忌】"
    )
    r1 = _ask(llm, "01_卖点分析", p1, 0.7, auto_approve)
    steps.append({"step": 1, "title": "卖点分析", "content": r1, "file": str(save_step(out_dir, "01_卖点分析", r1))})

    # 步骤2：内容角度
    p2 = (
        f"基于商品{name}（卖点：{product['selling_points']}，人群：{product['target_audience']}），"
        "生成3个短视频内容角度。每个含：名称、人群、前3秒钩子、结构、时长、转化方式。用---分隔。"
    )
    r2 = _ask(llm, "02_内容角度", p2, 0.7, auto_approve)
    steps.append({"step": 2, "title": "内容角度", "content": r2, "file": str(save_step(out_dir, "02_内容角度", r2))})

    # 步骤3：脚本分镜
    p3 = (
        f"创作30秒短视频脚本。\n商品：{name}（{product['price']}）\n"
        f"卖点：{product['selling_points']}\n人群：{product['target_audience']}\n\n"
        "输出：\n【脚本分镜表】时间|画面|旁白|字幕|镜头\n"
        "【AI画面提示词】3条\n【剪辑要点】3-5条\n【发布标题】3个"
    )
    r3 = _ask(llm, "03_脚本分镜", p3, 0.8, auto_approve)
    steps.append({"step": 3, "title": "脚本分镜", "content": r3, "file": str(save_step(out_dir, "03_脚本分镜", r3))})

    # 步骤4：质检与发布标题
    p4 = (
        f"基于商品{name}输出：\n1.【发布标题】3个\n"
        "2.【质检清单】发布前检查表\n3.【AI提示词】3条文生视频画面描述"
    )
    r4 = _ask(llm, "04_质检发布", p4, 0.7, auto_approve)
    steps.append({"step": 4, "title": "质检发布", "content": r4, "file": str(save_step(out_dir, "04_质检发布", r4))})

    # 真实回写：内容拆解表 + 脚本分镜表（CSV 与 SQLite 双写）
    print("\n  [回写数据表] 正在写入 contents / scripts ...")
    script_id = storage.next_id("S", SCRIPTS_CSV)
    content_id = storage.next_id("C", CONTENTS_CSV)
    today = datetime.now().strftime("%Y-%m-%d")

    content_row = {
        "id": content_id,
        "title": f"{name}内容角度",
        "hook": "见AI生成结果",
        "target_audience": product["target_audience"],
        "structure": "AI自动生成",
        "conversion_point": "购物车点击",
        "product_id": product["id"],
        "status": "已完成",
        "owner": "系统",
        "priority": "中",
        "updated_at": today,
        "remark": "由AI工作流自动生成",
    }
    script_row = {
        "id": script_id,
        "title": f"{name}脚本",
        "product_id": product["id"],
        "content_id": content_id,
        "duration_sec": "30",
        "shot_table": r3[:200],
        "review_status": "已审核",
        "owner": "系统",
        "priority": "高",
        "updated_at": today,
        "remark": "由AI工作流真实回写",
    }
    storage.append_csv(CONTENTS_CSV, CONTENT_COLUMNS, content_row)
    storage.append_csv(SCRIPTS_CSV, SCRIPT_COLUMNS, script_row)
    db.insert("contents", content_row)
    db.insert("scripts", script_row)
    print(f"  [OK] 内容拆解表: {content_id} -> 关联 {product['id']}")
    print(f"  [OK] 脚本分镜表: {script_id} -> 关联 {product['id']} + {content_id}")

    result = {
        "product_id": product["id"],
        "product_name": name,
        "script_id": script_id,
        "content_id": content_id,
        "output_dir": str(out_dir),
        "steps": steps,
    }
    print(f"\n  [完成] 工作流输出保存在: {out_dir}")
    return result
