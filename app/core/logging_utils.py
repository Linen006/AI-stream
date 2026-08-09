"""统一日志：控制台 + 文件（logs/app.log），方便排查和演示复盘。"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIR / "app.log"

_configured = False


def setup_logging() -> logging.Logger:
    """初始化一次根日志器，重复调用不会叠加 handler。"""
    global _configured
    logger = logging.getLogger("ai_ecommerce")
    if _configured:
        return logger

    LOG_DIR.mkdir(exist_ok=True)
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.propagate = False
    _configured = True
    return logger


def get_logger(name: str = "app") -> logging.Logger:
    """获取子模块 logger。"""
    return logging.getLogger(f"ai_ecommerce.{name}")
