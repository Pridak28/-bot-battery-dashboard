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
        # Track SOC reservations: {order_id: soc_delta}
        # Positive delta = charge reservation, negative = discharge reservation
        self.reservations = {}

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

    def reserve_for_order(self, side: str, volume_mwh: float, order_id: str = None) -> str:
        """Reserve SOC headroom/energy for a pending order.

        Parameters
        ----------
        side : str
            Order side ("BUY" or "SELL")
        volume_mwh : float
            Volume to reserve
        order_id : str, optional
            Order ID for tracking. If None, auto-generated.

        Returns
        -------
        str
            Order ID for this reservation

        Notes
        -----
        Correct SOC reservation logic:
        - BUY order (charge): Reserve headroom. SOC increases by charged_energy (no efficiency loss during charge reservation).
          When actually executed, energy goes into battery with charge efficiency.
          For simplicity in reservation, we assume full volume goes in, then apply round-trip efficiency only on discharge.
        - SELL order (discharge): Reserve available energy. SOC decreases by the energy that will be drawn from battery.
          Since we're selling volume_mwh, we need to draw volume_mwh/discharge_efficiency from battery.

        Efficiency split (for round-trip η):
        - Charge efficiency ≈ √η
        - Discharge efficiency ≈ √η
        - Round-trip = charge_eff × discharge_eff = η

        Conservative approach: Reserve full volume for charge, and volume/√η for discharge.
        """
        # Generate order ID if not provided
        if order_id is None:
            order_id = f"order_{self.open_orders + 1}_{id(self)}"

        self.open_orders += 1

        if side.upper() == "BUY":
            # BUY (charging): Reserve headroom for incoming energy
            # Energy stored in battery = volume_mwh × charge_efficiency
            # Using √η as charge efficiency (conservative: assumes some loss during charge)
            charge_efficiency = (self.battery.round_trip_efficiency) ** 0.5
            energy_to_battery = volume_mwh * charge_efficiency
            soc_delta = energy_to_battery / self.battery.capacity_mwh
            self.soc = min(1.0, self.soc + soc_delta)
            self.reservations[order_id] = soc_delta
        else:
            # SELL (discharging): Reserve available energy
            # To deliver volume_mwh, we need to draw more from battery due to discharge losses
            # Energy from battery = volume_mwh / discharge_efficiency
            discharge_efficiency = (self.battery.round_trip_efficiency) ** 0.5
            energy_from_battery = volume_mwh / discharge_efficiency
            soc_delta = -(energy_from_battery / self.battery.capacity_mwh)
            self.soc = max(0.0, self.soc + soc_delta)
            self.reservations[order_id] = soc_delta

        return order_id

    def release_order(self, order_id: str = None) -> None:
        """Release SOC reservation for an order.

        Parameters
        ----------
        order_id : str, optional
            Order ID to release. If None, releases the most recent reservation.
        """
        self.open_orders = max(0, self.open_orders - 1)

        if order_id is None:
            # Release most recent reservation
            if self.reservations:
                order_id = list(self.reservations.keys())[-1]

        if order_id in self.reservations:
            # Reverse the SOC change
            soc_delta = self.reservations[order_id]
            self.soc = max(0.0, min(1.0, self.soc - soc_delta))
            del self.reservations[order_id]
