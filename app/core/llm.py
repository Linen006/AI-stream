"""统一大模型客户端：DeepSeek / OpenAI 兼容接口 + Mock 离线模式。

设计参考 MoneyPrinterTurbo：多模型服务统一抽象，服务层不直接写 requests。
"""
import time
from typing import Dict, List, Optional

import requests

from app.core.config import settings
from app.core.logging_utils import get_logger

logger = get_logger("llm")


class LLMError(RuntimeError):
    """大模型调用失败统一异常。"""


class LLMClient:
    """支持真实 API 与 Mock 两种模式。"""

    def __init__(self, mock: Optional[bool] = None) -> None:
        self.mock = settings.mock_ai if mock is None else mock

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        timeout: Optional[int] = None,
    ) -> str:
        """调用大模型并返回文本。带重试、超时、清晰报错。"""
        if self.mock:
            return self._mock_reply(messages)
        if not settings.api_ready:
            raise LLMError(
                "未配置 DeepSeek API Key：复制 .env.example 为 .env 填入 Key，"
                "或设置 MOCK_AI=true 使用离线演示。"
            )

        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.deepseek_model,
            "messages": messages,
            "temperature": temperature,
        }
        url = f"{settings.deepseek_base_url.rstrip('/')}/v1/chat/completions"
        timeout = timeout or settings.request_timeout
        last_error = "未知错误"

        for attempt in range(1, 4):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    logger.info("LLM 调用成功，返回 %s 字符", len(content))
                    return content
                last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                logger.warning("LLM 调用失败（第 %s 次）：%s", attempt, last_error)
            except Exception as exc:  # 网络超时、连接失败等
                last_error = str(exc)
                logger.warning("LLM 网络异常（第 %s 次）：%s", attempt, last_error)
            time.sleep(attempt)  # 指数退避：1s、2s

        raise LLMError(f"AI 调用失败，已重试 3 次：{last_error}")

    def _mock_reply(self, messages: List[Dict[str, str]]) -> str:
        """离线演示输出：按提示词关键词返回结构完整的固定内容。"""
        user_text = " ".join(
            m.get("content", "") for m in messages if m.get("role") == "user"
        )
        if "质检" in user_text or "发布标题" in user_text:
            return (
                "【发布标题】\n"
                "1. 30秒看完就想买：便携榨汁杯的隐藏用法\n"
                "2. 打工人早餐救星：便携榨汁杯实测\n"
                "3. 宿舍党狂喜：便携榨汁杯也太方便了\n\n"
                "【质检清单】\n"
                "| 检查项 | 结果 |\n"
                "| --- | --- |\n"
                "| 前3秒钩子 | 通过 |\n"
                "| 卖点清晰 | 通过 |\n"
                "| 无绝对化用语 | 通过 |\n"
                "| 无医疗功效 | 通过 |\n"
                "| 字幕完整 | 通过 |\n\n"
                "【AI画面提示词】\n"
                "1. 清晨厨房，阳光洒落，榨汁杯高速运转\n"
                "2. 通勤路上，白色榨汁杯握在手中\n"
                "3. 办公桌角落，产品特写，背景虚化"
            )
        if "脚本" in user_text or "分镜" in user_text or "30秒" in user_text:
            return (
                "【脚本分镜表】\n"
                "| 时间 | 画面描述 | 旁白 | 字幕 | 镜头运动 |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| 0-3秒 | 闹钟响起，打工人起床 | 早起喝一杯鲜榨果汁 | 起床 | 固定 |\n"
                "| 3-8秒 | 放入水果一键启动 | 免拆洗，20秒出汁 | 20秒出汁 | 推近 |\n"
                "| 8-15秒 | 榨汁完成，直接带走 | 通勤路上也能喝 | 便携 | 跟拍 |\n"
                "| 15-22秒 | 对比奶茶与果汁 | 一杯奶茶的钱喝一周 | 省钱 | 对比镜头 |\n"
                "| 22-30秒 | 点击购物车 | 现在下单，明天到 | 购买 | 特写 |\n\n"
                "【AI画面提示词】\n"
                "1. 清晨厨房，阳光洒落，榨汁杯高速运转\n"
                "2. 通勤地铁，白色榨汁杯握在手中\n"
                "3. 办公桌角落，产品特写，背景虚化\n\n"
                "【剪辑要点】\n"
                "1. 前3秒用闹钟声制造紧张感\n"
                "2. 转场用快切，节奏 1 秒 1 镜\n"
                "3. 最后 CTA 停顿 0.5 秒\n"
                "4. 全程字幕跟随旁白\n"
                "5. 添加轻快 BGM\n\n"
                "【发布标题】\n"
                "1. 30秒看完就想买：便携榨汁杯的隐藏用法\n"
                "2. 打工人早餐救星：便携榨汁杯实测\n"
                "3. 宿舍党狂喜：便携榨汁杯也太方便了"
            )
        if "卖点" in user_text or "分析" in user_text or "人群" in user_text:
            return (
                "1. 目标人群：上班族、学生、宝妈\n"
                "2. 使用场景：早餐、通勤、宿舍、办公室\n"
                "3. 核心卖点：便携、无线、易清洗、20秒出汁\n"
                "4. 用户痛点：早起来不及、外带饮品贵、清洗麻烦"
            )
        return "Mock AI 输出：请填写 DEEPSEEK_API_KEY 或保持 MOCK_AI=true 使用离线演示。"
