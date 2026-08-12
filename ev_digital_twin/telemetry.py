"""
IoT telemetry simulation layer (spec section 6).

Generates the messages an actual IoT deployment would produce, with
optional noise and dropout, instead of relying on physical sensors.
"""

import random


class TelemetrySimulator:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rng = random.Random(cfg.random_seed + 1)

    def _noisy(self, value: float) -> float:
        noise = self.rng.gauss(0, self.cfg.telemetry_noise_std) * value
        return value + noise

    def generate(self, twin, sim_step_index: int) -> list:
        """Return a list of telemetry messages for the current step.
        Some messages may be dropped to simulate stale/missing data."""
        messages = []
        hour = twin.sim_time_h % 24.0
        hh = int(hour)
        mm = int(round((hour - hh) * 60))
        timestamp = f"{hh:02d}:{mm:02d}"

        for ev in twin.evs.values():
            if self.rng.random() < self.cfg.telemetry_dropout_prob:
                continue  # dropped message
            station = twin.stations.get(ev.connected_station)
            power_kw = 0.0
            if station is not None and ev.connected_connector is not None:
                power_kw = station.power_delivered_kw.get(ev.connected_connector, 0.0)
            msg = {
                "ev_id": ev.ev_id,
                "timestamp": timestamp,
                "soc": round(self._noisy(ev.soc * 100), 2),
                "battery_kwh": ev.battery_kwh,
                "power_kw": round(self._noisy(power_kw), 2),
                "voltage_v": round(self._noisy(230.0), 1),
                "temperature_c": round(self._noisy(30.0), 1),
                "grid_load_mw": round(self._noisy(twin.grid.total_load_mw()), 3),
                "solar_mw": round(self._noisy(twin.solar_mw), 3),
            }
            messages.append(msg)
        return messages
