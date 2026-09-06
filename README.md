## EV Digital Twin for Intelligent Charging and Grid Resilience

An executable research platform for simulating, optimizing, securing, and
evaluating electric-vehicle charging infrastructure. The project models EVs,
charging stations, grid demand, renewable generation, pricing, carbon
intensity, telemetry, failures, attacks, V2G energy export, and adaptive
controllers in one reproducible Python workflow.

It is designed for experimentation without physical IoT hardware or a real
charging dataset. Synthetic scenarios are deterministic when given a seed,
so controller behavior can be compared fairly across normal and stressed
grid conditions.

## Project Goal

The platform answers questions such as:

- How does uncontrolled charging compare with deadline-aware scheduling?
- Can PSO, NSGA-II, and hybrid optimization reduce cost, carbon, or overload?
- How do controllers behave during EV surges, renewable loss, grid limits, or charger failures?
- Can malformed or attacked telemetry be detected before it influences decisions?
- Can participating EVs support the grid through V2G without violating SOC reserves?
- Can an adaptive Q-learning policy learn a useful charging strategy from simulation?

## Roadmap Status

Phases 1 through 9 are implemented as working prototypes. Phases 10 and 11
are currently in progress. Phase 12 is optional follow-up work for dashboard
polish, packaging, and deployment automation.

```
Digital Twin -> baseline -> PSO -> NSGA-II -> hybrid PSO-NSGA-II
-> scenario/stress testing -> anomaly/security -> V2G/multi-agent
-> Q-learning -> real-time simulation -> live SVG/HTML visuals
-> dashboard/deployment polish
```

## How the System Works

Each simulation advances in configurable time steps, normally 15 minutes:

1. The digital twin admits scheduled EV arrivals and connects available stations.
2. The environment updates base load, solar generation, electricity price, and carbon intensity.
3. The telemetry simulator emits noisy and occasionally dropped IoT messages.
4. Optional attack hooks mutate messages; the security monitor validates and scores them.
5. The selected controller observes the twin and returns `{ev_id: power_kw}` decisions.
6. The twin applies charging or V2G discharge while enforcing physical limits.
7. Departing EVs are recorded with final SOC and deadline compliance.
8. Per-step metrics and final summary metrics are written or displayed.

Controllers currently read the simulated twin state directly. Telemetry is
validated and logged independently so later experiments can safely replace
direct state access with trusted telemetry without changing the simulation
contract.

## Repository Structure

| Path | Responsibility |
|---|---|
| `ev_digital_twin/ev.py` | EV battery, SOC, charging efficiency, deadlines, and V2G discharge limits |
| `ev_digital_twin/charging_station.py` | Station availability, four-connector occupancy, and per-connector power limits |
| `ev_digital_twin/grid.py` | Base-load profile, solar generation, pricing, carbon intensity, and net load |
| `ev_digital_twin/digital_twin.py` | Stateful EV, station, and grid environment |
| `ev_digital_twin/telemetry.py` | Synthetic IoT messages, noise, and dropout |
| `ev_digital_twin/security.py` | Telemetry validation, anomaly alerts, and attack simulation |
| `ev_digital_twin/baseline_controller.py` | Uncontrolled, EDF, PSO, NSGA-II, and hybrid PSO-NSGA-II controllers |
| `ev_digital_twin/v2g_controller.py` | Multi-agent bidirectional charging and grid support |
| `ev_digital_twin/rl_controller.py` | Dependency-free tabular Q-learning controller |
| `ev_digital_twin/realtime_runner.py` | Thread-safe background tick loop and pending changes |
| `ev_digital_twin/metrics.py` | Cost, carbon, peak load, capacity, SOC, alert, and V2G metrics |
| `ev_digital_twin/simulation.py` | Closed-loop simulation runner |
| `ev_digital_twin/scenarios.py` | Scenario presets and randomized synthetic inputs |
| `main.py` | CLI simulation, controller registry, and stress sweeps |
| `dashboard.py` | Streamlit comparison dashboard |
| `tests/test_baseline.py` | Regression and behavior tests for all implemented phases |
| `outputs/` | Generated per-step metrics and benchmark CSV files |

## Installation

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

The simulation and controllers use the Python standard library. Streamlit,
Pandas, and Matplotlib are used by the dashboard. No Gymnasium,
Stable-Baselines3, or external optimization package is required.

## Basic CLI Usage

Run a single simulation:

```bash
python main.py --controller uncontrolled --evs 50 --hours 24
python main.py --controller edf --evs 50 --hours 24 --seed 42 --verbose
```

Available controllers:

| CLI name | Behavior |
|---|---|
| `uncontrolled` | Charges connected EVs at maximum power |
| `edf` | Earliest-deadline-first scheduling with grid headroom |
| `pso` | Particle-swarm charging optimization |
| `nsga2` | Pareto-style multi-objective candidate selection |
| `hybrid_pso_nsga2` | PSO exploration combined with Pareto selection |
| `multi_agent_v2g` | Coordinated charging and bidirectional grid support |
| `q_learning` | Adaptive tabular Q-learning policy |

Single-run output includes a summary on stdout and per-step metrics in the
file supplied by `--out` (default: `outputs/metrics.csv`). Common summary
fields are electricity cost, carbon emissions, peak grid load, capacity
violations, EV departure compliance, telemetry alerts, and V2G energy exported.

## Scenario Stress Testing

The built-in presets are:

- `normal`: standard EV population and renewable generation.
- `ev_surge`: concentrated arrivals during a short evening window.
- `low_renewable`: substantially reduced solar generation.
- `grid_constraint`: reduced grid capacity.
- `charger_failure`: reduced station availability.
- `high_penetration`: sharply increased EV population.
- `combined_stress`: simultaneous demand, renewable, and grid stress.

Run every requested scenario/controller/seed combination:

```bash
python main.py \
  --scenarios normal ev_surge grid_constraint combined_stress \
  --controllers edf hybrid_pso_nsga2 q_learning \
  --seeds 42 43 44 --rl-episodes 5 \
  --evs 50 --hours 24 --out outputs/stress_sweep.csv
```

The CSV contains one row per combination and is suitable for repeatable
controller benchmarking. Use `--v2g-rate 0.5` or `--v2g-rate 1.0` to include
partial or full V2G participation in a sweep.

## Telemetry Security Experiments

Security validation is enabled by default. Attack injection is disabled by
default and can be enabled for controlled experiments:

```bash
python main.py --controller edf --evs 30 --hours 6 \
  --attack-type power_spike --attack-probability 0.25 \
  --out outputs/security_metrics.csv
```

Supported attack hooks are `soc_spoof`, `power_spike`, `grid_load_spoof`, and
`replay`. The monitor checks required fields, numeric ranges, EV identity,
duplicate messages, and implausible SOC jumps. Use `--disable-security` to
run a controlled comparison without validation.

## V2G and Multi-Agent Control

Run the V2G controller with configurable participation:

```bash
python main.py --controller multi_agent_v2g --v2g-rate 1.0 \
  --evs 50 --hours 24 --out outputs/v2g_metrics.csv
```

Eligible EV agents discharge when grid support is needed, remain above the
configured reserve SOC, and respect per-EV discharge limits. Other EVs are
scheduled around remaining grid headroom. The simulation records both EV
charging load and V2G export, and capacity checks use net grid load.

## Reinforcement Learning

Phase 9 uses dependency-free tabular Q-learning rather than requiring a
large ML framework:

```bash
python main.py --controller q_learning --rl-episodes 10 \
  --evs 50 --hours 24 --out outputs/rl_metrics.csv
```

The policy state is an aggregate tuple containing grid utilization, price,
solar availability, and charging urgency buckets. Its shared fleet actions
are reduced V2G, idle, partial charging, and full charging. Training runs
episodes through the same digital twin; evaluation sets exploration to zero.

## Dashboard

Launch the Streamlit dashboard:

```bash
streamlit run dashboard.py
```

The dashboard supports manual or randomized scenario inputs, controller
comparison, V2G participation, telemetry attack settings, security toggles,
RL training episodes, summary cards, grid-load charts, price/carbon charts,
and a per-controller metrics table. The live station view contains 16
stations arranged across four 2x2 station grids, with four connector slots
shown for every station.

When real-time simulation is started, the dashboard also provides start/stop
controls and refreshes the four station grids once per second. Stations show
connector occupancy and EV SOC using the live digital-twin snapshot.

## Metrics and Outputs

Per-step CSV metrics include:

- simulation time, total load, net load, EV load, and V2G export;
- base load, solar generation, price, and carbon intensity;
- active EV count, step cost, step carbon, and capacity status.

Summary metrics include total cost, total carbon, peak load, capacity
violations, departed EVs, required-SOC compliance, telemetry alert counts,
high-severity alert counts, and total V2G energy exported.

Generated CSVs in `outputs/` are experiment artifacts and can be regenerated
at any time by rerunning the corresponding command.

## Testing

Run the full regression suite:

```bash
pytest tests/
```

The tests cover controller execution, SOC bounds, stress-sweep coverage and
reproducibility, telemetry attack detection, V2G reserve protection, RL
training/evaluation, real-time batch-equivalence, tick-boundary updates, and
compatibility of the public comparison helpers.

## Scope and Limitations

- The project uses synthetic EV arrivals, grid curves, telemetry, and attacks.
- There is no physical charger, MQTT broker, historical dataset, or hardware integration.
- PSO, NSGA-II, and Q-learning implementations are lightweight research prototypes,
  intended for reproducible comparison rather than production-scale optimization.
- Controllers currently observe the digital twin directly; telemetry security
  is implemented as an observability and validation layer.
- Phase 12 is optional follow-up work for deployment packaging, richer visualizations,
  automated reports, and production hardening.

## Phase-wise Project Status

### Phase 1 — Digital Twin core: completed
- EV battery / SOC model
- arrival and departure scheduling
- station connector management
- grid demand, solar generation, and price model
- digital twin state transitions over time

### Phase 2 — Baseline controller + simulation: completed
- uncontrolled charging baseline
- EDF deadline-prioritized baseline
- closed-loop simulation loop
- step-wise metrics recorder
- cost, carbon, peak load, capacity, and SOC summaries
- CLI execution and test suite validation

### Phase 3 — PSO optimization: completed prototype
- particle-based charging decision search
- cost/carbon/overload/SOC objective formulation
- weighted objective tuning support
- CLI and dashboard controller registration
- comparison against baseline strategies

### Phase 4 — NSGA-II multi-objective optimization: completed prototype
- Pareto-style population evolution
- multi-objective candidate ranking across cost, carbon, overload, and unmet SOC
- non-dominated solution selection
- simulation-ready controller interface
- baseline compatibility and test coverage

### Phase 5 — Hybrid PSO–NSGA-II: completed prototype
- PSO velocity updates for candidate exploration
- Pareto dominance and crowding-distance selection
- grid-capacity-normalized charging decisions
- CLI, dashboard, and scenario-comparison registration

### Phase 6 — Scenario/stress engine: completed prototype
- scenario presets for demand, renewable, charger, and grid disruptions
- repeatable multi-scenario benchmark runs across configurable seeds
- controller comparison across grid and demand stress cases
- CSV export through the CLI stress-sweep mode

### Phase 7 — Anomaly/security layer: completed prototype
- schema and range validation for simulated IoT telemetry
- temporal SOC-jump anomaly detection
- configurable SOC spoofing, power spike, grid-load spoofing, and replay hooks
- structured alert logs and total/high-severity summary metrics
- CLI and dashboard support for security experiments

### Phase 8 — V2G / multi-agent: completed prototype
- configurable V2G participation across EV agents
- multi-agent charging and discharging coordination
- SOC reserve and per-EV discharge-power protection
- grid export and net-load accounting
- V2G metrics in CLI, CSV, and dashboard results
- `multi_agent_v2g` controller registration

### Phase 9 — RL controller: completed prototype
- dependency-free tabular Q-learning policy
- configurable training episodes and exploration decay
- aggregate state representation for grid, price, solar, and urgency
- charging and V2G action support
- CLI, dashboard, and stress-sweep registration

### Phase 10 — Real-time simulation engine: in progress
- background-thread tick loop around the existing digital twin and controller
- thread-safe live state with twin, controller, metrics, running flag, and step
- tick-boundary application of controller, V2G, and scenario changes
- deterministic comparison with the existing batch simulation
- `tests/test_realtime.py` coverage for real-time determinism

### Phase 11 — Live SVG/HTML visual layer: in progress
- live EV, station, and grid state rendered with inline SVG/HTML
- one-second Streamlit fragment updates without resetting sidebar state
- pure rendering layer driven by `DigitalTwin.get_state_snapshot()`
- 16 stations displayed as four 2x2 station grids
- four connector slots rendered for every station

### Phase 12 — Final dashboard / deployment: optional follow-up
- richer dashboard visualizations
- automated benchmark reports
- packaging and deployment workflow
- production hardening and operational documentation

## Recommended Next Steps

The current focus is completing Phases 10 and 11: real-time background
execution and live visual state rendering. Phase 12 remains optional follow-up
work for richer dashboard polish, benchmark automation, packaging, and
deployment documentation.

