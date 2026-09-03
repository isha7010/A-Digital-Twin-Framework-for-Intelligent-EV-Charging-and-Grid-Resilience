"""Evaluation metrics collection (spec section 18, baseline subset)."""

from dataclasses import dataclass, field


class MetricsRecorder:
    def __init__(self):
        self.rows = []
        self.security_alerts = []

    def record_security_alerts(self, alerts):
        self.security_alerts.extend(alerts)

    def record_step(self, twin, ev_load_mw: float):
        cost_this_step = ev_load_mw * 1000.0 * twin.dt_hours * twin.grid.current_price
        carbon_this_step = ev_load_mw * 1000.0 * twin.dt_hours * twin.grid.carbon_intensity
        self.rows.append({
            "time_h": round(twin.sim_time_h, 3),
            "total_load_mw": round(twin.grid.total_load_mw(), 4),
            "ev_load_mw": round(ev_load_mw, 4),
            "base_load_mw": round(twin.grid.base_load_mw, 4),
            "solar_mw": round(twin.solar_mw, 4),
            "price": round(twin.grid.current_price, 4),
            "carbon_intensity": round(twin.grid.carbon_intensity, 4),
            "active_evs": len(twin.evs),
            "cost_step_usd": round(cost_this_step, 4),
            "carbon_step_kg": round(carbon_this_step, 4),
            "over_capacity": twin.grid.is_over_capacity(),
        })

    def summary(self, twin) -> dict:
        if not self.rows:
            return {}
        total_cost = sum(r["cost_step_usd"] for r in self.rows)
        total_carbon = sum(r["carbon_step_kg"] for r in self.rows)
        peak_load = max(r["total_load_mw"] for r in self.rows)
        over_capacity_steps = sum(1 for r in self.rows if r["over_capacity"])

        n_departed = len(twin.departed_log)
        n_met = sum(1 for d in twin.departed_log if d["deadline_met"])
        pct_met = 100.0 * n_met / n_departed if n_departed else 0.0

        return {
            "total_electricity_cost_usd": round(total_cost, 2),
            "total_carbon_emissions_kg": round(total_carbon, 2),
            "peak_grid_load_mw": round(peak_load, 3),
            "steps_over_capacity": over_capacity_steps,
            "evs_departed": n_departed,
            "pct_evs_met_required_soc": round(pct_met, 1),
            "telemetry_alerts": len(self.security_alerts),
            "high_severity_telemetry_alerts": sum(
                1 for alert in self.security_alerts if alert["severity"] == "high"
            ),
        }
