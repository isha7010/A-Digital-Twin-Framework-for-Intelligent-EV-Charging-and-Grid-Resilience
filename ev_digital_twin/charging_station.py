"""Charging station state model (spec section 5.2)."""

from dataclasses import dataclass, field


@dataclass
class ChargingStation:
    station_id: str
    location: str
    num_connectors: int
    max_power_kw: float
    available: bool = True
    connector_occupancy: dict = field(default_factory=dict)   # connector_idx -> ev_id or None
    power_delivered_kw: dict = field(default_factory=dict)    # connector_idx -> kw

    def __post_init__(self):
        if not self.connector_occupancy:
            self.connector_occupancy = {i: None for i in range(self.num_connectors)}
        if not self.power_delivered_kw:
            self.power_delivered_kw = {i: 0.0 for i in range(self.num_connectors)}

    def free_connectors(self):
        if not self.available:
            return []
        return [i for i, occ in self.connector_occupancy.items() if occ is None]

    def connect(self, ev_id: str) -> int:
        """Assign an EV to the first free connector. Returns connector index or None."""
        free = self.free_connectors()
        if not free:
            return None
        idx = free[0]
        self.connector_occupancy[idx] = ev_id
        return idx

    def disconnect(self, connector_idx: int):
        self.connector_occupancy[connector_idx] = None
        self.power_delivered_kw[connector_idx] = 0.0

    def total_power_kw(self) -> float:
        return sum(self.power_delivered_kw.values())

    def per_connector_power_limit(self) -> float:
        active = max(1, self.num_connectors)
        return self.max_power_kw / active
