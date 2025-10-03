"""
Order lifecycle monitor.

Tracks order state changes and triggers callbacks automatically.
"""

from __future__ import annotations
from typing import Dict, Optional, Callable
from datetime import datetime
from enum import Enum
import logging


class OrderStatus(str, Enum):
    """Order status values."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderInfo:
    """Order information tracked by monitor."""

    def __init__(
        self,
        order_id: str,
        side: str,
        volume_mwh: float,
        price_eur_mwh: float,
        status: str,
        reservation_id: str
    ):
        self.order_id = order_id
        self.side = side
        self.volume_mwh = volume_mwh
        self.price_eur_mwh = price_eur_mwh
        self.status = status
        self.reservation_id = reservation_id
        self.filled_volume_mwh = 0.0
        self.remaining_volume_mwh = volume_mwh
        self.last_update = datetime.now()

    @property
    def is_terminal(self) -> bool:
        """Check if order is in terminal state."""
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        )


class OrderMonitor:
    """
    Monitors order lifecycle and triggers callbacks.

    This component:
    1. Tracks active orders
    2. Detects state changes (fills, cancellations)
    3. Automatically triggers appropriate callbacks
    4. Manages order cleanup
    """

    def __init__(
        self,
        on_filled_callback: Callable[[str, float, str], None],
        on_cancelled_callback: Callable[[str], None],
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize order monitor.

        Args:
            on_filled_callback: Called when order fills (order_id, filled_volume, side)
            on_cancelled_callback: Called when order cancelled (order_id)
            logger: Optional logger
        """
        self.tracked_orders: Dict[str, OrderInfo] = {}
        self.on_filled_callback = on_filled_callback
        self.on_cancelled_callback = on_cancelled_callback
        self.log = logger or logging.getLogger(__name__)

    def track_order(
        self,
        order_id: str,
        side: str,
        volume_mwh: float,
        price_eur_mwh: float,
        status: str,
        reservation_id: str
    ) -> None:
        """
        Start tracking an order.

        Args:
            order_id: Market order ID
            side: "BUY" or "SELL"
            volume_mwh: Order volume
            price_eur_mwh: Order price
            status: Initial status
            reservation_id: Associated reservation ID
        """
        order_info = OrderInfo(
            order_id=order_id,
            side=side,
            volume_mwh=volume_mwh,
            price_eur_mwh=price_eur_mwh,
            status=status,
            reservation_id=reservation_id
        )
        self.tracked_orders[order_id] = order_info
        self.log.debug(f"Started tracking order {order_id}: {status}")

    def update_order_status(
        self,
        order_id: str,
        new_status: str,
        filled_volume_mwh: Optional[float] = None
    ) -> None:
        """
        Update order status and trigger callbacks if needed.

        Args:
            order_id: Market order ID
            new_status: New status
            filled_volume_mwh: Total filled volume (if applicable)
        """
        if order_id not in self.tracked_orders:
            self.log.warning(f"Order {order_id} not tracked - ignoring update")
            return

        order = self.tracked_orders[order_id]
        old_status = order.status
        order.status = new_status
        order.last_update = datetime.now()

        self.log.debug(f"Order {order_id} status: {old_status} → {new_status}")

        # Update filled volume if provided
        if filled_volume_mwh is not None:
            old_filled = order.filled_volume_mwh
            order.filled_volume_mwh = filled_volume_mwh
            order.remaining_volume_mwh = order.volume_mwh - filled_volume_mwh

            # Detect fills
            if filled_volume_mwh > old_filled:
                newly_filled = filled_volume_mwh - old_filled
                self._handle_fill(order, newly_filled)

        # Handle terminal states
        if order.is_terminal:
            self._handle_terminal_state(order)

    def _handle_fill(self, order: OrderInfo, newly_filled_volume: float) -> None:
        """Handle order fill."""
        self.log.info(f"Order {order.order_id} filled: {newly_filled_volume} MWh")

        # Trigger fill callback
        try:
            self.on_filled_callback(
                order.order_id,
                newly_filled_volume,
                order.side
            )
        except Exception as e:
            self.log.error(f"Fill callback failed for {order.order_id}: {e}")

    def _handle_terminal_state(self, order: OrderInfo) -> None:
        """Handle terminal order state."""
        self.log.info(f"Order {order.order_id} terminal: {order.status}")

        # Trigger appropriate callback
        try:
            if order.status == OrderStatus.CANCELLED:
                self.on_cancelled_callback(order.order_id)
            elif order.status == OrderStatus.EXPIRED:
                self.on_cancelled_callback(order.order_id)
            elif order.status == OrderStatus.REJECTED:
                # Rejection handled during submit, but clean up if needed
                pass
        except Exception as e:
            self.log.error(f"Terminal state callback failed for {order.order_id}: {e}")

        # Remove from tracking
        del self.tracked_orders[order.order_id]
        self.log.debug(f"Stopped tracking order {order.order_id}")

    def get_active_orders(self) -> Dict[str, OrderInfo]:
        """Get all active orders."""
        return self.tracked_orders.copy()

    def cleanup_stale_orders(self, max_age_seconds: int = 86400) -> int:
        """
        Clean up orders with no updates for max_age_seconds.

        Args:
            max_age_seconds: Maximum age before cleanup (default 24h)

        Returns:
            Number of orders cleaned up
        """
        now = datetime.now()
        stale_orders = []

        for order_id, order in self.tracked_orders.items():
            age_seconds = (now - order.last_update).total_seconds()
            if age_seconds > max_age_seconds:
                stale_orders.append(order_id)

        for order_id in stale_orders:
            self.log.warning(f"Cleaning up stale order {order_id}")
            del self.tracked_orders[order_id]

        return len(stale_orders)
