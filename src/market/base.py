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

    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get current status of an order.

        Returns:
            Dict with keys:
                - order_id: str
                - status: str (PENDING, ACCEPTED, PARTIAL, FILLED, CANCELLED, REJECTED)
                - filled_volume_mwh: float (total filled)
                - remaining_volume_mwh: float (remaining)
        """
        ...

    def get_all_orders_status(self) -> Sequence[Dict[str, Any]]:
        """
        Get status of all active orders.

        Override this if the API supports batch status queries.
        Default implementation returns empty list.
        """
        return []
