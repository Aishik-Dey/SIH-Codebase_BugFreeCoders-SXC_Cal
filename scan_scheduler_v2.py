"""
scan_scheduler_v2.py
======================
Two concrete upgrades over BeliefScheduler in scan_scheduler_prototype.py:

  1. UCB-style exploration bonus instead of fixed epsilon-greedy.
     Each band gets a bonus that shrinks as it's scanned more, so the
     scheduler explores hard early and locks onto productive bands
     later -- no epsilon to hand-tune, and no exploration budget wasted
     once a band's behaviour is well understood.

  2. Multi-channel scanning: the receiver can dwell on k bands per step
     (a digital channelizer / multi-channel ESM receiver), not just one.
     All three schedulers (RoundRobin, Random, BeliefUCB) now expose
     choose_bands(k) and scan k bands per step.

Run:  python3 scan_scheduler_v2.py
"""

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional  # Dict already used by run_episode below

from scan_scheduler_prototype import (
    MarkovEmitter, PeriodicEmitter, AgileEmitter, Environment, make_scenario
)


# ----------------------------------------------------------------------
# Schedulers (multi-channel interface)
# ----------------------------------------------------------------------

def recommended_warmup_dwell(switch_cost_steps: int, warmup_steps: int, margin: int = 2):
    """Given a real switch_cost_steps and the warmup_steps you'd use if
    switching were free, returns (warmup_dwell_steps, scaled_warmup_steps)
    that keep the warmup sweep's per-band expected-hit count comparable to
    the switch_cost_steps=0 case.

    Validated (validate_warmup_dwell_fix.py, 30 seeds) that dwell =
    switch_cost_steps + 1 (bare minimum: settle, then one valid look) is
    NOT enough margin -- the per-visit valid-observation rate is still too
    thin relative to jitter overhead, and lock-on stays poor even with
    jitter enabled. dwell = switch_cost_steps + margin (margin=2 by
    default) gives real, majority-seed lock-on (23-25/30 seeds locking on
    across cost=1 and cost=2 in that validation).

    Because each dwell visit "wastes" switch_cost_steps of its length just
    settling, a fixed warmup_steps budget fits proportionally fewer full
    sweeps once dwell>1 -- so warmup_steps must scale up by roughly
    dwell/(dwell - switch_cost_steps) to keep the same expected number of
    valid per-band observations as the switch_cost_steps=0 case.

    warmup_dwell_jitter should stay ON (its default, 1) whenever dwell>1:
    validated that dwell alone, with NO jitter, fails deterministically
    (0% lock-on across every single one of 30 seeds, not just on average)
    due to a fixed-parity aliasing between "settling" and "valid" steps --
    see the class docstring on _warmup_bands.
    """
    if switch_cost_steps <= 0:
        return 1, warmup_steps
    dwell = switch_cost_steps + margin
    scaled_warmup = int(round(warmup_steps * dwell / (dwell - switch_cost_steps)))
    return dwell, scaled_warmup


class Scheduler:
    def __init__(self, n_bands: int):
        self.n_bands = n_bands

    def choose_bands(self, k: int) -> List[int]:
        raise NotImplementedError

    def update(self, band: int, observed_on: bool):
        pass


class RoundRobinScheduler(Scheduler):
    def __init__(self, n_bands):
        super().__init__(n_bands)
        self.ptr = 0

    def choose_bands(self, k):
        bands = [(self.ptr + i) % self.n_bands for i in range(k)]
        self.ptr = (self.ptr + k) % self.n_bands
        return bands


class RandomScheduler(Scheduler):
    def choose_bands(self, k):
        return random.sample(range(self.n_bands), min(k, self.n_bands))


class BeliefUCBScheduler(Scheduler):
    """
    Learns a per-band 2-state Markov model online (same as BeliefScheduler),
    but replaces fixed-epsilon exploration with a UCB1-style optimism
    bonus: score(b) = priority(b) * belief(b) + c * sqrt(log(t+1) / (scans(b)+1)).
    Scans the top-k bands by score each step.

    `priority` lets you tell the scheduler some bands matter more than
    others regardless of how often they transmit -- e.g. a rare,
    disciplined fixed-PRI radar should outrank a loud, harmless comms
    channel even though the comms channel is easier to rack up
    interception "credit" against. Without this, a scheduler that only
    maximizes raw interception count will always favor loud, easy
    sources over rare, important ones (see the fixed-PRI-radar-vs-comm-1
    trade-off this was built to address). The exploration bonus is left
    unweighted so priority shapes exploitation, not how eagerly a band's
    true behaviour gets learned in the first place.
    """
    def __init__(self, n_bands, ucb_c: float = 0.5, warmup_steps: int = 0,
                 priority: Optional[List[float]] = None,
                 warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1):
        super().__init__(n_bands)
        self.ucb_c = ucb_c
        self.warmup_steps = warmup_steps
        self.priority = list(priority) if priority is not None else [1.0] * n_bands
        self.off_on = [1.0] * n_bands
        self.off_tot = [2.0] * n_bands
        self.on_on = [1.0] * n_bands
        self.on_tot = [2.0] * n_bands
        self.belief = [0.3] * n_bands
        self.last_scan_result = [None] * n_bands
        self.scan_count = [0] * n_bands
        self.t = 0
        self._warmup_order: List[int] = []
        self._warmup_idx = 0
        # --- warm-up dwell (for use with switch_cost_steps>0) ---
        # Default 1 reproduces the ORIGINAL behaviour exactly: a fresh
        # band every single warmup call, no repeats. That's fine when
        # switching is free, but under a real switch_cost_steps>0 the
        # warmup sweep itself switches on every step -- exactly the
        # RoundRobin failure mode -- so it can NEVER accumulate a valid
        # (post-settling) observation and lock-on never happens at all.
        #
        # Setting warmup_dwell_steps > 1 makes the warmup sweep camp on
        # each band for multiple consecutive steps (enough for the
        # switch to settle and still get >=1 valid look), instead of
        # hopping every step. Found the hard way that dwell alone isn't
        # enough and can even make things WORSE: a *fixed* dwell width
        # creates a *fixed* parity between "settling" and "valid" steps
        # relative to the sweep's lap length, and a periodic emitter
        # whose true phase happens to fall on the settling parity is
        # then structurally unreachable forever, no matter how long you
        # run it -- a new instance of the exact scan/emitter-period
        # aliasing problem the original warmup *shuffle* was built to
        # avoid. warmup_dwell_jitter randomizes each dwell's length by
        # 0..warmup_dwell_jitter extra steps, which breaks that fixed
        # parity the same way shuffling broke the fixed-rotation
        # aliasing. Set to 0 to disable jitter (not recommended once
        # dwell > 1).
        self.warmup_dwell_steps = warmup_dwell_steps
        self.warmup_dwell_jitter = warmup_dwell_jitter
        self._warmup_slots: List[Dict[str, int]] = []

    def _p_on_given_off(self, b):
        return self.off_on[b] / self.off_tot[b]

    def _p_on_given_on(self, b):
        return self.on_on[b] / self.on_tot[b]

    def _propagate(self, b):
        bel = self.belief[b]
        self.belief[b] = bel * self._p_on_given_on(b) + (1 - bel) * self._p_on_given_off(b)

    def _next_warmup_band(self):
        """Pull the next band from a freshly-shuffled-per-lap sweep order
        (shuffling, not a fixed rotation, is what avoids a permanent
        scan/emitter-period aliasing blind spot -- see class docstring
        on _warmup_bands' original purpose)."""
        if self._warmup_idx >= len(self._warmup_order):
            self._warmup_order = list(range(self.n_bands))
            random.shuffle(self._warmup_order)
            self._warmup_idx = 0
        band = self._warmup_order[self._warmup_idx]
        self._warmup_idx += 1
        return band

    def _warmup_bands(self, k):
        """Choose k warmup bands, one per receiver channel/slot. Each
        slot independently sweeps the shuffled band order, but DWELLS on
        its current band for warmup_dwell_steps (+jitter) calls before
        advancing, instead of moving to a new band every single call.

        With warmup_dwell_steps=1 (the default) each slot advances every
        call -- identical to the original behaviour, byte-for-byte.
        Dwelling matters once switch_cost_steps>0 is used together with
        warmup: without it, the warmup sweep switches bands on literally
        every step (same failure mode as RoundRobin), so under any real
        switch cost it never survives settling long enough to get a
        single valid look -- lock-on can never even begin. Dwelling
        gives each visit enough consecutive steps for a switch to settle
        and still leave >=1 valid observation.

        The jitter matters because a *fixed* dwell width creates a
        *fixed* parity between "settling" and "valid" steps relative to
        the sweep's lap length -- and an emitter whose true phase lands
        on that settling parity would otherwise be permanently
        unreachable, no matter how long the run. Randomizing each dwell's
        length by a small amount breaks that fixed parity."""
        if len(self._warmup_slots) < k:
            self._warmup_slots.extend(
                {"band": -1, "remaining": 0} for _ in range(k - len(self._warmup_slots))
            )
        bands = []
        for slot in self._warmup_slots[:k]:
            if slot["remaining"] <= 0:
                slot["band"] = self._next_warmup_band()
                jitter = (random.randint(0, self.warmup_dwell_jitter)
                          if self.warmup_dwell_steps > 1 and self.warmup_dwell_jitter > 0
                          else 0)
                slot["remaining"] = self.warmup_dwell_steps + jitter
            bands.append(slot["band"])
            slot["remaining"] -= 1
        return bands

    def choose_bands(self, k):
        self.t += 1
        if self.t <= self.warmup_steps:
            for b in range(self.n_bands):
                self._propagate(b)
            return self._warmup_bands(k)
        for b in range(self.n_bands):
            self._propagate(b)
        scores = [
            self.priority[b] * self.belief[b]
            + self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
            for b in range(self.n_bands)
        ]
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
        return order[:k]

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
        self.scan_count[band] += 1


# ----------------------------------------------------------------------
# Simulation loop (multi-channel) + metrics
# ----------------------------------------------------------------------

@dataclass
class RunStats:
    total_steps: int = 0
    total_band_transmissions: int = 0   # sum over steps of #bands ON
    hits: int = 0                        # #(band,step) pairs scanned AND on
    intercept_delays: List[int] = field(default_factory=list)
    step_hit_rewards: List[int] = field(default_factory=list)  # 1 if >=1 hit this step
    switches: int = 0                    # #times a chosen band differed from last step
    wasted_scans: int = 0                # #scan-steps spent settling after a switch, unable to observe

    def report(self):
        interception_ratio = self.hits / max(1, self.total_band_transmissions)
        avg_reward = statistics.mean(self.step_hit_rewards) if self.step_hit_rewards else 0.0
        avg_delay = statistics.mean(self.intercept_delays) if self.intercept_delays else None
        return {
            "interception_ratio": round(interception_ratio, 3),
            "avg_reward_per_step": round(avg_reward, 3),
            "avg_intercept_delay": round(avg_delay, 2) if avg_delay is not None else "n/a",
            "switches": self.switches,
            "wasted_scans": self.wasted_scans,
        }


def run_episode(env_factory, scheduler: Scheduler, n_steps: int, n_bands: int, k_channels: int = 1,
                 switch_cost_steps: int = 0) -> RunStats:
    """switch_cost_steps models real receiver hardware needing time to
    re-tune (LO/filter settling) when the scheduler moves a channel to a
    band it wasn't already parked on. Default 0 preserves every existing
    result exactly (this is purely opt-in) -- set > 0 to see how the
    comparisons change once switching isn't free.

    When a channel switches to a band it wasn't scanning last step, that
    band is unobservable for the next `switch_cost_steps` steps: no
    scheduler.update() call happens (its belief model isn't corrupted
    with a fabricated observation -- it just gets no information, same
    as a real receiver that isn't listening yet), and no hit/interception
    credit is given even if the band was genuinely transmitting during
    that window. Time still advances and the channel is still tied up on
    that band (it can't scan elsewhere while settling), so this is a
    real, direct cost -- not merely a delayed observation.

    A revisited band (scanned before, then left, then scanned again)
    pays the full switch cost again, matching real hardware: the LO was
    retuned elsewhere in between, so there's nothing to still be "warm."
    """
    env = env_factory()
    stats = RunStats()
    on_since = [None] * n_bands
    credited = [False] * n_bands
    prev_bands = set()
    settling_remaining: Dict[int, int] = {}

    for t in range(n_steps):
        status: Dict[int, bool] = env.step()

        for b in range(n_bands):
            if status[b]:
                stats.total_band_transmissions += 1
                if on_since[b] is None:
                    on_since[b] = t
                    credited[b] = False
            else:
                on_since[b] = None
                credited[b] = False

        bands = scheduler.choose_bands(k_channels)
        step_hit = False
        for band in bands:
            if switch_cost_steps > 0:
                if band not in prev_bands:
                    settling_remaining[band] = switch_cost_steps
                    stats.switches += 1
                if settling_remaining.get(band, 0) > 0:
                    settling_remaining[band] -= 1
                    stats.wasted_scans += 1
                    continue  # tied up settling -- no valid observation this step

            observed_on = status[band]
            scheduler.update(band, observed_on)
            if observed_on:
                step_hit = True
                stats.hits += 1
                if on_since[band] is not None and not credited[band]:
                    stats.intercept_delays.append(t - on_since[band])
                    credited[band] = True

        stats.step_hit_rewards.append(1 if step_hit else 0)
        stats.total_steps += 1
        prev_bands = set(bands)

    return stats


def main():
    N_BANDS = 36
    n_steps = 4000
    scenario = make_scenario(N_BANDS)

    print(f"Scenario: {N_BANDS} bands, {n_steps} steps, 4 concurrent emitters "
          f"(2 Markov comms, 1 periodic beacon, 1 frequency-agile threat)\n")

    for k in (1, 2, 3):
        random.seed(7)
        print(f"--- k_channels = {k} (receiver scans {k} band(s) per step) ---")
        schedulers = {
            "RoundRobin (open-loop baseline)": RoundRobinScheduler(N_BANDS),
            "Random (naive baseline)": RandomScheduler(N_BANDS),
            "BeliefUCB (learned, closed-loop)": BeliefUCBScheduler(N_BANDS, ucb_c=0.5),
        }
        header = (f"{'Scheduler':40s} | {'Interception %':>15s} | "
                  f"{'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}")
        print(header)
        print("-" * len(header))
        for name, sched in schedulers.items():
            stats = run_episode(scenario, sched, n_steps, N_BANDS, k_channels=k)
            r = stats.report()
            print(f"{name:40s} | {r['interception_ratio']*100:14.1f}% | "
                  f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")
        print()


if __name__ == "__main__":
    main()
