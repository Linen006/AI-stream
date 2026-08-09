"""数据复盘 CLI（兼容入口）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.analysis_service import analyze


def main() -> None:
    analyze()


if __name__ == "__main__":
    main()
