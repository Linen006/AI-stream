"""零依赖 Web 服务：静态页面 + JSON API + 后台任务队列。"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.db import database as db
from app.services import (
    agent_service,
    analysis_service,
    knowledge_service,
    workflow_service,
)
from app.services import storage
from app.web.tasks import tasks

logger = get_logger("web")

STATIC_DIR = Path(__file__).resolve().parent / "static"
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def _send_json(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "AIContentWeb/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        logger.debug("HTTP %s", fmt % args)

    # ---------- GET ----------
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in ("/", "/index.html"):
                self._serve_static("index.html")
            elif path.startswith("/static/"):
                self._serve_static(path[len("/static/"):])
            elif path == "/api/health":
                _send_json(self, {
                    "ok": True,
                    "app": settings.app_name,
                    "version": settings.version,
                    "api_ready": settings.api_ready,
                    "mock_ai": settings.mock_ai,
                })
            elif path == "/api/overview":
                self._overview()
            elif path == "/api/recent":
                self._recent()
            elif path == "/api/products":
                _send_json(self, {"products": workflow_service.load_products()})
            elif path == "/api/knowledge":
                _send_json(self, {"items": knowledge_service.list_prompts()})
            elif path == "/api/reports":
                report_path = storage.OUTPUT_DIR / "复盘报告.txt"
                content = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
                _send_json(self, {"path": str(report_path), "content": content})
            elif path == "/api/tasks":
                query = parse_qs(parsed.query)
                task_id = (query.get("id") or [""])[0]
                if task_id:
                    task = tasks.get(task_id)
                    if not task:
                        _send_json(self, {"error": "任务不存在"}, 404)
                    else:
                        _send_json(self, {"task": task})
                else:
                    _send_json(self, {"tasks": tasks.recent()})
            else:
                _send_json(self, {"error": "接口不存在"}, 404)
        except Exception as exc:
            logger.exception("GET %s 处理失败", path)
            _send_json(self, {"error": str(exc)}, 500)

    def _overview(self) -> None:
        products = len(workflow_service.load_products())
        metrics = [
            analysis_service.compute_metrics(row)
            for row in analysis_service.load_ads_data()
        ]
        total_cost = sum(m.cost for m in metrics)
        total_revenue = sum(m.revenue for m in metrics)
        overall_roi = round(total_revenue / total_cost, 2) if total_cost else 0
        _send_json(self, {
            "products": products,
            "scripts": db.count("scripts"),
            "contents": db.count("contents"),
            "videos": db.count("videos"),
            "ads": db.count("ads"),
            "leads": db.count("leads"),
            "reviews": db.count("reviews"),
            "total_cost": round(total_cost, 2),
            "total_revenue": round(total_revenue, 2),
            "overall_roi": overall_roi,
        })

    def _recent(self) -> None:
        """返回数据库中最近的脚本、视频与复盘，用于工作台概览。"""
        sources = (
            ("script", "scripts", "title", "review_status"),
            ("video", "videos", "title", "status"),
            ("review", "reviews", "period", "status"),
        )
        items = []
        for item_type, table, title_field, status_field in sources:
            rows = db.query_all(
                f"SELECT id, {title_field} AS title, "
                f"{status_field} AS status, updated_at FROM {table} "
                "ORDER BY COALESCE(updated_at, '') DESC LIMIT 5"
            )
            for row in rows:
                row["type"] = item_type
                items.append(row)
        items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        _send_json(self, {"items": items[:5]})

    # ---------- POST ----------
    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json()
            if path == "/api/agent/generate":
                task_id = tasks.submit(
                    agent_service.run_agent,
                    body.get("product_name", ""),
                    body.get("audience"),
                    body.get("scenario"),
                    body.get("sell"),
                    body.get("mock"),
                )
                _send_json(self, {"task_id": task_id})
            elif path == "/api/workflow/run":
                product = workflow_service.find_product(body.get("product_id", ""))
                if not product:
                    _send_json(self, {"error": "商品不存在"}, 404)
                    return
                task_id = tasks.submit(
                    workflow_service.run_workflow, product, True, body.get("mock")
                )
                _send_json(self, {"task_id": task_id})
            elif path == "/api/analysis/run":
                task_id = tasks.submit(analysis_service.analyze, body.get("mock"))
                _send_json(self, {"task_id": task_id})
            elif path == "/api/knowledge/add":
                item = knowledge_service.add_prompt(
                    body.get("key", ""),
                    body.get("prompt", ""),
                    body.get("category", ""),
                    body.get("description", ""),
                )
                _send_json(self, {"item": item})
            else:
                _send_json(self, {"error": "接口不存在"}, 404)
        except Exception as exc:
            logger.exception("POST %s 处理失败", path)
            _send_json(self, {"error": str(exc)}, 500)

    def _read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    # ---------- static ----------
    def _serve_static(self, relative: str) -> None:
        root = STATIC_DIR.resolve()
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            _send_json(self, {"error": "文件不存在"}, 404)
            return
        body = target.read_bytes()
        mime = MIME_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(address) -> ThreadingHTTPServer:
    """创建可复用的线程化 HTTP 服务。"""
    server = ThreadingHTTPServer(address, AppHandler)
    server.daemon_threads = True
    return server
