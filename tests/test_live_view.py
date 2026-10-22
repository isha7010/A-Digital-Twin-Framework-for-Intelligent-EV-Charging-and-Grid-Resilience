import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ev_digital_twin.live_view import render_live_state


def test_live_view_renders_all_station_grids_and_connectors():
    snapshot = {
        "running": True,
        "state": {
            "time_h": 1.5,
            "grid": {"capacity_mw": 12.0, "net_load_mw": 8.0,
                     "solar_mw": 2.0, "v2g_export_mw": 0.5},
            "stations": [
                {"station_id": f"CS_{index:03d}",
                 "occupancy": {0: f"EV_{index:03d}" if index == 0 else None}}
                for index in range(16)
            ],
            "evs": [{"ev_id": "EV_000", "state": "charging", "soc": 0.5}],
        },
    }
    rendered = render_live_state(snapshot)

    assert rendered.count('aria-label="Station grid') == 4
    assert rendered.count("<svg") == 4
    assert "CS_000" in rendered
    assert "Net load" in rendered
    assert "Charging" in rendered


def test_live_view_escapes_runner_errors_and_supports_string_connectors():
    snapshot = {
        "error": "<failure>",
        "state": {
            "grid": {"capacity_mw": 1.0, "net_load_mw": 2.0},
            "stations": [{"station_id": "CS_000",
                          "occupancy": {"0": "EV_000"}}],
            "evs": [{"ev_id": "EV_000", "state": "idle", "soc": 1.2}],
        },
    }
    rendered = render_live_state(snapshot)

    assert "Live runner error: &lt;failure&gt;" in rendered
    assert "<failure>" not in rendered
    assert "width=\"12\" height=\"24.0\"" in rendered
