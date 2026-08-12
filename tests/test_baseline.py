import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ev_digital_twin.config import SimulationConfig
from ev_digital_twin.simulation import Simulation
from ev_digital_twin.baseline_controller import (
    UncontrolledController,
    EarliestDeadlineFirstController,
)


def make_cfg():
    cfg = SimulationConfig()
    cfg.num_evs = 20
    cfg.num_stations = 6
    cfg.horizon_hours = 6
    return cfg


def test_uncontrolled_runs_and_produces_metrics():
    cfg = make_cfg()
    sim = Simulation(cfg, UncontrolledController())
    summary = sim.run()
    assert summary["evs_departed"] >= 0
    assert len(sim.metrics.rows) > 0
    assert summary["total_electricity_cost_usd"] >= 0


def test_edf_respects_grid_capacity_more_than_uncontrolled():
    cfg = make_cfg()
    sim_u = Simulation(cfg, UncontrolledController())
    summary_u = sim_u.run()

    cfg2 = make_cfg()
    sim_e = Simulation(cfg2, EarliestDeadlineFirstController())
    summary_e = sim_e.run()

    # EDF should not create more capacity violations than uncontrolled charging.
    assert summary_e["steps_over_capacity"] <= summary_u["steps_over_capacity"]


def test_ev_soc_never_exceeds_bounds():
    cfg = make_cfg()
    sim = Simulation(cfg, UncontrolledController())
    sim.run()
    for record in sim.twin.departed_log:
        assert 0.0 <= record["final_soc"] <= 1.0


if __name__ == "__main__":
    test_uncontrolled_runs_and_produces_metrics()
    test_edf_respects_grid_capacity_more_than_uncontrolled()
    test_ev_soc_never_exceeds_bounds()
    print("All tests passed.")
