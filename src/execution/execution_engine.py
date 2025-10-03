from __future__ import annotations
from typing import Dict, Any
from datetime import datetime

from ..market.base import MarketClient
from ..risk.risk_manager import RiskManager
from .order_monitor import OrderMonitor


class ExecutionEngine:
    def __init__(self, pzu: MarketClient | None, bm: MarketClient | None, risk: RiskManager, logger):
        self.pzu = pzu
        self.bm = bm
        self.risk = risk
        self.log = logger

        # Order monitor with callbacks wired to this engine
        self.order_monitor = OrderMonitor(
            on_filled_callback=self._on_order_filled_internal,
            on_cancelled_callback=self._on_order_cancelled_internal
        )

        # Track active orders: {order_id: reservation_id}
        self.active_orders = {}

    def submit(
        self,
        market: str,
        product: str,
        delivery_start: datetime,
        delivery_end: datetime,
        side: str,
        volume_mwh: float,
        price_eur_mwh: float,
    ) -> Dict[str, Any]:
        ok, reason = self.risk.validate_order(side, volume_mwh, price_eur_mwh)
        if not ok:
            self.log.warning(f"Order rejected by risk: {reason}")
            return {"status": "REJECTED", "reason": reason}

        client: MarketClient | None = None
        if market.upper() == "PZU":
            client = self.pzu
        elif market.upper() in ("BM", "BALANCING"):
            client = self.bm

        if client is None:
            self.log.warning("No client configured for market %s", market)
            return {"status": "REJECTED", "reason": "no client"}

        # Reserve SOC for order and get tracking ID
        reservation_id = self.risk.reserve_for_order(side, volume_mwh)
        try:
            res = client.place_order(
                product=product,
                delivery_start=delivery_start,
                delivery_end=delivery_end,
                side=side,
                volume_mwh=volume_mwh,
                price_eur_mwh=price_eur_mwh,
            )
            self.log.info("Submitted order: %s", res)

            # Handle reservation based on order status
            status = res.get("status", "UNKNOWN")

            if status == "REJECTED":
                # Order rejected - release reservation immediately
                self.risk.release_order(reservation_id)
                self.log.debug(f"Released reservation {reservation_id} (order rejected)")

            elif status in ("ACCEPTED", "PENDING", "PARTIAL"):
                # Order accepted/pending - track it for later release
                order_id = res.get("order_id") or res.get("id")
                if order_id:
                    self.active_orders[order_id] = reservation_id

                    # Start monitoring this order
                    self.order_monitor.track_order(
                        order_id=order_id,
                        side=side,
                        volume_mwh=volume_mwh,
                        price_eur_mwh=price_eur_mwh,
                        status=status,
                        reservation_id=reservation_id
                    )

                    self.log.debug(f"Tracking order {order_id} with reservation {reservation_id}")
                else:
                    # No order ID - release immediately to prevent leak
                    self.log.warning(f"Order accepted but no order_id returned - releasing reservation")
                    self.risk.release_order(reservation_id)

            else:
                # Unknown status - release to be safe
                self.log.warning(f"Unknown order status '{status}' - releasing reservation")
                self.risk.release_order(reservation_id)

            return res
        except Exception as e:
            # On exception, always release the reservation
            self.risk.release_order(reservation_id)
            raise

    def update_order_status(
        self,
        order_id: str,
        new_status: str,
        filled_volume_mwh: float = None
    ) -> None:
        """
        Update order status from market feed.

        This is the PUBLIC METHOD that should be called from:
        - Market data feeds
        - WebSocket updates
        - Polling loops
        - Backtesting fills

        The order monitor will automatically trigger callbacks.

        Args:
            order_id: Market order ID
            new_status: New order status ("FILLED", "CANCELLED", etc.)
            filled_volume_mwh: Total filled volume (if applicable)

        Example:
            # From market data feed
            engine.update_order_status("ORDER_123", "FILLED", 10.0)

            # From backtest
            for fill in fills:
                engine.update_order_status(fill.order_id, "FILLED", fill.volume)
        """
        self.order_monitor.update_order_status(order_id, new_status, filled_volume_mwh)

    def _on_order_filled_internal(self, order_id: str, filled_volume_mwh: float, side: str) -> None:
        """Internal callback when order fills (called by order monitor)."""
        self.on_order_filled(order_id, filled_volume_mwh, side)

    def _on_order_cancelled_internal(self, order_id: str) -> None:
        """Internal callback when order cancelled (called by order monitor)."""
        self.on_order_cancelled(order_id)

    def on_order_filled(self, order_id: str, filled_volume_mwh: float, side: str) -> None:
        """Called when an order is filled (fully or partially).

        Parameters
        ----------
        order_id : str
            Market order ID
        filled_volume_mwh : float
            Volume filled
        side : str
            Order side (BUY/SELL)

        Notes
        -----
        When order is filled, we DON'T adjust SOC again - the reservation already adjusted it.
        We just release the reservation to confirm it's permanent.
        The reservation becomes reality, so SOC stays where it is.
        """
        if order_id in self.active_orders:
            reservation_id = self.active_orders[order_id]

            # Remove the reservation tracking (but keep the SOC change)
            # The SOC was already adjusted when we reserved - now it's permanent
            if reservation_id in self.risk.reservations:
                del self.risk.reservations[reservation_id]

            # Decrement open orders
            self.risk.open_orders = max(0, self.risk.open_orders - 1)

            # Remove from active orders
            del self.active_orders[order_id]
            self.log.info(f"Order {order_id} filled: {filled_volume_mwh} MWh {side}, SOC now {self.risk.soc:.2%}")

    def on_order_cancelled(self, order_id: str) -> None:
        """Called when an order is cancelled.

        Parameters
        ----------
        order_id : str
            Market order ID
        """
        if order_id in self.active_orders:
            reservation_id = self.active_orders[order_id]

            # Release the reservation
            self.risk.release_order(reservation_id)

            # Remove from active orders
            del self.active_orders[order_id]
            self.log.info(f"Order {order_id} cancelled, reservation {reservation_id} released")
