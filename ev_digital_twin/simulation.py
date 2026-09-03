"""
Closed-loop simulation workflow (spec section 15), baseline version:

  1. Initialize digital twin
  2. Generate EV arrivals            (built into DigitalTwin)
  3. Generate IoT telemetry
  4. (Validation / anomaly detection - to be added in a later phase)
  5. Run controller -> charging decisions
  6. Apply decisions to the digital twin
  7. Advance one time step
  8. Record metrics
  9. Repeat until horizon ends
"""

from .digital_twin import DigitalTwin
from .telemetry import TelemetrySimulator
from .metrics import MetricsRecorder
from .security import TelemetryAttackSimulator, TelemetrySecurityMonitor


class Simulation:
    def __init__(self, cfg, controller):
        self.cfg = cfg
        self.controller = controller
        self.twin = DigitalTwin(cfg)
        self.telemetry_sim = TelemetrySimulator(cfg)
        self.metrics = MetricsRecorder()
        self.telemetry_log = []
        self.security_alert_log = []
        self.attack_simulator = TelemetryAttackSimulator(cfg)
        self.security_monitor = TelemetrySecurityMonitor(cfg) if cfg.telemetry_security_enabled else None
        self.step_index = 0

    def run(self, verbose: bool = False):
        while not self.twin.is_finished():
            # Telemetry is generated for observability / future anomaly
            # detection hooks; the baseline controller reads twin state
            # directly for now.
            messages = self.telemetry_sim.generate(self.twin, self.step_index)
            messages = self.attack_simulator.apply(messages, self.step_index)
            self.telemetry_log.append(messages)
            if self.security_monitor is not None:
                alerts = self.security_monitor.inspect(messages, self.twin, self.step_index)
                self.security_alert_log.extend(alerts)
                self.metrics.record_security_alerts(alerts)

            self.twin._admit_arrivals()
            self.twin.update_environment()
            decisions = self.controller.decide(self.twin)
            ev_load_mw = self.twin.apply_charging_decisions(decisions)
            self.twin._release_departures()
            self.metrics.record_step(self.twin, ev_load_mw)

            if verbose and self.step_index % 8 == 0:
                print(f"t={self.twin.sim_time_h:5.2f}h  "
                      f"active_evs={len(self.twin.evs):3d}  "
                      f"ev_load={ev_load_mw:6.3f}MW  "
                      f"price=${self.twin.grid.current_price:.2f}/kWh")

            self.twin.sim_time_h += self.twin.dt_hours
            self.step_index += 1

        return self.metrics.summary(self.twin)
