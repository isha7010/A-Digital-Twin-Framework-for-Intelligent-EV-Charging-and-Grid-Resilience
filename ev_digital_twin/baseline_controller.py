"""
Baseline charging strategy: uncontrolled ("charge immediately at max
power") charging. This is the reference point every later optimizer
(PSO, NSGA-II, hybrid, RL) should be compared against.
"""

import random


class UncontrolledController:
    """Every connected EV charges at its maximum power until full."""

    name = "uncontrolled"

    def decide(self, twin) -> dict:
        decisions = {}
        for ev in twin.evs.values():
            if ev.connected_station is None:
                continue
            if ev.soc >= ev.departure_soc:
                decisions[ev.ev_id] = 0.0
            else:
                decisions[ev.ev_id] = ev.max_power_kw
        return decisions


class EarliestDeadlineFirstController:
    """
    A slightly smarter rule-based baseline: EVs with the soonest departure
    deadline get charging priority when the grid is near capacity.
    Useful as a second reference point before introducing PSO-NSGA-II.
    """

    name = "earliest_deadline_first"

    def __init__(self, headroom_mw: float = None):
        self.headroom_mw = headroom_mw

    def decide(self, twin) -> dict:
        active = [ev for ev in twin.evs.values()
                  if ev.connected_station is not None and ev.soc < ev.departure_soc]
        active.sort(key=lambda ev: ev.departure_deadline_h)

        capacity_mw = self.headroom_mw if self.headroom_mw is not None else twin.grid.capacity_mw
        remaining_mw = max(0.0, capacity_mw - twin.grid.base_load_mw)
        remaining_kw = remaining_mw * 1000.0

        decisions = {}
        for ev in active:
            power = min(ev.max_power_kw, remaining_kw)
            power = max(0.0, power)
            decisions[ev.ev_id] = power
            remaining_kw -= power
        return decisions


class PSOController:
    """
    A lightweight PSO controller for the baseline digital twin.

    The controller keeps a small swarm of candidate charging vectors,
    evaluates each vector against the current twin state using the same
    cost/carbon/over-capacity/SOC risks already represented by the metrics
    module, and returns the best candidate decision for the current step.
    """

    name = "pso"

    def __init__(self, num_particles: int = 12, iterations: int = 5,
                 inertia: float = 0.7, cognitive: float = 1.4,
                 social: float = 1.6, seed: int = None,
                 weights: dict = None):
        self.num_particles = num_particles
        self.iterations = iterations
        self.inertia = inertia
        self.cognitive = cognitive
        self.social = social
        self.rng = random.Random(seed)
        self.weights = {
            "cost": 1.0,
            "carbon": 1.0,
            "overload": 5.0,
            "soc": 10.0,
        }
        if weights:
            self.weights.update(weights)
        self.history = []

    def _required_power_kw(self, ev, twin) -> float:
        remaining_h = max(ev.departure_deadline_h - twin.sim_time_h, 0.5)
        energy_needed_kwh = max(0.0, ev.energy_needed_kwh())
        needed_kw = (energy_needed_kwh / remaining_h) / max(ev.efficiency, 0.001)
        return min(max(0.0, needed_kw), ev.max_power_kw)

    def _objective(self, twin, decisions: dict) -> float:
        active = [ev for ev in twin.evs.values()
                  if ev.connected_station is not None and ev.soc < ev.departure_soc]
        if not active:
            return 0.0

        total_load_mw = twin.grid.base_load_mw
        for ev in active:
            power_kw = decisions.get(ev.ev_id, 0.0)
            total_load_mw += max(0.0, power_kw) / 1000.0
        total_load_mw = max(0.0, total_load_mw)

        cost_penalty = self.weights["cost"] * total_load_mw * 1000.0 * twin.dt_hours * twin.grid.current_price
        carbon_penalty = self.weights["carbon"] * total_load_mw * 1000.0 * twin.dt_hours * twin.grid.carbon_intensity

        overload_penalty = 0.0
        if total_load_mw > twin.grid.capacity_mw:
            overload_penalty = self.weights["overload"] * 5000.0 * (total_load_mw - twin.grid.capacity_mw)

        soc_penalty = 0.0
        for ev in active:
            power_kw = decisions.get(ev.ev_id, 0.0)
            delivered_kwh = power_kw * twin.dt_hours * ev.efficiency
            required_kwh = ev.energy_needed_kwh()
            if required_kwh > 0.0:
                shortfall = max(0.0, required_kwh - delivered_kwh)
                soc_penalty += self.weights["soc"] * 500.0 * shortfall

        objective = cost_penalty + carbon_penalty + overload_penalty + soc_penalty
        self.history.append(objective)
        return objective

    def _normalize_candidate(self, candidate: list[float], max_power_by_ev: list[float], grid_limit_kw: float) -> list[float]:
        candidate = [max(0.0, min(max_power_by_ev[i], candidate[i])) for i in range(len(candidate))]
        total = sum(candidate)
        if total > grid_limit_kw and total > 0.0:
            scale = grid_limit_kw / total
            candidate = [v * scale for v in candidate]
        return candidate

    def decide(self, twin) -> dict:
        active = [ev for ev in twin.evs.values()
                  if ev.connected_station is not None and ev.soc < ev.departure_soc]
        if not active:
            return {}

        active.sort(key=lambda ev: (ev.departure_deadline_h, ev.soc))
        grid_limit_kw = max(0.0, (twin.grid.capacity_mw - twin.grid.base_load_mw) * 1000.0)
        max_power_by_ev = [ev.max_power_kw for ev in active]
        base_targets = [self._required_power_kw(ev, twin) for ev in active]

        particles = []
        velocities = []
        pbest_positions = []
        pbest_scores = []

        for _ in range(self.num_particles):
            position = []
            velocity = []
            for idx, ev in enumerate(active):
                target = base_targets[idx]
                jitter = self.rng.uniform(0.0, max(1.0, target * 0.8))
                value = max(0.0, min(max_power_by_ev[idx], target + jitter - (target * 0.5)))
                position.append(value)
                velocity.append(self.rng.uniform(-max(1.0, target * 0.5), max(1.0, target * 0.5)))
            position = self._normalize_candidate(position, max_power_by_ev, grid_limit_kw)
            particles.append(position)
            velocities.append(velocity)
            score = self._objective(twin, dict(zip([ev.ev_id for ev in active], position)))
            pbest_positions.append(position[:])
            pbest_scores.append(score)

        gbest_index = min(range(len(pbest_scores)), key=lambda i: pbest_scores[i])
        gbest_position = pbest_positions[gbest_index][:]
        gbest_score = pbest_scores[gbest_index]

        for _ in range(self.iterations):
            for i in range(self.num_particles):
                for j in range(len(active)):
                    r1 = self.rng.random()
                    r2 = self.rng.random()
                    velocity = (
                        self.inertia * velocities[i][j]
                        + self.cognitive * r1 * (pbest_positions[i][j] - particles[i][j])
                        + self.social * r2 * (gbest_position[j] - particles[i][j])
                    )
                    velocities[i][j] = velocity
                    particles[i][j] = max(0.0, min(max_power_by_ev[j], particles[i][j] + velocity))

                particles[i] = self._normalize_candidate(particles[i], max_power_by_ev, grid_limit_kw)
                score = self._objective(twin, dict(zip([ev.ev_id for ev in active], particles[i])))
                if score < pbest_scores[i]:
                    pbest_positions[i] = particles[i][:]
                    pbest_scores[i] = score

                if pbest_scores[i] < gbest_score:
                    gbest_score = pbest_scores[i]
                    gbest_position = pbest_positions[i][:]

        best_decisions = {ev.ev_id: gbest_position[idx] for idx, ev in enumerate(active)}
        return best_decisions


class NSGAIIController:
    """
    A lightweight multi-objective optimizer inspired by NSGA-II.

    It keeps a small population of charging vectors and ranks candidates
    using Pareto dominance across the key objectives already represented in
    the simulator: cost, carbon, grid peak load, and missed SOC risk.
    """

    name = "nsga2"

    def __init__(self, population_size: int = 8, generations: int = 4, seed: int = None):
        self.population_size = population_size
        self.generations = generations
        self.rng = random.Random(seed)

    def _make_candidate(self, active, twin):
        values = []
        for ev in active:
            target = max(0.0, min(ev.max_power_kw, ev.energy_needed_kwh() / max(1.0, ev.departure_deadline_h - twin.sim_time_h)))
            noise = self.rng.uniform(0.0, target * 0.8)
            values.append(max(0.0, min(ev.max_power_kw, target + noise)))
        return values

    def _dominates(self, a, b):
        better_or_equal = True
        strictly_better = False
        for ai, bi in zip(a, b):
            if ai < bi:
                better_or_equal = False
                break
            if ai > bi:
                strictly_better = True
        return better_or_equal and strictly_better

    def _objective_vector(self, twin, decisions: dict, active):
        total_load_mw = twin.grid.base_load_mw
        total_cost = 0.0
        total_carbon = 0.0
        unmet_soc = 0.0
        for ev in active:
            power_kw = decisions.get(ev.ev_id, 0.0)
            total_load_mw += max(0.0, power_kw) / 1000.0
            total_cost += max(0.0, power_kw) * twin.dt_hours * twin.grid.current_price
            total_carbon += max(0.0, power_kw) * twin.dt_hours * twin.grid.carbon_intensity
            shortfall = max(0.0, ev.energy_needed_kwh() - power_kw * twin.dt_hours * ev.efficiency)
            unmet_soc += shortfall
        overload = max(0.0, total_load_mw - twin.grid.capacity_mw)
        return [total_cost, total_carbon, overload, unmet_soc]

    def decide(self, twin) -> dict:
        active = [ev for ev in twin.evs.values()
                  if ev.connected_station is not None and ev.soc < ev.departure_soc]
        if not active:
            return {}

        active.sort(key=lambda ev: (ev.departure_deadline_h, ev.soc))
        population = []
        for _ in range(self.population_size):
            candidate = self._make_candidate(active, twin)
            objective = self._objective_vector(twin, dict(zip([ev.ev_id for ev in active], candidate)), active)
            population.append({"values": candidate, "objective": objective})

        for _ in range(self.generations):
            candidates = []
            for p in population:
                mutated = p["values"][:]
                idx = self.rng.randrange(len(mutated))
                mutated[idx] = max(0.0, min(active[idx].max_power_kw, mutated[idx] + self.rng.uniform(-2.0, 2.0)))
                objective = self._objective_vector(twin, dict(zip([ev.ev_id for ev in active], mutated)), active)
                candidates.append({"values": mutated, "objective": objective})
            population.extend(candidates)

            non_dominated = []
            for candidate in population:
                dominated = False
                for other in population:
                    if other is candidate and len(population) > 1:
                        continue
                    if self._dominates(other["objective"], candidate["objective"]):
                        dominated = True
                        break
                if not dominated:
                    non_dominated.append(candidate)

            if non_dominated:
                population = non_dominated[:self.population_size]
            else:
                population = population[:self.population_size]

        best = min(population, key=lambda p: sum(p["objective"]))
        return {ev.ev_id: best["values"][idx] for idx, ev in enumerate(active)}
