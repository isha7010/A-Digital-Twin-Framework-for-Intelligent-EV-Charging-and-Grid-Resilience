"""Dependency-free tabular reinforcement-learning controller."""

import copy
import random


class QLearningController:
    """Learn a compact charging/V2G policy with tabular Q-learning.

    The state is an aggregate observation of grid utilization, price, solar,
    and charging urgency. One shared action is selected for the active fleet,
    while each EV applies its own power and V2G constraints.
    """

    name = "q_learning"
    ACTIONS = (-0.5, 0.0, 0.5, 1.0)

    def __init__(self, learning_rate=0.25, discount_factor=0.85,
                 epsilon=0.2, epsilon_decay=0.92, seed=None):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.rng = random.Random(seed)
        self.q_table = {}
        self.training_history = []
        self._last_state = None
        self._last_action = None

    @staticmethod
    def _bucket(value, thresholds):
        return sum(value >= threshold for threshold in thresholds)

    def _state(self, twin, active):
        capacity = max(twin.grid.capacity_mw, 0.001)
        load_ratio = twin.grid.base_load_mw / capacity
        price = twin.grid.current_price
        solar_ratio = twin.solar_mw / max(twin.cfg.solar_capacity_mw, 0.001)
        urgency = 0.0
        if active:
            urgency = sum(
                ev.energy_needed_kwh() / max(ev.departure_deadline_h - twin.sim_time_h, 0.5)
                for ev in active
            ) / sum(max(ev.max_power_kw, 0.001) for ev in active)
        return (
            self._bucket(load_ratio, (0.65, 0.85, 1.0)),
            self._bucket(price, (0.12, 0.22)),
            self._bucket(solar_ratio, (0.25, 0.65)),
            self._bucket(urgency, (0.35, 0.75, 1.0)),
        )

    def _values(self, state):
        return self.q_table.setdefault(state, [0.0] * len(self.ACTIONS))

    def _reward(self, twin, active, action):
        total_power_kw = 0.0
        export_kw = 0.0
        unmet = 0.0
        for ev in active:
            if action < 0 and ev.v2g_participant and ev.soc > twin.cfg.v2g_reserve_soc:
                export_kw += min(ev.max_power_kw * abs(action),
                                 (ev.soc - twin.cfg.v2g_reserve_soc) * ev.battery_kwh /
                                 max(twin.dt_hours, 0.001))
            elif action > 0:
                total_power_kw += ev.max_power_kw * action
                unmet += max(0.0, ev.energy_needed_kwh() - total_power_kw * twin.dt_hours * ev.efficiency)
        load_mw = twin.grid.base_load_mw + total_power_kw / 1000.0 - export_kw / 1000.0
        overload = max(0.0, load_mw - twin.grid.capacity_mw)
        cost = total_power_kw * twin.dt_hours * twin.grid.current_price
        carbon = total_power_kw * twin.dt_hours * twin.grid.carbon_intensity
        return -(cost + carbon + 100.0 * overload + 0.05 * unmet) + 0.03 * export_kw

    def _update(self, reward, next_state):
        if self._last_state is None:
            return
        values = self._values(self._last_state)
        next_best = max(self._values(next_state))
        target = reward + self.discount_factor * next_best
        values[self._last_action] += self.learning_rate * (target - values[self._last_action])

    def decide(self, twin):
        active = [ev for ev in twin.evs.values()
                  if ev.connected_station is not None and ev.soc < ev.departure_soc]
        if not active:
            self._last_state = None
            self._last_action = None
            return {}
        state = self._state(twin, active)
        if self.rng.random() < self.epsilon:
            action_index = self.rng.randrange(len(self.ACTIONS))
        else:
            action_index = max(range(len(self.ACTIONS)), key=lambda index: self._values(state)[index])
        action = self.ACTIONS[action_index]
        self._update(self._reward(twin, active, action), state)
        self._last_state = state
        self._last_action = action_index

        decisions = {}
        for ev in active:
            if action < 0 and ev.v2g_participant and ev.soc > twin.cfg.v2g_reserve_soc:
                decisions[ev.ev_id] = -ev.max_power_kw * abs(action)
            elif action > 0:
                decisions[ev.ev_id] = ev.max_power_kw * action
            else:
                decisions[ev.ev_id] = 0.0
        return decisions

    def train(self, cfg, episodes=5):
        """Run simulator episodes to learn a reusable policy."""
        from .simulation import Simulation

        for episode in range(max(0, episodes)):
            episode_cfg = copy.deepcopy(cfg)
            episode_cfg.random_seed = cfg.random_seed + episode
            self.reset_episode()
            Simulation(episode_cfg, self).run()
            self.training_history.append({
                "episode": episode + 1,
                "states": len(self.q_table),
            })
            self.epsilon *= self.epsilon_decay
        return self.training_history

    def reset_episode(self):
        self._last_state = None
        self._last_action = None

    def set_evaluation_mode(self):
        self.epsilon = 0.0
        self.reset_episode()
