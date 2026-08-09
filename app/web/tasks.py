"""内存任务队列：让耗时 AI 调用在后台执行，WebUI 轮询进度。

设计参考 MoneyPrinterTurbo：任务提交后立即返回 task_id，
前端轮询 /api/tasks?id=xx 获取状态、日志与结果。
"""
import io
import threading
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from typing import Any, Callable, Dict, Optional


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TaskManager:
    def __init__(self) -> None:
        self._tasks: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def submit(self, fn: Callable, *args, **kwargs) -> str:
        task_id = f"T{datetime.now().strftime('%H%M%S')}-{uuid.uuid4().hex[:4]}"
        with self._lock:
            self._tasks[task_id] = {
                "id": task_id,
                "status": "running",
                "result": None,
                "error": None,
                "logs": "",
                "created_at": _now(),
                "finished_at": None,
            }
        thread = threading.Thread(
            target=self._run, args=(task_id, fn, args, kwargs), daemon=True
        )
        thread.start()
        return task_id

    def _run(
        self, task_id: str, fn: Callable, args: tuple, kwargs: dict
    ) -> None:
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                result = fn(*args, **kwargs)
            with self._lock:
                self._tasks[task_id]["status"] = "done"
                self._tasks[task_id]["result"] = result
                self._tasks[task_id]["logs"] = buffer.getvalue()
        except Exception as exc:
            with self._lock:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(exc)
                self._tasks[task_id]["logs"] = buffer.getvalue()
        finally:
            with self._lock:
                self._tasks[task_id]["finished_at"] = _now()

    def get(self, task_id: str) -> Optional[dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def recent(self, limit: int = 10) -> list:
        with self._lock:
            items = sorted(
                self._tasks.values(), key=lambda t: t["created_at"], reverse=True
            )
            return [dict(t) for t in items[:limit]]


tasks = TaskManager()
