"""
Baseline entry point.

Usage:
    python main.py
    python main.py --controller edf --evs 100 --hours 24

Runs the closed-loop digital twin simulation with a chosen baseline
controller and prints/saves summary metrics. This is the "baseline"
phase of the recommended build order in the project spec:

    Digital Twin -> baseline -> PSO -> NSGA-II -> hybrid PSO-NSGA-II
    -> scenario/stress testing -> anomaly/security -> V2G/multi-agent
    -> RL -> final dashboard
"""

import argparse
import csv
import os

from ev_digital_twin.config import SimulationConfig
from ev_digital_twin.scenarios import build_config
from ev_digital_twin.simulation import Simulation
from ev_digital_twin.baseline_controller import (
    UncontrolledController,
    EarliestDeadlineFirstController,
    PSOController,
    NSGAIIController,
)


CONTROLLERS = {
    "uncontrolled": UncontrolledController,
    "edf": EarliestDeadlineFirstController,
    "pso": PSOController,
    "nsga2": NSGAIIController,
}


def parse_args():
    p = argparse.ArgumentParser(description="Run the EV digital twin baseline simulation")
    p.add_argument("--controller", choices=CONTROLLERS.keys(), default="uncontrolled")
    p.add_argument("--evs", type=int, default=None, help="number of EVs")
    p.add_argument("--hours", type=float, default=None, help="simulation horizon in hours")
    p.add_argument("--seed", type=int, default=None, help="random seed")
    p.add_argument("--out", type=str, default="outputs/metrics.csv")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def run_scenario_comparison(controller_names, scenario_names, base_num_evs=50, horizon_hours=24):
    rows = []
    for scenario_name in scenario_names:
        cfg = build_config(scenario_name, base_num_evs=base_num_evs, seed=42)
        cfg.horizon_hours = horizon_hours
        for controller_name in controller_names:
            controller = CONTROLLERS[controller_name]()
            sim = Simulation(cfg, controller)
            summary = sim.run(verbose=False)
            row = {
                "scenario": scenario_name,
                "controller": controller.name,
                "total_electricity_cost_usd": summary.get("total_electricity_cost_usd", 0.0),
                "total_carbon_emissions_kg": summary.get("total_carbon_emissions_kg", 0.0),
                "peak_grid_load_mw": summary.get("peak_grid_load_mw", 0.0),
                "steps_over_capacity": summary.get("steps_over_capacity", 0),
                "pct_evs_met_required_soc": summary.get("pct_evs_met_required_soc", 0.0),
            }
            rows.append(row)
    return rows


def main():
    args = parse_args()
    cfg = SimulationConfig()
    if args.evs is not None:
        cfg.num_evs = args.evs
    if args.hours is not None:
        cfg.horizon_hours = args.hours
    if args.seed is not None:
        cfg.random_seed = args.seed

    controller = CONTROLLERS[args.controller]()
    sim = Simulation(cfg, controller)
    summary = sim.run(verbose=args.verbose)

    print(f"\n=== Simulation summary (controller={controller.name}) ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if sim.metrics.rows:
        with open(args.out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=sim.metrics.rows[0].keys())
            writer.writeheader()
            writer.writerows(sim.metrics.rows)
        print(f"\nPer-step metrics written to {args.out}")


if __name__ == "__main__":
    main()
