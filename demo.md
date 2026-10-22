# EV Digital Twin Project Demo Guide

This guide explains how to demonstrate the completed EV Digital Twin project
to someone else. It focuses on running the project and showing its features,
not on installation or environment setup.

The recommended order is:

1. Start the dashboard.
2. Show one normal simulation.
3. Compare all charging controllers.
4. Demonstrate grid and demand stress conditions.
5. Demonstrate telemetry attacks and security alerts.
6. Demonstrate V2G grid support.
7. Demonstrate Q-learning.
8. Demonstrate real-time simulation and the live SVG station view.
9. Run the complete manual benchmark combination.
10. Download and show the generated CSV report.

---

## 1. Start the dashboard

### Option A: Run locally

From the project directory, run:

```powershell
streamlit run dashboard.py
```

Open the address shown by Streamlit, normally:

```text
http://localhost:8501
```

### Option B: Run with Docker

If the Docker image has already been built, run:

```powershell
docker run --rm -p 8501:8501 ev-digital-twin:academic
```

Then open:

```text
http://localhost:8501
```

The Docker version provides the same dashboard and is useful when presenting
the project on another computer.

---

## 2. Dashboard demonstration

The dashboard is the easiest way to provide a visual demonstration.

### 2.1 Normal scenario

Use these settings:

| Setting | Value |
|---|---|
| Scenario | `normal` |
| Base EV population | `50` |
| Horizon | `24` hours |
| Random seed | `42` |
| Telemetry attack | `none` |
| Attack probability | `0.0` |
| Telemetry security | Enabled |
| V2G participation | `0.0` |
| RL training episodes | `0` |
| Controllers | `uncontrolled`, `edf` |

Click **Run simulation**.

Explain the displayed results:

- **Total cost** shows the electricity cost of charging.
- **Carbon emissions** shows the estimated carbon impact.
- **Peak grid load** shows the highest total grid demand.
- **Steps over capacity** shows grid-capacity violations.
- **EVs departed** shows how many EVs completed their charging session.
- **Required SOC compliance** shows the percentage of EVs meeting their target.
- **Telemetry alerts** shows detected invalid or suspicious telemetry.
- **V2G exported** shows energy sent back to the grid.

Use this first comparison to explain that uncontrolled charging is the
reference strategy, while EDF attempts to schedule EVs according to their
departure deadlines and grid headroom.

---

## 3. Compare all available controllers

Select all of the following controllers:

```text
uncontrolled
edf
pso
nsga2
hybrid_pso_nsga2
multi_agent_v2g
q_learning
```

Recommended settings:

| Setting | Value |
|---|---|
| Scenario | `normal` |
| Base EV population | `50` |
| Horizon | `24` hours |
| Random seed | `42` |
| Telemetry attack | `none` |
| V2G participation | `0.5` |
| RL training episodes | `5` |

Click **Run simulation** and compare the summary cards and charts.

Describe the controllers as follows:

| Controller | Demonstration explanation |
|---|---|
| `uncontrolled` | Charges connected EVs at maximum available power. This is the baseline. |
| `edf` | Prioritizes EVs with the earliest departure deadlines. |
| `pso` | Searches for charging powers using a particle-swarm optimization prototype. |
| `nsga2` | Selects charging decisions using multiple objectives such as cost, carbon, overload, and SOC. |
| `hybrid_pso_nsga2` | Combines PSO exploration with Pareto-style multi-objective selection. |
| `multi_agent_v2g` | Coordinates EV charging and discharging while protecting SOC reserves. |
| `q_learning` | Uses a tabular reinforcement-learning policy trained on the simulated environment. |

Point out that this is a reproducible research comparison: all controllers
can be evaluated using the same scenario, seed, EV population, and horizon.

---

## 4. Demonstrate the real-time visual layer

In the dashboard sidebar:

1. Select a live controller, preferably `edf`.
2. Use a small demonstration configuration:
   - Scenario: `normal`
   - EV population: `50`
   - Horizon: `24`
   - Seed: `42`
3. Click **Start real-time simulation**.
4. Scroll to the **Live digital twin** section.

Show the following live elements:

- Current simulation time.
- Running or stopped status.
- Net load compared with grid capacity.
- Solar generation.
- V2G export.
- Active EV count.
- Grid-capacity utilization bar.
- Four station grids.
- Sixteen charging stations.
- Four connector slots per station.
- Connector colors for charging, V2G discharge, idle, and empty slots.

Explain that the simulation advances on a background thread while the
Streamlit visual layer refreshes approximately once per second.

Click **Stop real-time simulation** after showing several updates.

For a clear overload demonstration, select `uncontrolled` as the live
controller and use a larger EV population such as `200` or `300`.

---

## 5. Scenario and stress demonstrations

The project includes these built-in scenario conditions:

| Scenario | What it demonstrates |
|---|---|
| `normal` | Standard EV arrivals, renewable generation, and grid conditions. |
| `ev_surge` | Many EVs arriving during a concentrated period. |
| `low_renewable` | Reduced solar generation and greater dependence on the grid. |
| `grid_constraint` | Reduced grid capacity and overload pressure. |
| `charger_failure` | Reduced charging-station availability. |
| `high_penetration` | A sharply increased EV population. |
| `combined_stress` | Demand, renewable, and grid stress occurring together. |

### Dashboard method

Run the following scenarios one at a time with:

| Setting | Value |
|---|---|
| Base EV population | `50` |
| Horizon | `24` hours |
| Seed | `42` |
| Controllers | `edf`, `hybrid_pso_nsga2`, `q_learning` |
| V2G participation | `0.0` |
| RL training episodes | `5` |

For each scenario, compare:

- Peak grid load.
- Number of capacity violations.
- Electricity cost.
- Carbon emissions.
- Required-SOC compliance.

### CLI method

Run a multi-condition stress sweep:

```powershell
python main.py `
  --scenarios normal ev_surge low_renewable grid_constraint `
  --controllers edf hybrid_pso_nsga2 q_learning `
  --seeds 42 43 44 `
  --rl-episodes 5 `
  --evs 50 `
  --hours 24 `
  --out outputs/demo_stress_sweep.csv
```

This produces one CSV row for every:

```text
scenario × controller × seed
```

For the command above, the output contains:

```text
4 scenarios × 3 controllers × 3 seeds = 36 runs
```

To include every built-in condition:

```powershell
python main.py `
  --scenarios normal ev_surge low_renewable grid_constraint charger_failure high_penetration combined_stress `
  --controllers uncontrolled edf pso nsga2 hybrid_pso_nsga2 multi_agent_v2g q_learning `
  --seeds 42 43 44 `
  --rl-episodes 5 `
  --evs 50 `
  --hours 24 `
  --v2g-rate 0.5 `
  --out outputs/demo_all_conditions.csv
```

This full demonstration contains:

```text
7 scenarios × 7 controllers × 3 seeds = 147 runs
```

Use the generated CSV to show that the project supports repeatable,
multi-condition benchmarking.

---

## 6. Telemetry security demonstration

Security validation is enabled by default. Attack injection can be shown using
the following commands.

### Clean telemetry baseline

```powershell
python main.py `
  --controller edf `
  --evs 30 `
  --hours 6 `
  --seed 42 `
  --out outputs/demo_clean_security.csv
```

Expected observation:

- Telemetry alerts should normally be zero or very low when noise and dropout
  do not create invalid messages.

### Power-spike attack

```powershell
python main.py `
  --controller edf `
  --evs 30 `
  --hours 6 `
  --seed 42 `
  --attack-type power_spike `
  --attack-probability 1.0 `
  --out outputs/demo_power_spike.csv
```

### SOC-spoofing attack

```powershell
python main.py `
  --controller edf `
  --evs 30 `
  --hours 6 `
  --seed 42 `
  --attack-type soc_spoof `
  --attack-probability 1.0 `
  --out outputs/demo_soc_spoof.csv
```

### Grid-load spoofing attack

```powershell
python main.py `
  --controller edf `
  --evs 30 `
  --hours 6 `
  --seed 42 `
  --attack-type grid_load_spoof `
  --attack-probability 1.0 `
  --out outputs/demo_grid_spoof.csv
```

### Replay attack

```powershell
python main.py `
  --controller edf `
  --evs 30 `
  --hours 6 `
  --seed 42 `
  --attack-type replay `
  --attack-probability 1.0 `
  --out outputs/demo_replay.csv
```

Explain that the security layer checks:

- Required telemetry fields.
- Numeric ranges.
- EV identity.
- Duplicate or replayed messages.
- Implausible SOC changes.
- Abnormal power values.

Then show the `telemetry_alerts` and
`high_severity_telemetry_alerts` fields in the terminal output or CSV.

For a controlled comparison without validation, run:

```powershell
python main.py `
  --controller edf `
  --evs 30 `
  --hours 6 `
  --attack-type power_spike `
  --attack-probability 1.0 `
  --disable-security `
  --out outputs/demo_security_disabled.csv
```

---

## 7. V2G demonstration

Run a V2G-enabled simulation:

```powershell
python main.py `
  --controller multi_agent_v2g `
  --v2g-rate 1.0 `
  --evs 50 `
  --hours 24 `
  --seed 42 `
  --out outputs/demo_v2g.csv
```

Compare it with a no-V2G run:

```powershell
python main.py `
  --controller multi_agent_v2g `
  --v2g-rate 0.0 `
  --evs 50 `
  --hours 24 `
  --seed 42 `
  --out outputs/demo_no_v2g.csv
```

Highlight:

- `total_v2g_energy_exported_kwh`.
- Net grid load rather than only charging load.
- Protection of the configured reserve SOC.
- The difference between participating and non-participating EVs.

Use `--v2g-rate 0.5` to demonstrate partial participation.

---

## 8. Q-learning demonstration

Train and evaluate the Q-learning controller:

```powershell
python main.py `
  --controller q_learning `
  --rl-episodes 10 `
  --evs 50 `
  --hours 24 `
  --seed 42 `
  --out outputs/demo_q_learning.csv
```

For a stronger training comparison:

```powershell
python main.py `
  --controller q_learning `
  --rl-episodes 25 `
  --evs 50 `
  --hours 24 `
  --seed 42 `
  --out outputs/demo_q_learning_25_episodes.csv
```

Explain that the project uses dependency-free tabular Q-learning. The policy
learns from an aggregate state containing grid utilization, price, solar
conditions, urgency, capacity violations, SOC compliance, telemetry alerts,
and V2G export.

---

## 9. Individual controller demonstrations

These commands isolate each controller for a simple presentation:

```powershell
python main.py --controller uncontrolled --evs 50 --hours 24 --seed 42 --out outputs/demo_uncontrolled.csv
python main.py --controller edf --evs 50 --hours 24 --seed 42 --out outputs/demo_edf.csv
python main.py --controller pso --evs 50 --hours 24 --seed 42 --out outputs/demo_pso.csv
python main.py --controller nsga2 --evs 50 --hours 24 --seed 42 --out outputs/demo_nsga2.csv
python main.py --controller hybrid_pso_nsga2 --evs 50 --hours 24 --seed 42 --out outputs/demo_hybrid.csv
python main.py --controller multi_agent_v2g --v2g-rate 1.0 --evs 50 --hours 24 --seed 42 --out outputs/demo_multi_agent_v2g.csv
python main.py --controller q_learning --rl-episodes 10 --evs 50 --hours 24 --seed 42 --out outputs/demo_q_learning.csv
```

When presenting results, keep the seed, EV population, horizon, and scenario
the same so that the controller comparison is fair.

---

## 10. Suggested presentation script

Use the following short explanation:

> This project is a software-only digital twin for EV charging and grid
> resilience. It creates deterministic synthetic EV, charging-station, grid,
> renewable, pricing, telemetry, and attack conditions. Multiple controllers
> then make charging or V2G decisions in the same simulated environment. The
> results are measured using cost, carbon, peak load, capacity violations,
> charging compliance, security alerts, and exported V2G energy.

Recommended live sequence:

1. Show the normal `uncontrolled` versus `edf` comparison.
2. Add PSO, NSGA-II, hybrid optimization, V2G, and Q-learning.
3. Switch to `grid_constraint` and explain overload reduction.
4. Switch to `low_renewable` and explain solar availability.
5. Switch to `ev_surge` and explain concentrated demand.
6. Enable `power_spike` attacks and show security alerts.
7. Start the real-time simulation and show the four station grids.
8. Run the full stress sweep and open the CSV output.
9. Finish by showing the Docker dashboard if the demonstration is being
   performed on another computer.

---

## 11. Useful output files

The commands above generate CSV files under `outputs/`. The most useful demo
artifacts are:

| File | Purpose |
|---|---|
| `demo_stress_sweep.csv` | Comparison across selected scenarios, controllers, and seeds. |
| `demo_all_conditions.csv` | Full manual combination benchmark. |
| `demo_v2g.csv` | V2G energy export and net-load demonstration. |
| `demo_power_spike.csv` | Telemetry security attack demonstration. |
| `demo_q_learning.csv` | Reinforcement-learning demonstration. |
| Individual controller CSVs | Per-step metrics for charting or inspection. |

The dashboard also provides a **Download summary report (CSV)** button for the
currently selected controller comparison.

---

## 12. What the demo proves

The completed demonstration covers:

- Digital-twin state evolution.
- EV arrival, charging, departure, and SOC tracking.
- Charging-station and connector occupancy.
- Grid load, capacity, solar, pricing, and carbon conditions.
- Baseline and optimization controllers.
- Multi-agent V2G support.
- Q-learning-based adaptive control.
- Stress and scenario benchmarking.
- Telemetry attack detection.
- Real-time background execution.
- Live SVG/HTML visualization.
- Reproducible CSV reporting.
- Local Docker execution for academic presentation.
