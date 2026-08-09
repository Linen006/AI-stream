"""核心逻辑测试（不依赖真实 API，可离线运行）。"""
import csv
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.llm import LLMClient
from app.db import database as db
from app.services import agent_service as agent
from app.services import analysis_service as da
from app.services import knowledge_service as kb
from app.services import workflow_service as wf
from app.web.tasks import tasks


def test_load_products():
    """商品库能正确读取。"""
    products = wf.load_products()
    assert len(products) >= 6, "商品库至少6条"
    assert all("id" in p and "name" in p for p in products)
    print(f"[OK] 商品库读取 {len(products)} 条")


def test_next_id():
    """业务编号自动递增。"""
    tmp = Path(tempfile.mkdtemp()) / "test.csv"
    tmp.write_text("id,title\nS001,脚本1\nS003,脚本3\n", encoding="utf-8")
    assert wf.next_id("S", tmp) == "S004"
    tmp2 = Path(tempfile.mkdtemp()) / "empty.csv"
    assert wf.next_id("S", tmp2) == "S001"
    print("[OK] next_id 编号递增")


def test_append_csv():
    """回写 CSV 真实追加记录。"""
    tmp = Path(tempfile.mkdtemp()) / "scripts.csv"
    wf.append_csv(tmp, wf.SCRIPT_COLUMNS, {
        "id": "S099", "title": "测试", "product_id": "P001",
        "content_id": "C001", "duration_sec": "30", "shot_table": "x",
        "review_status": "已审核", "owner": "测试", "priority": "中",
        "updated_at": "2026-08-04", "remark": "test",
    })
    rows = list(csv.DictReader(open(tmp, encoding="utf-8-sig")))
    assert len(rows) == 1
    assert rows[0]["id"] == "S099"
    assert rows[0]["product_id"] == "P001"
    print("[OK] CSV 回写追加")


def test_review_metrics():
    """复盘指标：CTR、ROI、跳出率、零投流判断。"""
    rows = [da.compute_metrics(r) for r in da.load_ads_data()]
    assert len(rows) >= 5
    paid = [m for m in rows if m.is_paid]
    organic = [m for m in rows if not m.is_paid]
    assert paid, "存在付费视频"
    assert organic, "存在自然流量视频"
    assert all(m.roi is None for m in organic), "零投流 ROI 应为 None"
    assert all(m.ctr >= 0 for m in rows)
    best = max(paid, key=lambda m: m.roi)
    worst = min(paid, key=lambda m: m.roi)
    assert best.video_id == "V003", "最佳应为V003"
    assert worst.video_id == "V002", "最差付费应为V002（不是V004）"
    assert any(m.drop2s > 40 for m in rows), "跳出率异常应可被识别"
    print(f"[OK] 复盘指标: 最佳={best.video_id} 最差付费={worst.video_id}")


def test_validate_input():
    """智能体输入校验。"""
    try:
        agent.validate_input("")
        raise AssertionError("空输入应报错")
    except ValueError:
        pass
    try:
        agent.validate_input("x" * 100)
        raise AssertionError("超长输入应报错")
    except ValueError:
        pass
    assert agent.validate_input("  榨汁杯  ") == "榨汁杯"
    print("[OK] 输入校验")


def test_load_prompt():
    """知识库提示词可加载。"""
    prompt = agent.load_prompt("script_generation")
    assert prompt is not None
    assert "脚本分镜表" in prompt
    assert "AI画面提示词" in prompt
    print("[OK] 知识库提示词加载")


def test_knowledge_search():
    """知识库支持关键词检索。"""
    result = kb.search_prompts("脚本分镜")
    assert result, "检索应有结果"
    assert any(item["key"] == "script_generation" for item in result)
    print("[OK] 知识库检索")


def test_mock_llm():
    """离线 Mock 模式不依赖 API，输出包含关键结构。"""
    client = LLMClient(mock=True)
    text = client.chat([{"role": "user", "content": "请生成30秒短视频脚本"}])
    assert "脚本分镜表" in text
    assert "发布标题" in text
    print("[OK] Mock LLM 离线可用")


def test_db_closed_loop():
    """SQLite 闭环：复盘结果可真实写入并查询 reviews 表。"""
    with tempfile.TemporaryDirectory() as tmp:
        db.set_db_path(Path(tmp) / "test.db")
        try:
            db.ensure_db()
            db.insert("reviews", {
                "id": "R999",
                "period": "2026-T",
                "video_ids": "V001,V002",
                "best_video": "V003",
                "worst_video": "V002",
                "overall_roi": "3.33",
                "problem": "测试异常",
                "action": "测试动作",
                "owner": "测试",
                "deadline": "",
                "priority": "高",
                "status": "已完成",
                "updated_at": "2026-08-09",
                "remark": "test",
            })
            row = db.query_one("SELECT * FROM reviews WHERE id=?", ("R999",))
            assert row and row["best_video"] == "V003"
            assert db.count("reviews") >= 1
        finally:
            db.set_db_path(db.DB_PATH)
    print("[OK] SQLite 闭环回写")


def test_task_manager():
    """后台任务队列：提交后能拿到 done 状态与结果。"""
    task_id = tasks.submit(lambda: "ok")
    for _ in range(50):
        task = tasks.get(task_id)
        if task and task["status"] != "running":
            break
        time.sleep(0.05)
    assert tasks.get(task_id)["status"] == "done"
    assert tasks.get(task_id)["result"] == "ok"
    print("[OK] 后台任务队列")


if __name__ == "__main__":
    test_load_products()
    test_next_id()
    test_append_csv()
    test_review_metrics()
    test_validate_input()
    test_load_prompt()
    test_knowledge_search()
    test_mock_llm()
    test_db_closed_loop()
    test_task_manager()
    print("\n全部核心测试通过！")
