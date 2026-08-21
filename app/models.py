from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Price(BaseModel):
    amount: float
    currency: str = "INR"


class Weight(BaseModel):
    value: float
    unit: str
    original: Optional[str] = None


class ProductResponse(BaseModel):
    gtin: str
    name: list[str] = Field(default_factory=list, max_length=3)
    name_source: list[str] = Field(default_factory=list, max_length=3)
    price: list[Price] = Field(default_factory=list, max_length=3)
    price_source: list[str] = Field(default_factory=list, max_length=3)
    weight: list[Weight] = Field(default_factory=list, max_length=3)
    weight_source: list[str] = Field(default_factory=list, max_length=3)
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cache: str = "sample"


class NameChoice(BaseModel):
    value: Optional[str] = None
    source: Optional[str] = None
    custom: bool = False


class PriceChoice(BaseModel):
    amount: Optional[float] = None
    currency: str = "INR"
    source: Optional[str] = None
    custom: bool = False


class WeightChoice(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    source: Optional[str] = None
    custom: bool = False


class ConfirmRequest(BaseModel):
    name: NameChoice
    price: PriceChoice
    weight: WeightChoice


class ConfirmResponse(BaseModel):
    gtin: str
    product: dict
    confidence: dict[str, int]


class InvalidateResponse(BaseModel):
    gtin: str
    lookup: bool
    master: bool


class ErrorBody(BaseModel):
    error: str
    gtin: Optional[str] = None
    detail: Optional[str] = None
