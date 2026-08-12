"""Electric vehicle state model (spec section 5.1)."""

from dataclasses import dataclass


@dataclass
class EV:
    ev_id: str
    battery_kwh: float
    soc: float                  # 0.0 - 1.0
    min_soc: float
    departure_soc: float
    arrival_time_h: float
    departure_deadline_h: float
    max_power_kw: float
    efficiency: float
    priority: int = 1           # 1 = normal, higher = more urgent
    v2g_participant: bool = False
    connected_station: str = None
    connected_connector: int = None
    state: str = "waiting"      # waiting | charging | idle | departed | v2g_discharging

    def energy_needed_kwh(self) -> float:
        """Energy required to reach the departure SOC target."""
        deficit = max(0.0, self.departure_soc - self.soc)
        return deficit * self.battery_kwh

    def is_deadline_met(self) -> bool:
        return self.soc >= self.departure_soc

    def apply_charging(self, power_kw: float, dt_hours: float) -> float:
        """
        Apply `power_kw` of charging for `dt_hours`.
        Returns the actual energy drawn from the grid (kWh), accounting
        for charger efficiency and clipping to physical limits.
        """
        power_kw = max(0.0, min(power_kw, self.max_power_kw))
        max_addable_kwh = max(0.0, (1.0 - self.soc) * self.battery_kwh)
        energy_to_battery = min(power_kw * dt_hours * self.efficiency, max_addable_kwh)
        energy_from_grid = energy_to_battery / self.efficiency if self.efficiency > 0 else 0.0
        self.soc = min(1.0, self.soc + energy_to_battery / self.battery_kwh)
        self.state = "charging" if energy_from_grid > 0 else self.state
        return energy_from_grid

    def apply_discharge(self, power_kw: float, dt_hours: float) -> float:
        """
        V2G discharge. Returns energy delivered TO the grid (kWh).
        Will not discharge below min_soc.
        """
        if not self.v2g_participant:
            return 0.0
        power_kw = max(0.0, min(power_kw, self.max_power_kw))
        min_energy_kwh = self.min_soc * self.battery_kwh
        max_removable_kwh = max(0.0, self.soc * self.battery_kwh - min_energy_kwh)
        energy_from_battery = min(power_kw * dt_hours, max_removable_kwh)
        energy_to_grid = energy_from_battery * self.efficiency
        self.soc = max(0.0, self.soc - energy_from_battery / self.battery_kwh)
        self.state = "v2g_discharging" if energy_to_grid > 0 else self.state
        return energy_to_grid

    def to_telemetry_dict(self, timestamp: str) -> dict:
        return {
            "ev_id": self.ev_id,
            "timestamp": timestamp,
            "soc": round(self.soc * 100, 1),
            "battery_kwh": self.battery_kwh,
            "state": self.state,
        }
