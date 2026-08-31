import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ev_digital_twin.config import SimulationConfig
from ev_digital_twin.simulation import Simulation
from ev_digital_twin.baseline_controller import (
    UncontrolledController,
    EarliestDeadlineFirstController,
    PSOController,
    NSGAIIController,
)
from main import run_scenario_comparison


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


def test_pso_controller_runs_and_returns_decisions():
    cfg = make_cfg()
    sim = Simulation(cfg, PSOController())
    summary = sim.run()
    assert summary["evs_departed"] >= 0
    assert "total_electricity_cost_usd" in summary
    assert summary["total_electricity_cost_usd"] >= 0


def test_nsga2_controller_runs_and_returns_decisions():
    cfg = make_cfg()
    sim = Simulation(cfg, NSGAIIController())
    summary = sim.run()
    assert summary["evs_departed"] >= 0
    assert "peak_grid_load_mw" in summary
    assert summary["peak_grid_load_mw"] >= 0


def test_pso_controller_accepts_weighted_objective():
    cfg = make_cfg()
    sim = Simulation(cfg, PSOController(weights={"cost": 0.5, "carbon": 0.3, "overload": 1.5, "soc": 2.0}))
    summary = sim.run()
    assert summary["total_electricity_cost_usd"] >= 0
    assert len(sim.controller.history) > 0


def test_run_scenario_comparison_returns_table():
    table = run_scenario_comparison(
        controller_names=["uncontrolled", "edf"],
        scenario_names=["normal", "grid_constraint"],
        base_num_evs=20,
        horizon_hours=6,
    )
    assert len(table) > 0
    assert "scenario" in table[0]


if __name__ == "__main__":
    test_uncontrolled_runs_and_produces_metrics()
    test_edf_respects_grid_capacity_more_than_uncontrolled()
    test_ev_soc_never_exceeds_bounds()
    test_pso_controller_runs_and_returns_decisions()
    test_nsga2_controller_runs_and_returns_decisions()
    test_pso_controller_accepts_weighted_objective()
    test_run_scenario_comparison_returns_table()
    print("All tests passed.")
