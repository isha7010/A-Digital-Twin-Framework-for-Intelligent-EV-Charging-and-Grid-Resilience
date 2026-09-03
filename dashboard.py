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

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from ev_digital_twin.scenarios import SCENARIOS, build_config, randomize_inputs
from ev_digital_twin.simulation import Simulation
from ev_digital_twin.baseline_controller import (
    UncontrolledController,
    EarliestDeadlineFirstController,
    PSOController,
    NSGAIIController,
    HybridPSONSGAIIController,
)

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
}

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
    }

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

    st.session_state.inputs = {
        "mode": "manual",
        "scenario_name": scenario_name,
        "base_num_evs": base_num_evs,
        "seed": seed,
        "horizon_hours": horizon_hours,
        "attack_type": attack_type,
        "attack_probability": attack_probability,
        "security_enabled": security_enabled,
    }

    st.divider()
    controller_choices = st.multiselect(
        "Controllers to compare",
        list(CONTROLLERS.keys()),
        default=["uncontrolled", "edf"],
    )
    run_clicked = st.button("▶ Run simulation", type="primary", use_container_width=True)

# ------------------------------------------------------------- run sims ----
inputs = st.session_state.inputs
st.markdown(
    f"**Scenario:** `{inputs['scenario_name']}` — {SCENARIOS[inputs['scenario_name']]['description']}  \n"
    f"**EVs:** {inputs['base_num_evs']}  |  **Horizon:** {inputs['horizon_hours']}h  |  "
    f"**Seed:** {inputs['seed']}  |  **Source:** {'randomized' if inputs['mode'] == 'random' else 'manual'}"
)

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
        controller = CONTROLLERS[name]()
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
