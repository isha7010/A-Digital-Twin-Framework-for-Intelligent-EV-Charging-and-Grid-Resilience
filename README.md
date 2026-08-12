# EV Digital Twin — Baseline Project

Baseline software scaffold for the *Digital Twin-Based Intelligent and
Resilient EV Charging & Grid Optimization* project. This is phase 2 of
the recommended build order from the project spec:

```
Digital Twin -> baseline -> PSO -> NSGA-II -> hybrid PSO-NSGA-II
-> scenario/stress testing -> anomaly/security -> V2G/multi-agent
-> RL -> final dashboard
```

Phase 1 (the Digital Twin) and phase 2 (a baseline controller +
closed-loop simulation + metrics) are implemented here so you have a
working, testable core before adding the optimizer.

## What's included

| Module | Spec section | Purpose |
|---|---|---|
| `ev_digital_twin/ev.py` | 5.1 | EV state: SOC, battery, deadlines, charging/discharge physics |
| `ev_digital_twin/charging_station.py` | 5.2 | Connectors, occupancy, power delivery |
| `ev_digital_twin/grid.py` | 5.3 / 5.4 | Base load curve, solar curve, TOU pricing, carbon intensity |
| `ev_digital_twin/digital_twin.py` | 4 / 5 | Ties state together: arrivals, connections, stepping, departures |
| `ev_digital_twin/telemetry.py` | 6 | Simulated IoT messages with configurable noise/dropout |
| `ev_digital_twin/baseline_controller.py` | 21 (baseline) | `UncontrolledController` and `EarliestDeadlineFirstController` |
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

## Next steps (per the project's recommended priority)

1. **PSO** — implement a `PSOController` that treats
   `Simulation.twin` + `MetricsRecorder` as the fitness/evaluation
   function; represent a particle as one charging-power decision per
   EV per time slot.
2. **NSGA-II** — non-dominated sorting + crowding distance over the
   4 objectives already computed in `metrics.py` (cost, peak load,
   carbon, unmet SOC/delay).
3. **Hybrid PSO–NSGA-II** — combine per the sequence in spec section
   11.4.
4. **Scenario/stress engine** — parameterize `SimulationConfig` (EV
   surge, low renewable, reduced grid capacity, charger failure) and
   sweep across them.
5. **Anomaly/security layer** — add rule-based + ML checks in front of
   `telemetry.py`'s output before it reaches the controller; inject
   attacks in the scenario engine.
6. **V2G / multi-agent** — `EV.apply_discharge` and
   `v2g_participant` are already modeled; wire in a coordination
   layer for the multi-agent case.
7. **RL adaptive controller** — implement a `decide(twin)` object like
   the existing controllers so it's a drop-in replacement/supplement.
8. **Dashboard** — read `outputs/metrics.csv` (and per-scenario
   variants) into your visualization tool of choice.
