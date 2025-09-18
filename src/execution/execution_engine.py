from __future__ import annotations
from typing import Dict, Any
from datetime import datetime

from ..market.base import MarketClient
from ..risk.risk_manager import RiskManager


class ExecutionEngine:
    def __init__(self, pzu: MarketClient | None, bm: MarketClient | None, risk: RiskManager, logger):
        self.pzu = pzu
        self.bm = bm
        self.risk = risk
        self.log = logger

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

        self.risk.reserve_for_order(side, volume_mwh)
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
            return res
        finally:
            self.risk.release_order()
