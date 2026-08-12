"""
ev_digital_twin
================
Baseline software framework for the Digital Twin-based EV charging &
grid optimization research project.

This package implements Section 4-6 of the project spec:
- Digital Twin (EV / charging station / grid / renewable state)
- IoT telemetry simulation
- A simple baseline ("uncontrolled charging") controller for comparison
- A closed-loop simulation runner with metrics collection

Everything else in the roadmap (PSO, NSGA-II, hybrid optimizer,
anomaly detection, multi-agent EVs, RL, V2G, scenario/stress engine,
dashboard) plugs into this baseline in later phases.
"""

__version__ = "0.1.0"
