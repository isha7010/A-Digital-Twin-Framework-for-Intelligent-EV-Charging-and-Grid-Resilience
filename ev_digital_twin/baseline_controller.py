"""
Baseline charging strategy: uncontrolled ("charge immediately at max
power") charging. This is the reference point every later optimizer
(PSO, NSGA-II, hybrid, RL) should be compared against.
"""


class UncontrolledController:
    """Every connected EV charges at its maximum power until full."""

    name = "uncontrolled"

    def decide(self, twin) -> dict:
        decisions = {}
        for ev in twin.evs.values():
            if ev.connected_station is None:
                continue
            if ev.soc >= ev.departure_soc:
                decisions[ev.ev_id] = 0.0
            else:
                decisions[ev.ev_id] = ev.max_power_kw
        return decisions


class EarliestDeadlineFirstController:
    """
    A slightly smarter rule-based baseline: EVs with the soonest departure
    deadline get charging priority when the grid is near capacity.
    Useful as a second reference point before introducing PSO-NSGA-II.
    """

    name = "earliest_deadline_first"

    def __init__(self, headroom_mw: float = None):
        self.headroom_mw = headroom_mw

    def decide(self, twin) -> dict:
        active = [ev for ev in twin.evs.values()
                  if ev.connected_station is not None and ev.soc < ev.departure_soc]
        active.sort(key=lambda ev: ev.departure_deadline_h)

        capacity_mw = self.headroom_mw if self.headroom_mw is not None else twin.grid.capacity_mw
        remaining_mw = max(0.0, capacity_mw - twin.grid.base_load_mw)
        remaining_kw = remaining_mw * 1000.0

        decisions = {}
        for ev in active:
            power = min(ev.max_power_kw, remaining_kw)
            power = max(0.0, power)
            decisions[ev.ev_id] = power
            remaining_kw -= power
        return decisions
