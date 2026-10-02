"""
Smart Scan Strategy for Electronic Warfare — Working Prototype
================================================================
Simulates a spectrum-scanning receiver deciding, at each time step,
which single frequency band to listen to, against a mixed population
of emitters (bursty comms, a periodic beacon, and a frequency-agile
threat) sharing the same band pool.

Pipeline (the "workflow"):
    1. Environment  -> ground-truth emitter ON/OFF state per band per step
    2. Scheduler    -> picks ONE band to scan this step (this is the part
                        SIH wants "smart"/ML-driven instead of open-loop)
    3. Update       -> scheduler learns from the hit/miss it just observed
    4. Metrics      -> interception ratio, avg reward/step, avg intercept delay

Three schedulers are compared head-to-head on the identical scenario:
    - RoundRobinScheduler   : open-loop baseline (sweeps bands in order)
    - RandomScheduler       : naive baseline
    - BeliefScheduler       : closed-loop, learns a 2-state Markov model
                              per band online and scans whichever band it
                              currently believes is most likely ON
                              (a practical/myopic approximation of the
                              Whittle index used for restless-bandit
                              scheduling problems)

Run:  python3 scan_scheduler_prototype.py
"""

import random
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ----------------------------------------------------------------------
# 1. RF Environment: Emitters
# ----------------------------------------------------------------------

class Emitter:
    """Base class. Occupies one band at a time (band may change for
    hoppers) and is either transmitting or silent at that band."""
    def __init__(self, name: str):
        self.name = name
        self.band: int = -1
        self.on: bool = False

    def step(self, t: int):
        raise NotImplementedError


class MarkovEmitter(Emitter):
    """Fixed-band emitter. ON/OFF governed by a 2-state Markov chain —
    models bursty comms traffic in a known channel."""
    def __init__(self, name, band, p_on_given_off=0.15, p_on_given_on=0.85):
        super().__init__(name)
        self.band = band
        self.p_on_given_off = p_on_given_off
        self.p_on_given_on = p_on_given_on
        self.on = random.random() < 0.3

    def step(self, t):
        p = self.p_on_given_on if self.on else self.p_on_given_off
        self.on = random.random() < p
        return self.band, self.on


class PeriodicEmitter(Emitter):
    """Hops through a fixed cyclic sequence of bands, `dwell` steps per
    band (e.g. a periodic scanning radar / cyclic beacon)."""
    def __init__(self, name, band_sequence: List[int], dwell=3):
        super().__init__(name)
        self.band_sequence = band_sequence
        self.dwell = dwell
        self.on = True

    def step(self, t):
        idx = (t // self.dwell) % len(self.band_sequence)
        self.band = self.band_sequence[idx]
        self.on = True
        return self.band, self.on


class AgileEmitter(Emitter):
    """Frequency-agile emitter: hops to a random band from its pool every
    `dwell` steps, with a duty cycle. No exploitable periodicity —
    represents an LPI/LPD-style threat."""
    def __init__(self, name, bands: List[int], dwell=2, duty=0.6):
        super().__init__(name)
        self.bands = bands
        self.dwell = dwell
        self.duty = duty
        self.band = random.choice(bands)

    def step(self, t):
        if t % self.dwell == 0:
            self.band = random.choice(self.bands)
        self.on = random.random() < self.duty
        return self.band, self.on


@dataclass
class Environment:
    n_bands: int
    emitters: List[Emitter]
    t: int = 0

    def step(self) -> Dict[int, bool]:
        """Advance all emitters one step. Returns ground-truth ON/OFF
        status for every band this step (OR-combined if bands collide)."""
        status = {b: False for b in range(self.n_bands)}
        for e in self.emitters:
            band, on = e.step(self.t)
            if on:
                status[band] = True
        self.t += 1
        return status


# ----------------------------------------------------------------------
# 2. Schedulers
# ----------------------------------------------------------------------

class Scheduler:
    def __init__(self, n_bands: int):
        self.n_bands = n_bands

    def choose_band(self) -> int:
        raise NotImplementedError

    def update(self, band: int, observed_on: bool):
        """Called with the ground-truth result after scanning `band`."""
        pass


class RoundRobinScheduler(Scheduler):
    """Open-loop baseline: sweeps every band in fixed order."""
    def __init__(self, n_bands):
        super().__init__(n_bands)
        self.ptr = 0

    def choose_band(self):
        b = self.ptr
        self.ptr = (self.ptr + 1) % self.n_bands
        return b


class RandomScheduler(Scheduler):
    """Naive baseline: uniformly random band each step."""
    def choose_band(self):
        return random.randrange(self.n_bands)


class BeliefScheduler(Scheduler):
    """
    Closed-loop learned scheduler.

    For each band it online-learns a 2-state Markov model
    (P(on | off), P(on | on)) via counting, and maintains a belief
    P(band currently ON):
      - set to 0/1 exactly when the band is scanned (fully observed)
      - propagated forward via the learned transition model when NOT
        scanned (standard HMM forward step under partial observability)

    Each step it scans argmax(belief), with epsilon exploration so it
    keeps learning about rarely-scanned bands. This is a practical
    myopic approximation of the Whittle index used for restless
    multi-armed bandit scheduling.
    """
    def __init__(self, n_bands, epsilon=0.08):
        super().__init__(n_bands)
        self.epsilon = epsilon
        # Laplace-smoothed transition counts
        self.off_on = [1.0] * n_bands
        self.off_tot = [2.0] * n_bands
        self.on_on = [1.0] * n_bands
        self.on_tot = [2.0] * n_bands
        self.belief = [0.3] * n_bands
        self.last_scan_result = [None] * n_bands

    def _p_on_given_off(self, b):
        return self.off_on[b] / self.off_tot[b]

    def _p_on_given_on(self, b):
        return self.on_on[b] / self.on_tot[b]

    def _propagate(self, b):
        bel = self.belief[b]
        self.belief[b] = bel * self._p_on_given_on(b) + (1 - bel) * self._p_on_given_off(b)

    def choose_band(self):
        for b in range(self.n_bands):
            self._propagate(b)
        if random.random() < self.epsilon:
            return random.randrange(self.n_bands)
        return max(range(self.n_bands), key=lambda b: self.belief[b])

    def update(self, band, observed_on):
        prev = self.last_scan_result[band]
        if prev is not None:
            if prev:
                self.on_tot[band] += 1
                if observed_on:
                    self.on_on[band] += 1
            else:
                self.off_tot[band] += 1
                if observed_on:
                    self.off_on[band] += 1
        self.last_scan_result[band] = observed_on
        self.belief[band] = 1.0 if observed_on else 0.0


# ----------------------------------------------------------------------
# 3. Simulation loop + metrics
# ----------------------------------------------------------------------

@dataclass
class RunStats:
    total_steps: int = 0
    total_transmissions: int = 0     # steps where >=1 band was ON somewhere
    hits: int = 0                    # scanned band happened to be ON
    intercept_delays: List[int] = field(default_factory=list)
    rewards: List[int] = field(default_factory=list)

    def report(self):
        interception_ratio = self.hits / max(1, self.total_transmissions)
        avg_reward = statistics.mean(self.rewards) if self.rewards else 0.0
        avg_delay = statistics.mean(self.intercept_delays) if self.intercept_delays else None
        return {
            "interception_ratio": round(interception_ratio, 3),
            "avg_reward_per_step": round(avg_reward, 3),
            "avg_intercept_delay": round(avg_delay, 2) if avg_delay is not None else "n/a",
            "hits": self.hits,
        }


def run_episode(env_factory, scheduler: Scheduler, n_steps: int, n_bands: int) -> RunStats:
    env = env_factory()
    stats = RunStats()
    on_since: List[Optional[int]] = [None] * n_bands
    credited = [False] * n_bands

    for t in range(n_steps):
        status = env.step()

        for b in range(n_bands):
            if status[b]:
                if on_since[b] is None:
                    on_since[b] = t
                    credited[b] = False
            else:
                on_since[b] = None
                credited[b] = False

        if any(status.values()):
            stats.total_transmissions += 1

        band = scheduler.choose_band()
        observed_on = status[band]
        scheduler.update(band, observed_on)

        stats.rewards.append(1 if observed_on else 0)
        if observed_on:
            stats.hits += 1
            if on_since[band] is not None and not credited[band]:
                stats.intercept_delays.append(t - on_since[band])
                credited[band] = True
        stats.total_steps += 1

    return stats


def make_scenario(n_bands=8):
    """Mixed scene: two Markov comms channels, one periodic beacon, one
    frequency-agile threat, all sharing the same band pool."""
    def factory():
        emitters = [
            MarkovEmitter("comm-1", band=1, p_on_given_off=0.05, p_on_given_on=0.9),
            MarkovEmitter("comm-2", band=4, p_on_given_off=0.10, p_on_given_on=0.7),
            PeriodicEmitter("beacon", band_sequence=[2, 5, 6], dwell=4),
            AgileEmitter("agile-threat", bands=[0, 3, 6, 7], dwell=2, duty=0.5),
        ]
        return Environment(n_bands=n_bands, emitters=emitters)
    return factory


def main():
    random.seed(7)
    N_BANDS = 36
    n_steps = 4000
    scenario = make_scenario(N_BANDS)

    schedulers = {
        "RoundRobin (open-loop baseline)": RoundRobinScheduler(N_BANDS),
        "Random (naive baseline)": RandomScheduler(N_BANDS),
        "BeliefScheduler (learned, closed-loop)": BeliefScheduler(N_BANDS, epsilon=0.08),
    }

    print(f"Scenario: {N_BANDS} bands, {n_steps} steps, 4 concurrent emitters "
          f"(2 Markov comms, 1 periodic beacon, 1 frequency-agile threat)\n")
    header = f"{'Scheduler':40s} | {'Interception %':>15s} | {'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}"
    print(header)
    print("-" * len(header))

    for name, sched in schedulers.items():
        stats = run_episode(scenario, sched, n_steps, N_BANDS)
        r = stats.report()
        print(f"{name:40s} | {r['interception_ratio']*100:14.1f}% | "
              f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")


if __name__ == "__main__":
    main()
