"""
数据模型定义
用于定义API响应的数据结构
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Any


@dataclass
class Coordinates:
    """坐标数据结构"""
    x1: int
    y1: int
    x2: int
    y2: int

    def model_dump(self):
        return asdict(self)


@dataclass
class UpdateData:
    """更新数据结构"""
    questName: str
    onlineWidth: int
    linkId: int
    linkCatId: int
    stuff: Coordinates
    onlineHeight: int
    chasm: Coordinates

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            questName=d.get("questName", ""),
            onlineWidth=d.get("onlineWidth", 0),
            linkId=d.get("linkId", 0),
            linkCatId=d.get("linkCatId", 0),
            stuff=Coordinates(**d.get("stuff", {})),
            onlineHeight=d.get("onlineHeight", 0),
            chasm=Coordinates(**d.get("chasm", {}))
        )

    def model_dump(self):
        return asdict(self)


@dataclass
class RedeemCode:
    """兑换码数据结构"""
    code: str
    expiredAt: str

    def model_dump(self):
        return asdict(self)


@dataclass
class ApiData:
    """API数据结构"""
    version: str
    redeemCodes: List[RedeemCode]
    updateData: UpdateData

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            version=d.get("version", ""),
            redeemCodes=[RedeemCode(**item) for item in d.get("redeemCodes", [])],
            updateData=UpdateData.from_dict(d.get("updateData", {}))
        )

    def model_dump(self):
        """兼容 Pydantic 的 model_dump 调用"""
        return asdict(self)


@dataclass
class ApiResponse:
    """API响应结构"""
    status: str
    data: ApiData
    timestamp: str

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            status=d.get("status", ""),
            data=ApiData.from_dict(d.get("data", {})),
            timestamp=d.get("timestamp", "")
        )

    def model_dump(self):
        """兼容 Pydantic 的 model_dump 调用"""
        return asdict(self)


def parse_config_update_data(config_value: Any) -> Optional[ApiResponse]:
    """
    安全地解析配置中的update_data
    :param config_value: config.update_data.value
    :return: Optional->解析后的ApiResponse对象，如果解析失败则返回None
    """
    if not config_value or not isinstance(config_value, dict):
        return None

    try:
        return ApiResponse.from_dict(config_value)
    except Exception:
        return None
