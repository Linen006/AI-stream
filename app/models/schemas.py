"""领域模型：统一数据结构，方便服务层、CLI、Web API 共用。"""
from dataclasses import asdict, dataclass
from typing import Dict, Optional


@dataclass
class ProductInfo:
    """商品信息。"""

    id: str
    name: str
    price: str
    category: str = ""
    target_audience: str = ""
    selling_points: str = ""
    status: str = ""
    heat_score: str = ""

    @classmethod
    def from_dict(cls, row: Dict[str, str]) -> "ProductInfo":
        return cls(
            id=row.get("id", ""),
            name=row.get("name", ""),
            price=row.get("price", ""),
            category=row.get("category", ""),
            target_audience=row.get("target_audience", ""),
            selling_points=row.get("selling_points", ""),
            status=row.get("status", ""),
            heat_score=row.get("heat_score", ""),
        )

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class VideoMetrics:
    """单条视频的复盘指标。"""

    video_id: str
    video_name: str
    views: int
    cart_clicks: int
    orders: int
    revenue: float
    cost: float
    drop2s: float
    ctr: float
    conv: float
    roi: Optional[float]
    is_paid: bool

    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "roi": self.roi if self.roi is not None else "N/A",
        }
