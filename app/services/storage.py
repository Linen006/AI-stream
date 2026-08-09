"""CSV 与文件存储工具：商品读取、编号生成、回写追加、文本保存。"""
import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"


def load_csv(filename: str) -> List[Dict[str, str]]:
    """读取 data/ 下的 CSV 文件，返回字典列表。"""
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def append_csv(
    csv_path: Path, columns: List[str], row: Dict[str, str]
) -> None:
    """向 CSV 追加一行，文件不存在时自动写表头。"""
    exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not exists or os.path.getsize(csv_path) == 0:
            writer.writeheader()
        writer.writerow({c: row.get(c, "") for c in columns})


def next_id(prefix: str, csv_path: Path) -> str:
    """生成下一个业务编号，如 S006、R002。"""
    max_num = 0
    if csv_path.exists():
        with open(csv_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                m = re.match(rf"{prefix}(\d+)", row.get("id", ""))
                if m:
                    max_num = max(max_num, int(m.group(1)))
    return f"{prefix}{max_num + 1:03d}"


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
