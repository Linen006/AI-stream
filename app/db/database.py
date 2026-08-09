"""SQLite 访问层：统一建表、查询、写入，实现 CSV 与数据库的数据闭环。

设计参考 TikTok Viral Factory：数据模型集中管理，服务层只调用统一接口。
"""
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "ecommerce.db"

# 与 scripts/init_db.py 保持一致：8 张业务表 + 外键关联
SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    price TEXT,
    commission_pct TEXT,
    heat_score TEXT,
    target_audience TEXT,
    selling_points TEXT,
    status TEXT,
    owner TEXT,
    priority TEXT,
    updated_at TEXT,
    remark TEXT
);

CREATE TABLE IF NOT EXISTS contents (
    id TEXT PRIMARY KEY,
    title TEXT,
    hook TEXT,
    target_audience TEXT,
    structure TEXT,
    conversion_point TEXT,
    product_id TEXT,
    status TEXT,
    owner TEXT,
    priority TEXT,
    updated_at TEXT,
    remark TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS scripts (
    id TEXT PRIMARY KEY,
    title TEXT,
    product_id TEXT,
    content_id TEXT,
    duration_sec TEXT,
    shot_table TEXT,
    review_status TEXT,
    owner TEXT,
    priority TEXT,
    updated_at TEXT,
    remark TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (content_id) REFERENCES contents(id)
);

CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    title TEXT,
    script_id TEXT,
    material_status TEXT,
    tool TEXT,
    editor TEXT,
    qa_status TEXT,
    publish_time TEXT,
    platform TEXT,
    status TEXT,
    priority TEXT,
    updated_at TEXT,
    remark TEXT,
    FOREIGN KEY (script_id) REFERENCES scripts(id)
);

CREATE TABLE IF NOT EXISTS ads (
    video_id TEXT PRIMARY KEY,
    plan_name TEXT,
    cost REAL,
    views INTEGER,
    drop2s REAL,
    cart_clicks INTEGER,
    orders INTEGER,
    revenue REAL,
    roi TEXT,
    abnormal_flag TEXT,
    advice TEXT,
    owner TEXT,
    priority TEXT,
    status TEXT,
    updated_at TEXT,
    remark TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    video_id TEXT,
    question TEXT,
    intent TEXT,
    status TEXT,
    wechat_status TEXT,
    template TEXT,
    next_followup TEXT,
    owner TEXT,
    priority TEXT,
    updated_at TEXT,
    remark TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    period TEXT,
    video_ids TEXT,
    best_video TEXT,
    worst_video TEXT,
    overall_roi TEXT,
    problem TEXT,
    action TEXT,
    owner TEXT,
    deadline TEXT,
    priority TEXT,
    status TEXT,
    updated_at TEXT,
    remark TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id TEXT PRIMARY KEY,
    name TEXT,
    category TEXT,
    scenario TEXT,
    summary TEXT,
    prompt_key TEXT,
    version TEXT,
    effect TEXT,
    owner TEXT,
    priority TEXT,
    status TEXT,
    updated_at TEXT,
    remark TEXT
);
"""

_DB_PATH = DB_PATH


def set_db_path(path: Path) -> None:
    """测试用：切换到临时数据库。"""
    global _DB_PATH
    _DB_PATH = Path(path)


def get_db_path() -> Path:
    return _DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_db() -> None:
    """幂等建表：不存在才创建，可安全重复调用。"""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def insert(table: str, data: Dict[str, Any]) -> None:
    """插入或替换一行，字段名动态生成，避免手写重复 SQL。"""
    columns = list(data.keys())
    sql = (
        f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) "
        f"VALUES ({','.join('?' * len(columns))})"
    )
    conn = get_conn()
    try:
        conn.execute(sql, [data[c] for c in columns])
        conn.commit()
    finally:
        conn.close()


def insert_many(table: str, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    columns = list(rows[0].keys())
    sql = (
        f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) "
        f"VALUES ({','.join('?' * len(columns))})"
    )
    conn = get_conn()
    try:
        conn.executemany(
            sql, [[row.get(c, "") for c in columns] for row in rows]
        )
        conn.commit()
    finally:
        conn.close()


def count(table: str) -> int:
    row = query_one(f"SELECT COUNT(*) AS n FROM {table}")
    return int(row["n"]) if row else 0
