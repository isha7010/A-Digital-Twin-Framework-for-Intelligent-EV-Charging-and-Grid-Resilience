"""
The Digital Twin: a stateful simulation environment whose variables evolve
over time according to EV arrivals, charging decisions, grid demand,
renewable generation and failures (spec section 5).
"""

import random
from .ev import EV
from .charging_station import ChargingStation
from .grid import GridState, base_load_profile, solar_generation_mw, electricity_price


class DigitalTwin:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rng = random.Random(cfg.random_seed)

        self.sim_time_h = 0.0
        self.dt_hours = cfg.time_step_minutes / 60.0

        self.stations = self._build_stations()
        self.grid = GridState(
            base_load_mw=cfg.grid_base_load_mw,
            capacity_mw=cfg.grid_capacity_mw,
            carbon_intensity_base=cfg.carbon_intensity_base,
        )
        self.solar_mw = 0.0

        self.evs = {}                 # ev_id -> EV, only EVs currently on-site
        self._pending_arrivals = self._generate_arrival_schedule()
        self._next_ev_index = 0
        self.departed_log = []        # list of dicts summarizing departed EVs

    # ---------------------------------------------------------- setup ----

    def _build_stations(self):
        stations = {}
        for i in range(self.cfg.num_stations):
            sid = f"CS_{i:03d}"
            stations[sid] = ChargingStation(
                station_id=sid,
                location=f"zone_{i % 5}",
                num_connectors=self.cfg.connectors_per_station,
                max_power_kw=self.cfg.station_max_power_kw,
            )
        return stations

    def _generate_arrival_schedule(self):
        """Pre-generate all EV arrivals for the simulation horizon."""
        arrivals = []
        lo, hi = self.cfg.ev_arrival_hour_range
        for i in range(self.cfg.num_evs):
            arrival_h = self.rng.uniform(lo, hi)
            stay_h = self.rng.uniform(*self.cfg.ev_stay_hours_range)
            battery = self.rng.uniform(*self.cfg.ev_battery_kwh_range)
            max_power = self.rng.uniform(*self.cfg.ev_max_power_kw_range)
            start_soc = self.rng.uniform(0.15, 0.6)
            v2g = self.rng.random() < self.cfg.v2g_participation_rate
            ev = EV(
                ev_id=f"EV_{i:03d}",
                battery_kwh=round(battery, 1),
                soc=round(start_soc, 3),
                min_soc=self.cfg.ev_min_soc,
                departure_soc=self.cfg.ev_departure_soc,
                arrival_time_h=round(arrival_h, 2),
                departure_deadline_h=round(arrival_h + stay_h, 2),
                max_power_kw=round(max_power, 1),
                efficiency=self.cfg.ev_charging_efficiency,
                v2g_participant=v2g,
            )
            arrivals.append(ev)
        arrivals.sort(key=lambda e: e.arrival_time_h)
        return arrivals

    # -------------------------------------------------------- stepping ----

    def _admit_arrivals(self):
        """Move any EVs whose arrival time has passed into the active set
        and connect them to a free connector if one is available."""
        while (self._next_ev_index < len(self._pending_arrivals)
               and self._pending_arrivals[self._next_ev_index].arrival_time_h <= self.sim_time_h):
            ev = self._pending_arrivals[self._next_ev_index]
            self._next_ev_index += 1
            self.evs[ev.ev_id] = ev
            self._try_connect(ev)

    def _try_connect(self, ev: EV):
        for station in self.stations.values():
            idx = station.connect(ev.ev_id)
            if idx is not None:
                ev.connected_station = station.station_id
                ev.connected_connector = idx
                ev.state = "idle"
                return True
        ev.state = "waiting"  # no free connector right now
        return False

    def _release_departures(self):
        """Remove EVs whose departure deadline has passed and free their connector."""
        for ev_id in list(self.evs.keys()):
            ev = self.evs[ev_id]
            if self.sim_time_h >= ev.departure_deadline_h:
                if ev.connected_station is not None:
                    self.stations[ev.connected_station].disconnect(ev.connected_connector)
                ev.state = "departed"
                self.departed_log.append({
                    "ev_id": ev.ev_id,
                    "final_soc": ev.soc,
                    "deadline_met": ev.is_deadline_met(),
                    "departure_time_h": self.sim_time_h,
                })
                del self.evs[ev_id]

    def update_environment(self):
        """Refresh grid base load, solar generation and price for this step."""
        hour = self.sim_time_h % 24.0
        self.grid.base_load_mw = base_load_profile(hour, self.cfg.grid_base_load_mw)
        self.solar_mw = solar_generation_mw(hour, self.cfg.solar_capacity_mw)
        self.grid.current_price = electricity_price(hour, self.cfg)
        renewable_fraction = 0.0
        total_demand = self.grid.total_load_mw()
        if total_demand > 0:
            renewable_fraction = min(1.0, self.solar_mw / total_demand)
        self.grid.update_carbon_intensity(renewable_fraction)

    def apply_charging_decisions(self, decisions: dict) -> float:
        """
        decisions: {ev_id: power_kw}. Positive = charge, negative = V2G
        discharge (only honored if the EV is a V2G participant).
        Returns total EV load in MW added to the grid this step.
        """
        total_energy_kwh = 0.0
        for ev_id, power_kw in decisions.items():
            ev = self.evs.get(ev_id)
            if ev is None or ev.connected_station is None:
                continue
            station = self.stations[ev.connected_station]
            cap = station.per_connector_power_limit()
            power_kw = max(-cap, min(cap, power_kw))
            if power_kw >= 0:
                energy = ev.apply_charging(power_kw, self.dt_hours)
                total_energy_kwh += energy
            else:
                energy_to_grid = ev.apply_discharge(-power_kw, self.dt_hours)
                total_energy_kwh -= energy_to_grid
            station.power_delivered_kw[ev.connected_connector] = power_kw

        self.grid.ev_load_mw = max(0.0, total_energy_kwh / self.dt_hours / 1000.0)
        return self.grid.ev_load_mw

    def step(self, decisions: dict):
        """Advance the simulation by one time step given controller decisions."""
        self._admit_arrivals()
        self.update_environment()
        ev_load_mw = self.apply_charging_decisions(decisions)
        self._release_departures()
        self.sim_time_h += self.dt_hours
        return ev_load_mw

    def is_finished(self) -> bool:
        horizon = self.cfg.horizon_hours
        return self.sim_time_h >= horizon and self._next_ev_index >= len(self._pending_arrivals)

    def active_ev_ids(self):
        return list(self.evs.keys())
