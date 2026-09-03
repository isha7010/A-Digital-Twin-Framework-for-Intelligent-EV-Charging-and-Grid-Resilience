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
    HybridPSONSGAIIController,
)
from main import run_scenario_comparison, run_stress_sweep


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


def test_hybrid_pso_nsga2_controller_runs_and_records_history():
    cfg = make_cfg()
    controller = HybridPSONSGAIIController(population_size=6, generations=2, seed=11)
    sim = Simulation(cfg, controller)
    summary = sim.run()
    assert summary["evs_departed"] >= 0
    assert controller.history
    assert all(len(objective) == 4 for objective in controller.history)


def test_hybrid_controller_is_registered_for_comparison():
    table = run_scenario_comparison(
        controller_names=["hybrid_pso_nsga2"],
        scenario_names=["normal"],
        base_num_evs=10,
        horizon_hours=2,
    )
    assert table[0]["controller"] == "hybrid_pso_nsga2"


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


def test_stress_sweep_covers_scenarios_controllers_and_seeds():
    table = run_stress_sweep(
        controller_names=["edf", "hybrid_pso_nsga2"],
        scenario_names=["normal", "low_renewable"],
        seeds=[3, 4],
        base_num_evs=8,
        horizon_hours=2,
    )
    assert len(table) == 8
    assert {row["seed"] for row in table} == {3, 4}
    assert {row["scenario"] for row in table} == {"normal", "low_renewable"}
    assert {row["controller"] for row in table} == {
        "earliest_deadline_first", "hybrid_pso_nsga2"
    }


def test_stress_sweep_is_reproducible():
    kwargs = {
        "controller_names": ["edf"],
        "scenario_names": ["grid_constraint"],
        "seeds": [19],
        "base_num_evs": 8,
        "horizon_hours": 2,
    }
    assert run_stress_sweep(**kwargs) == run_stress_sweep(**kwargs)


def test_clean_telemetry_produces_no_security_alerts():
    cfg = make_cfg()
    cfg.telemetry_noise_std = 0.0
    cfg.telemetry_dropout_prob = 0.0
    summary = Simulation(cfg, UncontrolledController()).run()
    assert summary["telemetry_alerts"] == 0


def test_power_spike_attack_is_detected():
    cfg = make_cfg()
    cfg.telemetry_attack_type = "power_spike"
    cfg.telemetry_attack_probability = 1.0
    sim = Simulation(cfg, UncontrolledController())
    summary = sim.run()
    assert summary["telemetry_alerts"] > 0
    assert summary["high_severity_telemetry_alerts"] > 0
    assert any(alert["type"] == "invalid_power_kw" for alert in sim.security_alert_log)


if __name__ == "__main__":
    test_uncontrolled_runs_and_produces_metrics()
    test_edf_respects_grid_capacity_more_than_uncontrolled()
    test_ev_soc_never_exceeds_bounds()
    test_pso_controller_runs_and_returns_decisions()
    test_nsga2_controller_runs_and_returns_decisions()
    test_pso_controller_accepts_weighted_objective()
    test_run_scenario_comparison_returns_table()
    print("All tests passed.")
