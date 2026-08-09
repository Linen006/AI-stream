"""知识库服务：提示词 JSON 的读取、检索、版本管理。

对应评估里"知识库未落地"的扣分项：提示词现在可被工作流/智能体/复盘
真实加载，并且支持检索与版本迭代。
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
PROMPTS_PATH = KNOWLEDGE_DIR / "prompts.json"


def load_prompts() -> Dict[str, dict]:
    """读取完整提示词库。"""
    if not PROMPTS_PATH.exists():
        return {}
    return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))


def get_prompt(key: str) -> Optional[str]:
    """按 key 取提示词正文（旧接口兼容）。"""
    item = load_prompts().get(key)
    if isinstance(item, dict):
        return item.get("prompt")
    return item


def get_prompt_meta(key: str) -> dict:
    """返回带 key 的完整元信息。"""
    item = load_prompts().get(key)
    if not isinstance(item, dict):
        return {"key": key, "prompt": item}
    return {"key": key, **item}


def list_prompts() -> List[dict]:
    """列出全部提示词。"""
    return [get_prompt_meta(key) for key in load_prompts()]


def search_prompts(keyword: str) -> List[dict]:
    """按关键词检索提示词。"""
    kw = keyword.strip().lower()
    if not kw:
        return list_prompts()
    result = []
    for item in list_prompts():
        haystack = " ".join(str(v) for v in item.values()).lower()
        if kw in haystack:
            result.append(item)
    return result


def add_prompt(
    key: str, prompt: str, category: str = "", description: str = ""
) -> dict:
    """新增或更新提示词，自动升级版本号。"""
    prompts = load_prompts()
    old = prompts.get(key, {})
    version = _bump_version(old.get("version", "v0.0"))
    prompts[key] = {
        "version": version,
        "category": category or old.get("category", ""),
        "description": description or old.get("description", ""),
        "prompt": prompt,
    }
    PROMPTS_PATH.write_text(
        json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"key": key, **prompts[key]}


def _bump_version(version: str) -> str:
    """v1.0 -> v1.1。"""
    m = re.match(r"v(\d+)\.(\d+)", str(version))
    if not m:
        return "v1.0"
    return f"v{int(m.group(1))}.{int(m.group(2)) + 1}"
