"""
Green-themed dashboard for the EV digital twin baseline.

Run with:
    streamlit run dashboard.py

Lets you either configure a scenario manually or hit "Randomize
inputs" to generate a synthetic EV population / scenario on the fly
(useful while no real telemetry or historical dataset is wired in
yet), run one or more baseline controllers against it, and compare
the resulting metrics.
"""

import random
import html

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from ev_digital_twin.scenarios import SCENARIOS, build_config, randomize_inputs
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
from ev_digital_twin.realtime_runner import RealtimeRunner

GREEN_DARK = "#173404"
GREEN_MID = "#3B6D11"
GREEN_LINE = "#639922"
GREEN_LIGHT = "#97C459"
GREEN_BG = "#EAF3DE"

CONTROLLERS = {
    "uncontrolled": UncontrolledController,
    "edf": EarliestDeadlineFirstController,
    "pso": PSOController,
    "nsga2": NSGAIIController,
    "hybrid_pso_nsga2": HybridPSONSGAIIController,
    "multi_agent_v2g": MultiAgentV2GController,
    "q_learning": QLearningController,
}


def render_live_state(snapshot: dict) -> str:
    """Render four live station-layout grids as self-contained SVG/HTML."""
    state = snapshot.get("state", {})
    grid = state.get("grid", {})
    stations = state.get("stations", [])
    evs = state.get("evs", [])
    width, height = 470, 245
    capacity = max(grid.get("capacity_mw", 1.0), 0.001)
    load = max(grid.get("net_load_mw", 0.0), 0.0)
    load_ratio = min(1.0, load / capacity)
    meter_color = "#b42318" if load_ratio >= 1.0 else "#3B6D11"
    groups = [[] for _ in range(4)]
    for index, station in enumerate(stations):
        groups[index % 4].append(station)
    ev_by_station = {}
    for ev in evs:
        ev_by_station.setdefault(ev.get("station"), []).append(ev)
    colors = {"charging": "#639922", "v2g_discharging": "#b42318", "idle": "#64748b"}
    panels = []
    for group_index, group in enumerate(groups):
        station_shapes = []
        ev_shapes = []
        for station_index, station in enumerate(group):
            x = 16 + (station_index % 2) * 220
            y = 34 + (station_index // 2) * 82
            station_shapes.append(
                f'<rect x="{x}" y="{y}" width="190" height="58" rx="6" '
                f'fill="#EAF3DE" stroke="#639922"/><text x="{x + 8}" y="{y + 17}" '
                f'font-size="11" fill="#173404">{html.escape(station["station_id"])}</text>'
            )
            for connector in range(4):
                ev_id = station.get("occupancy", {}).get(connector)
                ev = next((item for item in evs if item.get("ev_id") == ev_id), None)
                color = colors.get(ev.get("state"), "#64748b") if ev else "#cbd5e1"
                fill_height = max(2, min(24, ev.get("soc", 0.0) * 24)) if ev else 0
                ev_x = x + 12 + connector * 28
                ev_y = y + 28
                ev_shapes.append(
                    f'<rect x="{ev_x}" y="{ev_y + 24 - fill_height}" width="12" height="{fill_height}" fill="{color}"/>'
                    f'<rect x="{ev_x}" y="{ev_y}" width="12" height="24" fill="none" stroke="{color}"/>'
                )
        panels.append(
            f'<div style="width:100%;min-width:0;overflow:hidden;">'
            f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Station grid {group_index + 1}">'
            f'<rect width="{width}" height="{height}" fill="#ffffff"/> '
            f'<text x="16" y="20" font-size="13" font-weight="600" fill="#173404">Station grid {group_index + 1}</text>'
            f'{"".join(station_shapes)}{"".join(ev_shapes)}</svg></div>'
        )
    return f"""
    <div style='font-family:sans-serif;color:#173404'>
      <div style='font-size:14px;margin-bottom:6px'>Live station layouts · t={state.get('time_h', 0):.2f}h</div>
      <div style='font-size:12px;margin-bottom:8px'>Net load {load:.2f} / {capacity:.2f} MW · Solar {grid.get('solar_mw', 0.0):.2f} MW · V2G export {grid.get('v2g_export_mw', 0.0):.2f} MW</div>
      <div style='height:8px;background:#e2e8f0;border-radius:4px;margin-bottom:8px'>
        <div style='width:{100 * load_ratio:.1f}%;height:8px;background:{meter_color};border-radius:4px'></div>
      </div>
            <div style='display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;width:100%'>
                {''.join(panels)}
            </div>
    </div>
    """

st.set_page_config(page_title="EV Digital Twin Dashboard", layout="wide")

st.markdown(
    f"""
    <style>
    .metric-card {{
        background-color: {GREEN_BG};
        border: 1px solid {GREEN_LIGHT};
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 8px;
    }}
    .metric-card .label {{ color: {GREEN_MID}; font-size: 13px; }}
    .metric-card .value {{ color: {GREEN_DARK}; font-size: 22px; font-weight: 600; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("EV charging digital twin — baseline dashboard")
st.caption(
    "Closed-loop simulation results for the digital twin + baseline "
    "controllers. No real telemetry dataset yet — use the randomizer "
    "in the sidebar to generate synthetic scenarios and EV populations."
)

# ---------------------------------------------------------------- state ----
if "inputs" not in st.session_state:
    st.session_state.inputs = {
        "mode": "manual",
        "scenario_name": "normal",
        "base_num_evs": 50,
        "seed": 42,
        "horizon_hours": 24,
        "attack_type": "none",
        "attack_probability": 0.0,
        "security_enabled": True,
        "v2g_rate": 0.0,
        "rl_episodes": 0,
    }
if "realtime_runner" not in st.session_state:
    st.session_state.realtime_runner = None

# --------------------------------------------------------------- sidebar ----
with st.sidebar:
    st.header("Inputs")

    if st.button("🎲 Randomize inputs", use_container_width=True):
        result = randomize_inputs(random.Random())
        st.session_state.inputs = {
            "mode": "random",
            "scenario_name": result["scenario_name"],
            "base_num_evs": result["base_num_evs"],
            "seed": result["seed"],
            "horizon_hours": result["horizon_hours"],
            "attack_type": "none",
            "attack_probability": 0.0,
            "security_enabled": True,
            "v2g_rate": 0.0,
            "rl_episodes": 0,
        }

    st.divider()
    st.caption("Or set inputs manually:")

    inputs = st.session_state.inputs
    scenario_name = st.selectbox(
        "Scenario",
        list(SCENARIOS.keys()),
        index=list(SCENARIOS.keys()).index(inputs["scenario_name"]),
    )
    base_num_evs = st.slider("Base EV population", 10, 300, inputs["base_num_evs"], step=10)
    horizon_hours = st.slider("Horizon (hours)", 6, 48, inputs["horizon_hours"], step=6)
    seed = st.number_input("Random seed", value=int(inputs["seed"]), step=1)
    attack_type = st.selectbox(
        "Telemetry attack", ["none", "soc_spoof", "power_spike", "grid_load_spoof", "replay"],
        index=["none", "soc_spoof", "power_spike", "grid_load_spoof", "replay"].index(inputs["attack_type"]),
    )
    attack_probability = st.slider(
        "Attack probability", 0.0, 1.0, float(inputs["attack_probability"]), step=0.05,
    )
    security_enabled = st.checkbox("Enable telemetry security", value=inputs["security_enabled"])
    v2g_rate = st.slider("V2G participation", 0.0, 1.0, float(inputs["v2g_rate"]), step=0.05)
    rl_episodes = st.number_input("RL training episodes", min_value=0, max_value=50, value=int(inputs["rl_episodes"]), step=1)

    st.session_state.inputs = {
        "mode": "manual",
        "scenario_name": scenario_name,
        "base_num_evs": base_num_evs,
        "seed": seed,
        "horizon_hours": horizon_hours,
        "attack_type": attack_type,
        "attack_probability": attack_probability,
        "security_enabled": security_enabled,
        "v2g_rate": v2g_rate,
        "rl_episodes": rl_episodes,
    }

    st.divider()
    controller_choices = st.multiselect(
        "Controllers to compare",
        list(CONTROLLERS.keys()),
        default=["uncontrolled", "edf"],
    )
    run_clicked = st.button("▶ Run simulation", type="primary", use_container_width=True)
    live_controller = st.selectbox("Live controller", list(CONTROLLERS.keys()), index=0)
    start_live = st.button("Start real-time simulation", use_container_width=True)
    stop_live = st.button("Stop real-time simulation", use_container_width=True)

    if start_live:
        live_cfg = build_config(
            inputs["scenario_name"],
            base_num_evs=inputs["base_num_evs"],
            seed=inputs["seed"],
        )
        live_cfg.horizon_hours = inputs["horizon_hours"]
        live_cfg.v2g_participation_rate = inputs["v2g_rate"]
        live_cfg.telemetry_attack_type = inputs["attack_type"]
        live_cfg.telemetry_attack_probability = inputs["attack_probability"]
        live_cfg.telemetry_security_enabled = inputs["security_enabled"]
        live_controller_instance = CONTROLLERS[live_controller]()
        if live_controller == "q_learning":
            live_controller_instance.train(live_cfg, episodes=int(inputs["rl_episodes"]))
            live_controller_instance.set_evaluation_mode()
        st.session_state.realtime_runner = RealtimeRunner(
            live_cfg, live_controller_instance, tick_seconds=1.0,
        )
        st.session_state.realtime_runner.start()
    if stop_live and st.session_state.realtime_runner is not None:
        st.session_state.realtime_runner.stop()

    if st.session_state.realtime_runner is not None:
        pending_cfg = build_config(
            scenario_name, base_num_evs=base_num_evs, seed=seed,
        )
        st.session_state.realtime_runner.queue_changes(
            controller=CONTROLLERS[live_controller](),
            v2g_rate=v2g_rate,
            config={
                "grid_capacity_mw": pending_cfg.grid_capacity_mw,
                "solar_capacity_mw": pending_cfg.solar_capacity_mw,
                "ev_arrival_hour_range": pending_cfg.ev_arrival_hour_range,
            },
        )

# ------------------------------------------------------------- run sims ----
inputs = st.session_state.inputs
st.markdown(
    f"**Scenario:** `{inputs['scenario_name']}` — {SCENARIOS[inputs['scenario_name']]['description']}  \n"
    f"**EVs:** {inputs['base_num_evs']}  |  **Horizon:** {inputs['horizon_hours']}h  |  "
    f"**Seed:** {inputs['seed']}  |  **Source:** {'randomized' if inputs['mode'] == 'random' else 'manual'}"
)


@st.fragment(run_every="1s")
def render_realtime_panel():
    st.subheader("Live digital twin")
    runner = st.session_state.realtime_runner
    if runner is None:
        st.info("Start a real-time simulation from the sidebar to view live state.")
        return
    snapshot = runner.snapshot()
    components.html(render_live_state(snapshot), height=410, scrolling=False)
    status = "running" if snapshot["running"] else "stopped"
    st.caption(f"Status: {status} · step {snapshot['current_step']} · time {snapshot['sim_time_h']:.2f}h")


render_realtime_panel()

if run_clicked or "last_results" not in st.session_state:
    if not controller_choices:
        st.warning("Select at least one controller in the sidebar.")
        st.stop()

    results = {}
    for name in controller_choices:
        cfg = build_config(
            inputs["scenario_name"],
            base_num_evs=inputs["base_num_evs"],
            seed=inputs["seed"],
        )
        cfg.horizon_hours = inputs["horizon_hours"]
        cfg.telemetry_attack_type = inputs["attack_type"]
        cfg.telemetry_attack_probability = inputs["attack_probability"]
        cfg.telemetry_security_enabled = inputs["security_enabled"]
        cfg.v2g_participation_rate = inputs["v2g_rate"]
        controller = CONTROLLERS[name]()
        if name == "q_learning":
            controller.train(cfg, episodes=int(inputs["rl_episodes"]))
            controller.set_evaluation_mode()
        sim = Simulation(cfg, controller)
        summary = sim.run()
        results[name] = {
            "summary": summary,
            "rows": pd.DataFrame(sim.metrics.rows),
        }
    st.session_state.last_results = results

results = st.session_state.last_results

# ------------------------------------------------------------ summary ----
st.subheader("Summary")
cols = st.columns(len(results))
for col, (name, r) in zip(cols, results.items()):
    s = r["summary"]
    with col:
        st.markdown(f"**{name}**")
        for label, key, fmt in [
            ("Total cost ($)", "total_electricity_cost_usd", "{:.2f}"),
            ("Carbon (kg CO2)", "total_carbon_emissions_kg", "{:.1f}"),
            ("Peak grid load (MW)", "peak_grid_load_mw", "{:.2f}"),
            ("Steps over capacity", "steps_over_capacity", "{:d}"),
            ("EVs departed", "evs_departed", "{:d}"),
            ("% met required SOC", "pct_evs_met_required_soc", "{:.1f}"),
            ("Telemetry alerts", "telemetry_alerts", "{:d}"),
            ("High-severity alerts", "high_severity_telemetry_alerts", "{:d}"),
            ("V2G exported (kWh)", "total_v2g_energy_exported_kwh", "{:.1f}"),
        ]:
            val = s.get(key, 0)
            st.markdown(
                f'<div class="metric-card"><div class="label">{label}</div>'
                f'<div class="value">{fmt.format(val)}</div></div>',
                unsafe_allow_html=True,
            )

# -------------------------------------------------------------- charts ----
st.subheader("Grid load over time")
fig, ax = plt.subplots(figsize=(9, 3.5))
line_colors = [GREEN_MID, GREEN_LINE, GREEN_LIGHT]
for i, (name, r) in enumerate(results.items()):
    df = r["rows"]
    ax.plot(df["time_h"], df["total_load_mw"], label=f"{name} (total load)",
            color=line_colors[i % len(line_colors)], linewidth=2)
ax.set_xlabel("Time (h)")
ax.set_ylabel("Grid load (MW)")
ax.legend(frameon=False)
ax.spines[["top", "right"]].set_visible(False)
st.pyplot(fig)

st.subheader("Electricity price & carbon intensity")
first_df = next(iter(results.values()))["rows"]
fig2, ax2 = plt.subplots(figsize=(9, 3))
ax2.plot(first_df["time_h"], first_df["price"], color=GREEN_MID, linewidth=2, label="price ($/kWh)")
ax2b = ax2.twinx()
ax2b.plot(first_df["time_h"], first_df["carbon_intensity"], color=GREEN_LIGHT, linewidth=2,
          linestyle="--", label="carbon intensity (kg/kWh)")
ax2.set_xlabel("Time (h)")
ax2.set_ylabel("Price ($/kWh)", color=GREEN_MID)
ax2b.set_ylabel("Carbon intensity", color=GREEN_LIGHT)
ax2.spines[["top"]].set_visible(False)
st.pyplot(fig2)

st.subheader("Per-controller metrics table")
summary_table = pd.DataFrame({name: r["summary"] for name, r in results.items()}).T
st.dataframe(summary_table, use_container_width=True)
