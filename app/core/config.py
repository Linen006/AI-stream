"""统一配置模块：从 .env 读取，支持离线 Mock 模式。

所有服务统一从这里拿配置，避免散落硬编码。等价于开源项目里的
Pydantic Settings，但保持零第三方依赖。
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # python-dotenv 未安装时仍可运行
    pass


class Settings:
    """类型化配置。"""

    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "AI短视频电商提效系统")
        self.version = os.getenv("APP_VERSION", "v3.0")
        self.debug = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.web_host = os.getenv("WEB_HOST", "127.0.0.1")
        self.web_port = int(os.getenv("WEB_PORT", "8000"))

        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "60"))
        # MOCK_AI=true 时不需要 API Key，AI 返回固定演示内容，适合面试演示
        self.mock_ai = os.getenv("MOCK_AI", "false").lower() in (
            "1",
            "true",
            "yes",
        )

    @property
    def api_ready(self) -> bool:
        """是否已配置真实 API Key。"""
        return bool(self.deepseek_api_key) and self.deepseek_api_key != "sk-your-key-here"


settings = Settings()
