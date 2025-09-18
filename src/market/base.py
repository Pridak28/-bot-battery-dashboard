from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Sequence
from datetime import datetime


class MarketClient(ABC):
    name: str

    @abstractmethod
    def authenticate(self) -> None:
        ...

    @abstractmethod
    def get_day_ahead_prices(self, delivery_date: datetime) -> Sequence[float]:
        ...

    @abstractmethod
    def place_order(
        self,
        product: str,
        delivery_start: datetime,
        delivery_end: datetime,
        side: str,  # BUY | SELL
        volume_mwh: float,
        price_eur_mwh: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        ...

    @abstractmethod
    def get_positions(self) -> Dict[str, Any]:
        ...
