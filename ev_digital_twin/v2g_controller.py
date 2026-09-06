"""Coordinated bidirectional charging controllers for Phase 8."""


class MultiAgentV2GController:
    """Coordinate EV agents around grid headroom, price, and SOC reserves.

    Each V2G-capable EV is treated as an agent with an individual reserve and
    deadline. Charging agents receive remaining headroom fairly; discharging
    agents are selected by highest available SOC when grid support is needed.
    """

    name = "multi_agent_v2g"

    def __init__(self, reserve_soc: float = 0.30, support_threshold: float = 0.85,
                 max_discharge_fraction: float = 0.5):
        self.reserve_soc = reserve_soc
        self.support_threshold = support_threshold
        self.max_discharge_fraction = max(0.0, min(1.0, max_discharge_fraction))
        self.history = []

    def decide(self, twin) -> dict:
        active = [ev for ev in twin.evs.values() if ev.connected_station is not None]
        if not active:
            return {}

        reserve_soc = getattr(twin.cfg, "v2g_reserve_soc", self.reserve_soc)
        support_threshold = getattr(twin.cfg, "v2g_support_threshold", self.support_threshold)
        discharge_fraction = getattr(twin.cfg, "v2g_max_discharge_fraction", self.max_discharge_fraction)
        support_needed = twin.grid.base_load_mw >= twin.grid.capacity_mw * support_threshold
        v2g_agents = [ev for ev in active if ev.v2g_participant and ev.soc > reserve_soc]
        decisions = {}
        exported_kw = 0.0

        if support_needed:
            for ev in sorted(v2g_agents, key=lambda item: item.soc, reverse=True):
                available_kw = min(ev.max_power_kw * discharge_fraction,
                                    max(0.0, (ev.soc - reserve_soc) * ev.battery_kwh /
                                        max(twin.dt_hours, 0.001)))
                if available_kw > 0:
                    decisions[ev.ev_id] = -available_kw
                    exported_kw += available_kw

        remaining_kw = max(0.0, (twin.grid.capacity_mw - twin.grid.base_load_mw) * 1000.0 + exported_kw)
        charging_agents = [ev for ev in active if ev.soc < ev.departure_soc and ev.ev_id not in decisions]
        charging_agents.sort(key=lambda item: (item.departure_deadline_h, item.soc))
        for ev in charging_agents:
            requested_kw = min(ev.max_power_kw, ev.energy_needed_kwh() /
                               max(ev.departure_deadline_h - twin.sim_time_h, 0.5) /
                               max(ev.efficiency, 0.001))
            power_kw = min(requested_kw, remaining_kw)
            decisions[ev.ev_id] = max(0.0, power_kw)
            remaining_kw -= power_kw

        self.history.append({
            "time_h": twin.sim_time_h,
            "support_needed": support_needed,
            "agents": len(active),
            "discharging_agents": sum(1 for power in decisions.values() if power < 0),
            "charging_agents": sum(1 for power in decisions.values() if power > 0),
        })
        return decisions


V2GController = MultiAgentV2GController
