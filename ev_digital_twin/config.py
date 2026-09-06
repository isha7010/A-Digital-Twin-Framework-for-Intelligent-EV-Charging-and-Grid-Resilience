"""Central simulation configuration. Tune these for experiments."""

from dataclasses import dataclass, field


@dataclass
class SimulationConfig:
    # Time
    time_step_minutes: int = 15
    horizon_hours: int = 24

    # EV population
    num_evs: int = 50
    ev_battery_kwh_range: tuple = (40.0, 90.0)
    ev_max_power_kw_range: tuple = (7.0, 22.0)
    ev_arrival_hour_range: tuple = (0.0, 24.0)
    ev_stay_hours_range: tuple = (2.0, 10.0)
    ev_min_soc: float = 0.15
    ev_departure_soc: float = 0.85
    ev_charging_efficiency: float = 0.92
    v2g_participation_rate: float = 0.0
    v2g_reserve_soc: float = 0.30
    v2g_support_threshold: float = 0.85
    v2g_max_discharge_fraction: float = 0.5
    rl_training_episodes: int = 0
    rl_epsilon: float = 0.2

    # Charging stations
    num_stations: int = 16
    connectors_per_station: int = 4
    station_max_power_kw: float = 50.0

    # Grid
    grid_base_load_mw: float = 5.0
    grid_capacity_mw: float = 12.0
    carbon_intensity_base: float = 0.4  # kg CO2 / kWh

    # Electricity price ($/kWh), simple time-of-use curve keyed by hour
    price_off_peak: float = 0.10
    price_mid_peak: float = 0.18
    price_on_peak: float = 0.32
    on_peak_hours: tuple = (17, 21)
    mid_peak_hours: tuple = (7, 17)

    # Renewables
    solar_capacity_mw: float = 4.0

    # Telemetry
    telemetry_noise_std: float = 0.02  # fraction noise on readings
    telemetry_dropout_prob: float = 0.01  # chance a message is missing
    telemetry_security_enabled: bool = True
    telemetry_attack_type: str = "none"
    telemetry_attack_probability: float = 0.0

    # Random seed for reproducibility
    random_seed: int = 42
