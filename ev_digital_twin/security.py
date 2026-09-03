"""Telemetry validation, anomaly detection, and attack simulation hooks."""

import copy
import random


class TelemetryAttackSimulator:
    """Optionally mutate telemetry to exercise security detection paths."""

    ATTACK_TYPES = {"soc_spoof", "power_spike", "grid_load_spoof", "replay"}

    def __init__(self, cfg):
        self.attack_type = cfg.telemetry_attack_type
        self.probability = cfg.telemetry_attack_probability
        self.rng = random.Random(cfg.random_seed + 2)
        self.attack_log = []
        self._previous_messages = []

    def apply(self, messages, step_index):
        if self.attack_type not in self.ATTACK_TYPES or self.probability <= 0:
            self._previous_messages = copy.deepcopy(messages)
            return messages

        mutated = copy.deepcopy(messages)
        for message in mutated:
            if self.rng.random() >= self.probability:
                continue
            if self.attack_type == "soc_spoof":
                message["soc"] = 100.0
            elif self.attack_type == "power_spike":
                message["power_kw"] = 10_000.0
            elif self.attack_type == "grid_load_spoof":
                message["grid_load_mw"] = -10.0
            elif self.attack_type == "replay" and self._previous_messages:
                previous = next((item for item in self._previous_messages
                                 if item.get("ev_id") == message.get("ev_id")), None)
                if previous:
                    message.update(previous)
            self.attack_log.append({
                "step": step_index,
                "ev_id": message.get("ev_id"),
                "attack_type": self.attack_type,
            })
        self._previous_messages = copy.deepcopy(messages)
        return mutated


class TelemetrySecurityMonitor:
    """Validate message schemas and flag implausible telemetry changes."""

    REQUIRED_FIELDS = {
        "ev_id", "timestamp", "soc", "battery_kwh", "power_kw",
        "voltage_v", "temperature_c", "grid_load_mw", "solar_mw",
    }

    def __init__(self, cfg):
        self.cfg = cfg
        self.previous = {}
        self.alerts = []

    def inspect(self, messages, twin, step_index):
        step_alerts = []
        seen = set()
        for message in messages:
            ev_id = message.get("ev_id")
            issues = []
            if not self.REQUIRED_FIELDS.issubset(message):
                issues.append("missing_field")
            if ev_id in seen:
                issues.append("duplicate_message")
            seen.add(ev_id)
            ev = twin.evs.get(ev_id)
            if ev is None:
                issues.append("unknown_ev")

            numeric_ranges = {
                "soc": (0.0, 100.0),
                "battery_kwh": (0.1, 2_000.0),
                "power_kw": (-100.0, 100.0),
                "voltage_v": (180.0, 260.0),
                "temperature_c": (-30.0, 100.0),
                "grid_load_mw": (0.0, max(100.0, twin.grid.capacity_mw * 2.0)),
                "solar_mw": (0.0, max(100.0, self.cfg.solar_capacity_mw * 2.0)),
            }
            for field, (minimum, maximum) in numeric_ranges.items():
                value = message.get(field)
                if not isinstance(value, (int, float)) or not minimum <= value <= maximum:
                    issues.append(f"invalid_{field}")

            previous = self.previous.get(ev_id)
            if previous and isinstance(message.get("soc"), (int, float)):
                if abs(message["soc"] - previous.get("soc", message["soc"])) > 20.0:
                    issues.append("soc_jump")
            self.previous[ev_id] = message

            for issue in sorted(set(issues)):
                alert = {
                    "step": step_index,
                    "ev_id": ev_id,
                    "type": issue,
                    "severity": "high" if issue.startswith("invalid_") or issue == "unknown_ev" else "medium",
                }
                step_alerts.append(alert)
                self.alerts.append(alert)
        return step_alerts
