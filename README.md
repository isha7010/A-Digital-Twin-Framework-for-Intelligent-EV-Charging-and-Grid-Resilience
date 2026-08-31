# EV Digital Twin — Optimization Project

This repository now contains a working digital twin with a validated
baseline, a PSO optimizer, and an NSGA-II-inspired multi-objective
controller. The project follows the recommended roadmap below and has
progressed through the core optimization phases:

```
Digital Twin -> baseline -> PSO -> NSGA-II -> hybrid PSO-NSGA-II
-> scenario/stress testing -> anomaly/security -> V2G/multi-agent
-> RL -> final dashboard
```

## Current implementation status

Completed phases:
- Phase 1: Digital Twin core
- Phase 2: Baseline controller + closed-loop simulation + metrics
- Phase 3: PSO controller prototype
- Phase 4: NSGA-II multi-objective controller prototype

In progress / next up:
- Phase 5: hybrid PSO-NSGA-II
- Phase 6: scenario/stress engine
- Phase 7: anomaly/security layer
- Phase 8: V2G / multi-agent coordination
- Phase 9: RL controller
- Phase 10: final polished dashboard and deployment workflow

The repo is now beyond the baseline scaffold and serves as a working
research-grade EV charging and grid optimization platform with
comparison-capable controller logic.

## What's included

| Module | Spec section | Purpose |
|---|---|---|
| `ev_digital_twin/ev.py` | 5.1 | EV state: SOC, battery, deadlines, charging/discharge physics |
| `ev_digital_twin/charging_station.py` | 5.2 | Connectors, occupancy, power delivery |
| `ev_digital_twin/grid.py` | 5.3 / 5.4 | Base load curve, solar curve, TOU pricing, carbon intensity |
| `ev_digital_twin/digital_twin.py` | 4 / 5 | Ties state together: arrivals, connections, stepping, departures |
| `ev_digital_twin/telemetry.py` | 6 | Simulated IoT messages with configurable noise/dropout |
| `ev_digital_twin/baseline_controller.py` | 21 + optimizer extensions | `UncontrolledController`, `EarliestDeadlineFirstController`, `PSOController`, `NSGAIIController` |
| `ev_digital_twin/metrics.py` | 18 (subset) | Cost, carbon, peak load, capacity violations, SOC compliance |
| `ev_digital_twin/simulation.py` | 15 | The closed-loop simulation runner |
| `ev_digital_twin/scenarios.py` | 14 | Scenario presets + random input generator (no real dataset yet) |
| `main.py` | — | CLI entry point |
| `dashboard.py` | 16 (early) | Green-themed Streamlit dashboard with the randomizer built in |
| `tests/test_baseline.py` | — | Sanity tests (run, metrics, EDF vs uncontrolled) |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt

python main.py --controller uncontrolled --evs 50 --hours 24
python main.py --controller edf --evs 50 --hours 24 --verbose
```

Per-step metrics are written to `outputs/metrics.csv`; a summary prints
to stdout (total cost, peak grid load, carbon emissions, capacity
violations, % of EVs that met their required departure SOC).

## Dashboard (green theme)

A Streamlit dashboard is included so you can see results visually and
compare controllers without touching the CLI:

```bash
pip install -r requirements.txt   # if not already installed
streamlit run dashboard.py
```

It opens in your browser (usually `http://localhost:8501`). From the
sidebar you can:

- **🎲 Randomize inputs** — picks a random scenario preset (see below),
  a random EV population size, horizon, and seed. Use this whenever
  you don't have a real dataset yet and just want plausible synthetic
  inputs to exercise the pipeline.
- **Set inputs manually** — pick a scenario, EV count, horizon and
  seed by hand.
- **Compare controllers** — select `uncontrolled` and/or `edf`; the
  dashboard runs the simulation for each and shows side-by-side
  summary cards, a grid-load-over-time chart, a price/carbon-intensity
  chart, and a metrics table.

Styling (card colors, `.streamlit/config.toml` theme, chart colors)
uses a single green palette throughout.

### Input randomizer / scenario presets

`ev_digital_twin/scenarios.py` implements the scenario presets from
spec section 14 (`normal`, `ev_surge`, `low_renewable`,
`grid_constraint`, `charger_failure`, `high_penetration`,
`combined_stress`) plus `randomize_inputs()`, which picks one at
random along with a random EV count, horizon, and seed. This is a
stand-in for real telemetry/historical datasets — swap it out once you
have actual data, but keep it around for stress-testing (section 14)
and for generating training scenarios once you get to the RL phase.

Run tests:

```bash
python tests/test_baseline.py
# or, if you install pytest:
pytest tests/
```

## Design notes

- **No physical hardware.** `telemetry.py` simulates what an IoT
  deployment would emit (per the spec's "no physical IoT hardware"
  requirement), including configurable measurement noise and message
  dropout — this is the hook point for the anomaly/attack-detection
  layer in a later phase.
- **Two baseline controllers** are included so you have more than one
  reference point once you add PSO/NSGA-II: `uncontrolled` (charge at
  max power immediately) and `edf` (earliest-deadline-first, grid
  capacity aware). The test suite checks that EDF never causes *more*
  capacity violations than uncontrolled charging.
- **Everything is a plain dict/dataclass**, not tied to any ML or
  optimization library yet, so PSO/NSGA-II particles can be encoded as
  `{ev_id: power_kw}` dictionaries (or arrays indexed the same way)
  without refactoring the twin.

## Phase-wise project status

### Phase 1 — Digital Twin core: completed
- EV battery / SOC model
- arrival and departure scheduling
- station connector management
- grid demand, solar generation, and price model
- digital twin state transitions over time

### Phase 2 — Baseline controller + simulation: completed
- Uncontrolled charging baseline
- EDF deadline-prioritized baseline
- closed-loop simulation loop
- step-wise metrics recorder
- summary statistics for cost, carbon, peak load, and SOC compliance
- CLI execution and test suite validation

### Phase 3 — PSO optimization: completed prototype
- particle-based charging decision search
- cost/carbon/overload/SOC objective formulation
- weighted objective tuning support
- CLI and dashboard controller registration
- comparison against baseline strategies

### Phase 4 — NSGA-II multi-objective optimization: completed prototype
- Pareto-style population evolution
- multi-objective candidate ranking across cost, carbon, overload,
  and unmet SOC
- non-dominated solution selection
- simulation-ready controller interface
- baseline compatibility and test coverage

### Phase 5 — Hybrid PSO–NSGA-II: pending
- combine PSO exploration with NSGA-II ranking and selection
- stronger multi-objective optimization loop

### Phase 6 — Scenario/stress engine: pending
- richer scenario presets and stress sweeps
- multi-scenario benchmark runs
- controller comparison across grid and demand disruptions

### Phase 7 — Anomaly/security layer: pending
- telemetry validation and anomaly detection
- attack simulation hooks and alerting

### Phase 8 — V2G / multi-agent: pending
- bidirectional charging coordination
- multi-agent scheduling and grid support decisions

### Phase 9 — RL controller: pending
- adaptive control policy training for dynamic conditions

### Phase 10 — Final dashboard / deployment: pending
- final polished dashboard visualizations
- automation, benchmarking, and packaged deployment workflow

## Recommended next milestone

The next practical milestone is to integrate a hybrid PSO–NSGA-II
controller and expand the scenario comparison framework so each
controller can be evaluated across stress cases in a repeatable way.
