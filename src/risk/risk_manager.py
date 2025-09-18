from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple


@dataclass
class BatteryConfig:
    capacity_mwh: float
    power_mw: float
    soc_initial: float
    round_trip_efficiency: float


@dataclass
class RiskConfig:
    max_position_mwh: float
    max_order_mwh: float
    min_price_eur_mwh: float
    max_price_eur_mwh: float
    max_open_orders: int


class RiskManager:
    def __init__(self, battery: BatteryConfig, risk: RiskConfig):
        self.battery = battery
        self.risk = risk
        self.soc = max(0.0, min(1.0, battery.soc_initial))
        self.open_orders = 0

    def available_energy_mwh(self) -> Tuple[float, float]:
        energy = self.soc * self.battery.capacity_mwh
        headroom = (1.0 - self.soc) * self.battery.capacity_mwh
        return energy, headroom

    def validate_order(self, side: str, volume_mwh: float, price: float) -> Tuple[bool, str]:
        if volume_mwh <= 0:
            return False, "volume must be > 0"
        if volume_mwh > self.risk.max_order_mwh:
            return False, "volume exceeds per-order limit"
        if price < self.risk.min_price_eur_mwh or price > self.risk.max_price_eur_mwh:
            return False, "price out of bounds"
        if self.open_orders >= self.risk.max_open_orders:
            return False, "too many open orders"
        discharge, charge = self.available_energy_mwh()
        if side.upper() == "SELL" and volume_mwh > discharge:
            return False, "insufficient energy to discharge"
        if side.upper() == "BUY" and volume_mwh > charge:
            return False, "insufficient headroom to charge"
        return True, "ok"

    def reserve_for_order(self, side: str, volume_mwh: float) -> None:
        self.open_orders += 1
        if side.upper() == "BUY":
            # charging increases SOC after fill; reserve headroom now
            self.soc = min(1.0, self.soc + (volume_mwh / self.battery.capacity_mwh) * self.battery.round_trip_efficiency)
        else:
            # discharging decreases SOC
            self.soc = max(0.0, self.soc - (volume_mwh / self.battery.capacity_mwh))

    def release_order(self) -> None:
        self.open_orders = max(0, self.open_orders - 1)
