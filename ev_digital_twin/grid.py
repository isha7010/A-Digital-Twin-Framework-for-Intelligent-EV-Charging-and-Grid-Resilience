"""Grid and renewable generation state models (spec sections 5.3-5.4)."""

import math
from dataclasses import dataclass


@dataclass
class GridState:
    base_load_mw: float
    capacity_mw: float
    carbon_intensity_base: float
    ev_load_mw: float = 0.0
    v2g_export_mw: float = 0.0
    current_price: float = 0.0
    carbon_intensity: float = 0.0

    def total_load_mw(self) -> float:
        return self.base_load_mw + self.ev_load_mw

    def net_load_mw(self) -> float:
        return self.base_load_mw + self.ev_load_mw - self.v2g_export_mw

    def is_over_capacity(self) -> bool:
        return self.net_load_mw() > self.capacity_mw

    def update_carbon_intensity(self, renewable_fraction: float):
        # More renewable share on the grid -> lower effective carbon intensity.
        self.carbon_intensity = self.carbon_intensity_base * (1.0 - 0.6 * renewable_fraction)


def base_load_profile(hour_of_day: float, base_mw: float) -> float:
    """Simple daily base-load curve: morning + evening peaks."""
    morning = math.exp(-((hour_of_day - 8.0) ** 2) / (2 * 2.0 ** 2))
    evening = math.exp(-((hour_of_day - 19.0) ** 2) / (2 * 2.5 ** 2))
    factor = 0.7 + 0.5 * morning + 0.6 * evening
    return base_mw * factor


def solar_generation_mw(hour_of_day: float, capacity_mw: float) -> float:
    """Simple bell-curve solar profile, zero at night, peak at solar noon."""
    if hour_of_day < 6 or hour_of_day > 19:
        return 0.0
    x = (hour_of_day - 12.5) / 5.0
    return max(0.0, capacity_mw * math.exp(-(x ** 2)))


def electricity_price(hour_of_day: float, cfg) -> float:
    on_lo, on_hi = cfg.on_peak_hours
    mid_lo, mid_hi = cfg.mid_peak_hours
    if on_lo <= hour_of_day < on_hi:
        return cfg.price_on_peak
    if mid_lo <= hour_of_day < mid_hi:
        return cfg.price_mid_peak
    return cfg.price_off_peak
