"""Threaded real-time execution for the digital twin."""

import copy
import threading

from .metrics import MetricsRecorder
from .security import TelemetryAttackSimulator, TelemetrySecurityMonitor
from .telemetry import TelemetrySimulator


def _snapshot_twin(twin):
    """Read snapshots from current twins and older hot-reloaded instances."""
    snapshot_method = getattr(twin, "get_state_snapshot", None)
    if snapshot_method is not None:
        return snapshot_method()
    return {
        "time_h": round(twin.sim_time_h, 3),
        "grid": {
            "base_load_mw": round(twin.grid.base_load_mw, 4),
            "ev_load_mw": round(twin.grid.ev_load_mw, 4),
            "v2g_export_mw": round(getattr(twin.grid, "v2g_export_mw", 0.0), 4),
            "net_load_mw": round(twin.grid.net_load_mw(), 4),
            "capacity_mw": round(twin.grid.capacity_mw, 4),
            "solar_mw": round(twin.solar_mw, 4),
        },
        "stations": [
            {
                "station_id": station.station_id,
                "location": station.location,
                "available": station.available,
                "occupancy": dict(station.connector_occupancy),
                "power_kw": round(station.total_power_kw(), 3),
            }
            for station in twin.stations.values()
        ],
        "evs": [
            {
                "ev_id": ev.ev_id,
                "soc": round(ev.soc, 4),
                "state": ev.state,
                "station": ev.connected_station,
                "connector": ev.connected_connector,
                "v2g_participant": ev.v2g_participant,
            }
            for ev in twin.evs.values()
        ],
    }


class RealtimeState:
    """Thread-safe live state shared by the runner and dashboard."""

    def __init__(self, twin, controller, metrics=None):
        self.lock = threading.Lock()
        self.twin = twin
        self.controller = controller
        self.metrics = metrics or MetricsRecorder()
        self.running = False
        self.current_step = 0
        self.pending_changes = {}
        self.last_summary = {}

    def snapshot(self):
        with self.lock:
            return {
                "running": self.running,
                "current_step": self.current_step,
                "sim_time_h": self.twin.sim_time_h,
                "summary": dict(self.last_summary),
                "state": _snapshot_twin(self.twin),
            }


class RealtimeRunner:
    """Advance a digital twin on a background thread at fixed intervals."""

    def __init__(self, cfg, controller, tick_seconds=0.25):
        self.cfg = cfg
        self.tick_seconds = max(0.0, tick_seconds)
        from .digital_twin import DigitalTwin
        self.state = RealtimeState(DigitalTwin(cfg), controller)
        self.telemetry_sim = TelemetrySimulator(cfg)
        self.attack_simulator = TelemetryAttackSimulator(cfg)
        self.security_monitor = TelemetrySecurityMonitor(cfg) if cfg.telemetry_security_enabled else None
        self.telemetry_log = []
        self.security_alert_log = []
        self._stop_event = threading.Event()
        self._thread = None

    def queue_changes(self, **changes):
        """Queue controller/config changes for the next tick boundary."""
        with self.state.lock:
            self.state.pending_changes.update(copy.deepcopy(changes))

    def _apply_pending_changes(self):
        changes = self.state.pending_changes
        self.state.pending_changes = {}
        if "controller" in changes:
            self.state.controller = changes["controller"]
        config_changes = changes.get("config", {})
        if "v2g_rate" in changes:
            config_changes["v2g_participation_rate"] = changes["v2g_rate"]
        for name, value in config_changes.items():
            if not hasattr(self.state.twin.cfg, name):
                continue
            setattr(self.state.twin.cfg, name, value)
            if name == "grid_capacity_mw":
                self.state.twin.grid.capacity_mw = value
            elif name == "grid_base_load_mw":
                self.state.twin.grid.base_load_mw = value
            elif name == "solar_capacity_mw":
                self.state.twin.cfg.solar_capacity_mw = value

    def tick(self):
        """Run exactly one controller/environment step at a tick boundary."""
        with self.state.lock:
            if self.state.twin.is_finished():
                self.state.running = False
                self.state.last_summary = self.state.metrics.summary(self.state.twin)
                return False
            self._apply_pending_changes()
            step_index = self.state.current_step
            twin = self.state.twin
            messages = self.telemetry_sim.generate(twin, step_index)
            messages = self.attack_simulator.apply(messages, step_index)
            self.telemetry_log.append(messages)
            if self.security_monitor is not None:
                alerts = self.security_monitor.inspect(messages, twin, step_index)
                self.security_alert_log.extend(alerts)
                self.state.metrics.record_security_alerts(alerts)

            twin._admit_arrivals()
            twin.update_environment()
            decisions = self.state.controller.decide(twin)
            ev_load_mw = twin.step(decisions)

            # DigitalTwin.step advances time; metrics use the same pre-step
            # timestamp as the batch Simulation recorder.
            twin.sim_time_h -= twin.dt_hours
            self.state.metrics.record_step(twin, ev_load_mw)
            twin.sim_time_h += twin.dt_hours
            self.state.current_step += 1
            self.state.last_summary = self.state.metrics.summary(twin)
            return True

    def _run_loop(self):
        with self.state.lock:
            self.state.running = True
        while not self._stop_event.is_set():
            if not self.tick():
                break
            if self._stop_event.wait(self.tick_seconds):
                break
        with self.state.lock:
            self.state.running = False
            self.state.last_summary = self.state.metrics.summary(self.state.twin)

    def start(self):
        with self.state.lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="ev-digital-twin", daemon=True)
            self._thread.start()

    def stop(self, join=True):
        self._stop_event.set()
        with self.state.lock:
            self.state.running = False
        if join and self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=max(1.0, self.tick_seconds * 4.0))

    def wait_until_finished(self, timeout=30.0):
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        return not self.is_running()

    def is_running(self):
        with self.state.lock:
            return self.state.running

    def summary(self):
        with self.state.lock:
            return self.state.metrics.summary(self.state.twin)

    def snapshot(self):
        return self.state.snapshot()
