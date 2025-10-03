"""
Simulation-based order fill engine.

This module simulates order fills based on historical price data,
automatically triggering the ExecutionEngine's update_order_status() method.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import logging


class SimulationFillEngine:
    """
    Simulates order fills based on historical price data.

    This connects the order lifecycle to simulation/backtesting by:
    1. Tracking submitted orders
    2. Checking if orders would fill against historical prices
    3. Automatically calling engine.update_order_status() when fills occur
    """

    def __init__(self, execution_engine, logger: Optional[logging.Logger] = None):
        """
        Initialize simulation fill engine.

        Args:
            execution_engine: The ExecutionEngine instance to wire fills to
            logger: Optional logger for debugging
        """
        self.engine = execution_engine
        self.log = logger or logging.getLogger(__name__)

        # Track pending orders: {order_id: order_info}
        self.pending_orders: Dict[str, Dict] = {}

    def register_order(
        self,
        order_id: str,
        product: str,
        delivery_start: datetime,
        delivery_end: datetime,
        side: str,
        volume_mwh: float,
        price_eur_mwh: float
    ) -> None:
        """
        Register an order for simulation fills.

        Call this immediately after engine.submit() returns ACCEPTED.

        Args:
            order_id: Market order ID from submit response
            product: Product (e.g., "H1", "H2")
            delivery_start: Delivery start datetime
            delivery_end: Delivery end datetime
            side: "BUY" or "SELL"
            volume_mwh: Order volume in MWh
            price_eur_mwh: Limit price
        """
        self.pending_orders[order_id] = {
            "product": product,
            "delivery_start": delivery_start,
            "delivery_end": delivery_end,
            "side": side,
            "volume_mwh": volume_mwh,
            "price_eur_mwh": price_eur_mwh,
            "filled": False
        }
        self.log.debug(f"Registered order {order_id} for simulation: {side} {volume_mwh} MWh @ {price_eur_mwh} EUR/MWh")

    def check_fills_against_market_data(
        self,
        market_prices: pd.DataFrame,
        current_time: Optional[datetime] = None
    ) -> List[str]:
        """
        Check pending orders against market price data and trigger fills.

        Args:
            market_prices: DataFrame with columns: date, hour, price
            current_time: Current simulation time (optional)

        Returns:
            List of order IDs that were filled

        Fill Logic:
        - BUY orders fill if market price <= limit price
        - SELL orders fill if market price >= limit price
        - Orders fill at delivery time if price condition met
        """
        filled_orders = []

        for order_id, order_info in list(self.pending_orders.items()):
            if order_info["filled"]:
                continue

            # Check if we've reached delivery time
            if current_time and current_time < order_info["delivery_start"]:
                continue

            # Find market price for delivery period
            delivery_date = order_info["delivery_start"].date()
            delivery_hour = order_info["delivery_start"].hour

            # Query market data
            matching_prices = market_prices[
                (market_prices["date"] == pd.Timestamp(delivery_date)) &
                (market_prices["hour"] == delivery_hour)
            ]

            if matching_prices.empty:
                self.log.debug(f"No market data for order {order_id} delivery: {delivery_date} H{delivery_hour}")
                continue

            market_price = matching_prices.iloc[0]["price"]
            limit_price = order_info["price_eur_mwh"]
            side = order_info["side"]

            # Check fill conditions
            should_fill = False
            if side == "BUY" and market_price <= limit_price:
                should_fill = True
                self.log.info(f"BUY order {order_id} fills: market {market_price} <= limit {limit_price}")
            elif side == "SELL" and market_price >= limit_price:
                should_fill = True
                self.log.info(f"SELL order {order_id} fills: market {market_price} >= limit {limit_price}")

            if should_fill:
                # Trigger fill via ExecutionEngine
                self.engine.update_order_status(
                    order_id=order_id,
                    new_status="FILLED",
                    filled_volume_mwh=order_info["volume_mwh"]
                )

                order_info["filled"] = True
                filled_orders.append(order_id)
                self.log.info(f"Order {order_id} filled: {side} {order_info['volume_mwh']} MWh @ market {market_price}")

        # Clean up filled orders
        for order_id in filled_orders:
            del self.pending_orders[order_id]

        return filled_orders

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if order was cancelled, False if not found
        """
        if order_id not in self.pending_orders:
            return False

        # Trigger cancel via ExecutionEngine
        self.engine.update_order_status(
            order_id=order_id,
            new_status="CANCELLED"
        )

        del self.pending_orders[order_id]
        self.log.info(f"Order {order_id} cancelled via simulation")
        return True

    def cancel_all_pending(self) -> int:
        """
        Cancel all pending orders.

        Returns:
            Number of orders cancelled
        """
        order_ids = list(self.pending_orders.keys())
        count = 0
        for order_id in order_ids:
            if self.cancel_order(order_id):
                count += 1
        return count

    def get_pending_orders(self) -> Dict[str, Dict]:
        """Get all pending orders."""
        return self.pending_orders.copy()

    def expire_old_orders(self, current_time: datetime, expiry_hours: int = 24) -> List[str]:
        """
        Expire orders older than specified hours.

        Args:
            current_time: Current simulation time
            expiry_hours: Hours after delivery_end to expire orders

        Returns:
            List of expired order IDs
        """
        expired = []

        for order_id, order_info in list(self.pending_orders.items()):
            delivery_end = order_info["delivery_end"]
            hours_since_delivery = (current_time - delivery_end).total_seconds() / 3600

            if hours_since_delivery > expiry_hours:
                self.engine.update_order_status(
                    order_id=order_id,
                    new_status="EXPIRED"
                )
                del self.pending_orders[order_id]
                expired.append(order_id)
                self.log.info(f"Order {order_id} expired (>{expiry_hours}h past delivery)")

        return expired


def create_simulation_workflow(execution_engine, market_data_csv: str, logger=None):
    """
    Helper to create complete simulation workflow.

    Usage:
        sim_engine, market_data = create_simulation_workflow(execution_engine, "data/pzu_prices.csv")

        # Place order
        result = execution_engine.submit(...)
        if result["status"] == "ACCEPTED":
            sim_engine.register_order(result["order_id"], ...)

        # Check fills
        filled = sim_engine.check_fills_against_market_data(market_data)

    Args:
        execution_engine: ExecutionEngine instance
        market_data_csv: Path to market price CSV
        logger: Optional logger

    Returns:
        (SimulationFillEngine, market_data_df)
    """
    sim_engine = SimulationFillEngine(execution_engine, logger)

    # Load market data
    import pandas as pd
    market_data = pd.read_csv(market_data_csv)
    market_data["date"] = pd.to_datetime(market_data["date"])

    return sim_engine, market_data
