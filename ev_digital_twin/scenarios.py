"""
Scenario presets and a randomizer for generating synthetic inputs
(spec section 14: scenario / stress-testing engine).

Since no real telemetry or historical charging datasets are wired in
yet, this module lets you generate plausible randomized configs and
EV populations so the rest of the pipeline (controller, metrics,
dashboard) has something realistic to run against.
"""

import random
import copy
from .config import SimulationConfig


SCENARIOS = {
    "normal": {
        "description": "Baseline EV population, normal renewable generation.",
    },
    "ev_surge": {
        "description": "A large number of EVs arrive in a short time window.",
        "num_evs_mult": 2.2,
        "arrival_window": (17.0, 20.0),
    },
    "low_renewable": {
        "description": "Solar generation falls substantially.",
        "solar_capacity_mult": 0.25,
    },
    "grid_constraint": {
        "description": "Available grid capacity is reduced.",
        "grid_capacity_mult": 0.6,
    },
    "charger_failure": {
        "description": "A portion of charging stations become unavailable.",
        "station_mult": 0.6,
    },
    "high_penetration": {
        "description": "EV population scaled up sharply.",
        "num_evs_mult": 4.0,
    },
    "combined_stress": {
        "description": "Simultaneous EV surge, low renewables, and reduced grid capacity.",
        "num_evs_mult": 2.0,
        "arrival_window": (17.0, 20.0),
        "solar_capacity_mult": 0.3,
        "grid_capacity_mult": 0.7,
    },
}


def build_config(scenario_name: str, base_num_evs: int = 50, seed: int = 42) -> SimulationConfig:
    """Build a SimulationConfig for a named scenario preset."""
    cfg = SimulationConfig()
    cfg.random_seed = seed
    cfg.num_evs = base_num_evs
    spec = SCENARIOS.get(scenario_name, SCENARIOS["normal"])

    if "num_evs_mult" in spec:
        cfg.num_evs = int(round(cfg.num_evs * spec["num_evs_mult"]))
    if "arrival_window" in spec:
        cfg.ev_arrival_hour_range = spec["arrival_window"]
    if "solar_capacity_mult" in spec:
        cfg.solar_capacity_mw *= spec["solar_capacity_mult"]
    if "grid_capacity_mult" in spec:
        cfg.grid_capacity_mw *= spec["grid_capacity_mult"]
    if "station_mult" in spec:
        cfg.num_stations = max(1, int(round(cfg.num_stations * spec["station_mult"])))

    return cfg


def randomize_inputs(rng: random.Random = None) -> dict:
    """
    Pick a random scenario + random dataset-shape parameters. Use this
    when you don't have a real dataset yet and want a plausible,
    reproducible set of inputs to exercise the pipeline with.

    Returns a dict describing the choice, plus the built SimulationConfig,
    so the caller can display what was randomized.
    """
    rng = rng or random.Random()
    scenario_name = rng.choice(list(SCENARIOS.keys()))
    base_num_evs = rng.choice([20, 30, 50, 75, 100, 150])
    seed = rng.randint(0, 999_999)
    horizon_hours = rng.choice([12, 18, 24, 36])

    cfg = build_config(scenario_name, base_num_evs=base_num_evs, seed=seed)
    cfg.horizon_hours = horizon_hours

    return {
        "scenario_name": scenario_name,
        "description": SCENARIOS[scenario_name]["description"],
        "base_num_evs": base_num_evs,
        "seed": seed,
        "horizon_hours": horizon_hours,
        "config": cfg,
    }
