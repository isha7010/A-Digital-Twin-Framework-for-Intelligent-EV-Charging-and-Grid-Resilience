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
from ev_digital_twin.scenarios import SCENARIOS, build_config
from ev_digital_twin.simulation import Simulation
from ev_digital_twin.baseline_controller import (
    UncontrolledController,
    EarliestDeadlineFirstController,
    PSOController,
    NSGAIIController,
    HybridPSONSGAIIController,
)
from ev_digital_twin.v2g_controller import MultiAgentV2GController
from ev_digital_twin.rl_controller import QLearningController


CONTROLLERS = {
    "uncontrolled": UncontrolledController,
    "edf": EarliestDeadlineFirstController,
    "pso": PSOController,
    "nsga2": NSGAIIController,
    "hybrid_pso_nsga2": HybridPSONSGAIIController,
    "multi_agent_v2g": MultiAgentV2GController,
    "q_learning": QLearningController,
}


def parse_args():
    p = argparse.ArgumentParser(description="Run the EV digital twin baseline simulation")
    p.add_argument("--controller", choices=CONTROLLERS.keys(), default="uncontrolled")
    p.add_argument("--evs", type=int, default=None, help="number of EVs")
    p.add_argument("--hours", type=float, default=None, help="simulation horizon in hours")
    p.add_argument("--seed", type=int, default=None, help="random seed")
    p.add_argument("--out", type=str, default="outputs/metrics.csv")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--scenarios", nargs="+", choices=SCENARIOS.keys(),
                   help="run a Phase 6 scenario stress sweep")
    p.add_argument("--controllers", nargs="+", choices=CONTROLLERS.keys(),
                   help="controllers to evaluate in a stress sweep")
    p.add_argument("--seeds", nargs="+", type=int, default=[42],
                   help="random seeds for a stress sweep")
    p.add_argument("--attack-type", choices=["none", "soc_spoof", "power_spike",
                                              "grid_load_spoof", "replay"], default="none")
    p.add_argument("--attack-probability", type=float, default=0.0,
                   help="probability of attacking each telemetry message")
    p.add_argument("--disable-security", action="store_true",
                   help="disable telemetry validation and anomaly detection")
    p.add_argument("--v2g-rate", type=float, default=None,
                   help="fraction of EVs participating in V2G")
    p.add_argument("--rl-episodes", type=int, default=0,
                   help="training episodes before evaluating q_learning")
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


def run_stress_sweep(controller_names, scenario_names, seeds=(42,),
                     base_num_evs=50, horizon_hours=24, attack_type="none",
                     attack_probability=0.0, security_enabled=True, v2g_rate=0.0,
                     rl_episodes=0):
    """Evaluate every controller/scenario/seed combination.

    Each run gets a freshly built configuration and controller, making the
    returned table suitable for repeatable benchmark comparisons.
    """
    rows = []
    for seed in seeds:
        for scenario_name in scenario_names:
            cfg = build_config(scenario_name, base_num_evs=base_num_evs, seed=seed)
            cfg.horizon_hours = horizon_hours
            cfg.telemetry_attack_type = attack_type
            cfg.telemetry_attack_probability = attack_probability
            cfg.telemetry_security_enabled = security_enabled
            cfg.v2g_participation_rate = max(0.0, min(1.0, v2g_rate))
            for controller_name in controller_names:
                controller = CONTROLLERS[controller_name]()
                if controller_name == "q_learning":
                    controller.train(cfg, episodes=rl_episodes)
                    controller.set_evaluation_mode()
                summary = Simulation(cfg, controller).run(verbose=False)
                rows.append({
                    "seed": seed,
                    "scenario": scenario_name,
                    "controller": controller.name,
                    "total_electricity_cost_usd": summary.get("total_electricity_cost_usd", 0.0),
                    "total_carbon_emissions_kg": summary.get("total_carbon_emissions_kg", 0.0),
                    "peak_grid_load_mw": summary.get("peak_grid_load_mw", 0.0),
                    "steps_over_capacity": summary.get("steps_over_capacity", 0),
                    "pct_evs_met_required_soc": summary.get("pct_evs_met_required_soc", 0.0),
                    "total_v2g_energy_exported_kwh": summary.get("total_v2g_energy_exported_kwh", 0.0),
                })
    return rows


def main():
    args = parse_args()
    if args.scenarios:
        controller_names = args.controllers or list(CONTROLLERS.keys())
        rows = run_stress_sweep(
            controller_names=controller_names,
            scenario_names=args.scenarios,
            seeds=args.seeds,
            base_num_evs=args.evs or 50,
            horizon_hours=args.hours or 24,
            attack_type=args.attack_type,
            attack_probability=args.attack_probability,
            security_enabled=not args.disable_security,
            v2g_rate=args.v2g_rate or 0.0,
            rl_episodes=args.rl_episodes,
        )
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"Stress sweep completed: {len(rows)} runs written to {args.out}")
        return

    cfg = SimulationConfig()
    if args.evs is not None:
        cfg.num_evs = args.evs
    if args.hours is not None:
        cfg.horizon_hours = args.hours
    if args.seed is not None:
        cfg.random_seed = args.seed
    cfg.telemetry_attack_type = args.attack_type
    cfg.telemetry_attack_probability = args.attack_probability
    cfg.telemetry_security_enabled = not args.disable_security
    if args.v2g_rate is not None:
        cfg.v2g_participation_rate = max(0.0, min(1.0, args.v2g_rate))
    cfg.rl_training_episodes = max(0, args.rl_episodes)

    controller = CONTROLLERS[args.controller]()
    if args.controller == "q_learning":
        controller.epsilon = cfg.rl_epsilon
        controller.train(cfg, episodes=cfg.rl_training_episodes)
        controller.set_evaluation_mode()
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
