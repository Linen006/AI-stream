"""初始化 SQLite 数据库：从 data/*.csv 导入 8 张关联表。"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import database as db

FILE_MAP = {
    "products": "products.csv",
    "contents": "contents.csv",
    "scripts": "scripts.csv",
    "videos": "videos.csv",
    "ads": "ads.csv",
    "leads": "leads.csv",
    "reviews": "reviews.csv",
    "knowledge_base": "knowledge_base.csv",
}


def main() -> None:
    path = db.get_db_path()
    if path.exists():
        path.unlink()
    db.ensure_db()

    total = 0
    for table, filename in FILE_MAP.items():
        csv_path = db.ROOT_DIR / "data" / filename
        with open(csv_path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if rows:
            db.insert_many(table, rows)
            total += len(rows)
        print(f"  [OK] {table}: {len(rows)} 条")

    print(f"\n数据库初始化完成: {path} (共 {total} 条记录)")


if __name__ == "__main__":
    main()
