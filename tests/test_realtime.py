import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ev_digital_twin.baseline_controller import EarliestDeadlineFirstController
from ev_digital_twin.config import SimulationConfig
from ev_digital_twin.realtime_runner import RealtimeRunner
from ev_digital_twin.simulation import Simulation


def make_realtime_cfg():
    return SimulationConfig(
        num_evs=8,
        num_stations=8,
        horizon_hours=1,
        ev_arrival_hour_range=(0.0, 0.0),
        telemetry_noise_std=0.0,
        telemetry_dropout_prob=0.0,
        random_seed=123,
    )


def test_realtime_matches_batch_simulation():
    batch_cfg = make_realtime_cfg()
    batch = Simulation(batch_cfg, EarliestDeadlineFirstController())
    batch_summary = batch.run()

    realtime_cfg = make_realtime_cfg()
    realtime = RealtimeRunner(realtime_cfg, EarliestDeadlineFirstController(), tick_seconds=0.001)
    realtime.start()
    assert realtime.wait_until_finished(timeout=10.0)

    assert realtime.summary() == batch_summary
    assert realtime.state.metrics.rows == batch.metrics.rows
    assert realtime.state.current_step == len(batch.metrics.rows)


def test_pending_controller_change_applies_at_tick_boundary():
    runner = RealtimeRunner(make_realtime_cfg(), EarliestDeadlineFirstController(), tick_seconds=0.001)
    runner.queue_changes(config={"grid_capacity_mw": 8.0})
    assert runner.tick()
    assert runner.state.twin.cfg.grid_capacity_mw == 8.0
    assert runner.state.twin.grid.capacity_mw == 8.0
    runner.stop()
