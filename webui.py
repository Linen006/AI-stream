"""Web 控制台入口：python webui.py

启动后自动打开浏览器，默认地址 http://127.0.0.1:8000
"""
import threading
import webbrowser

from app.core.config import settings
from app.core.logging_utils import setup_logging
from app.db import database as db
from app.web.server import create_server

setup_logging()


def main() -> None:
    db.ensure_db()
    url = f"http://{settings.web_host}:{settings.web_port}"
    server = create_server((settings.web_host, settings.web_port))
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"\n  {settings.app_name} v{settings.version}")
    print(f"  Web 控制台已启动: {url}")
    if settings.mock_ai:
        print("  当前为离线演示模式（MOCK_AI=true），AI 返回固定演示内容")
    elif not settings.api_ready:
        print("  提示：未配置 API Key，AI 功能将报错；可在 .env 中设置 MOCK_AI=true")
    print("  按 Ctrl+C 停止服务\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
