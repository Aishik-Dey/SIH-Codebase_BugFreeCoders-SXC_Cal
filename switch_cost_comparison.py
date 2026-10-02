"""
switch_cost_comparison.py
============================
Every result in this project so far assumed band-hopping is free and
instant. Real ESM/receiver hardware needs real time to re-tune (local
oscillator settling, filter settling) when moving to a band it wasn't
already parked on -- typically low microseconds to low tens of
microseconds for a fast synthesizer, which at a 20us dwell (the
fine-dwell setting used for the fractional-PRI PDW work) is not
negligible relative to a single dwell.

scan_scheduler_v2.py's run_episode() now takes a switch_cost_steps
parameter (default 0, fully backward compatible -- verified byte-for-
byte identical to every existing headline number in this project). When
> 0: any channel moved to a band it wasn't scanning last step is
unobservable for that many steps (busy settling, no update() call, no
hit credit), even if the band is genuinely transmitting.

This matters most for scheduling STRATEGY, not just raw numbers:
RoundRobin moves to a new band on literally every single step by
construction, so it should be hurt by a switch cost far more than a
learned scheduler that tends to camp on one productive band once it's
found one. This script checks whether that intuition holds, and by how
much, across the standard comparisons already used throughout the
project (beacon scenario at k=1..3, and the sparse fixed-PRI radar's
per-emitter capture).

Run: python3 switch_cost_comparison.py
"""

import random
from typing import Dict, List

from scan_scheduler_v2 import (
    RoundRobinScheduler, RandomScheduler, BeliefUCBScheduler, run_episode,
    recommended_warmup_dwell
)
from scan_scheduler_prototype import make_scenario
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario

SWITCH_COSTS = [0, 1, 2, 4]  # steps of settling time per switch


def beacon_sweep():
    n_bands = 36
    n_steps = 4000
    scenario = make_scenario(n_bands)

    for k in (1, 2, 3):
        print(f"--- Beacon scenario, k_channels={k} ---")
        header = f"{'switch_cost':>11s} | " + " | ".join(f"{name:>13s}" for name in
                  ("RoundRobin", "Random", "BeliefUCB"))
        print(header)
        print("-" * len(header))
        for cost in SWITCH_COSTS:
            row = [f"{cost:11d}"]
            for cls, name in [(RoundRobinScheduler, "RoundRobin"), (RandomScheduler, "Random"),
                               (BeliefUCBScheduler, "BeliefUCB")]:
                random.seed(7)
                sched = cls(n_bands) if cls is not BeliefUCBScheduler else cls(n_bands, ucb_c=0.5)
                stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k,
                                     switch_cost_steps=cost)
                r = stats.report()
                row.append(f"{r['interception_ratio']*100:12.1f}%")
            print(" | ".join(row))
        print()


def beacon_switches_breakdown():
    """How often does each scheduler actually switch bands? This is
    what determines how much a switch cost hurts it."""
    n_bands = 36
    n_steps = 4000
    scenario = make_scenario(n_bands)
    print("--- How many band-switches does each scheduler make? (k=1, 4000 steps) ---")
    for cls, name in [(RoundRobinScheduler, "RoundRobin"), (RandomScheduler, "Random"),
                       (BeliefUCBScheduler, "BeliefUCB")]:
        random.seed(7)
        sched = cls(n_bands) if cls is not BeliefUCBScheduler else cls(n_bands, ucb_c=0.5)
        stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=1, switch_cost_steps=1)
        print(f"  {name:12s}: {stats.switches} switches out of {n_steps} steps "
              f"({100*stats.switches/n_steps:.1f}% of steps trigger a switch)")
    print()


def sparse_radar_sweep():
    n_bands = 36
    n_steps = 4000
    warmup = 800
    scenario = make_sparse_scenario(n_bands)
    print("--- Sparse fixed-PRI radar, per-emitter capture, k=1 ---")
    print("(\"PRIAware\" uses defaults -- warmup switches every step, so it's\n"
          " devastated by switch cost the same way RoundRobin is. \"PRIAware+dwell\"\n"
          " adds warmup_dwell_steps/jitter + switch_lead_steps -- see\n"
          " validate_warmup_dwell_fix.py for the 30-seed validation of this fix.)\n")
    header = (f"{'switch_cost':>11s} | {'BeliefUCB radar%':>17s} | {'PRIAware radar%':>16s} | "
              f"{'PRIAware comm1%':>16s} | {'+dwell radar%':>14s} | {'+dwell comm1%':>14s}")
    print(header)
    print("-" * len(header))

    def capture(sched_cls, cost, warmup=warmup, **kw):
        random.seed(11)
        sched = sched_cls(n_bands, ucb_c=0.5, warmup_steps=warmup, **kw)
        env = scenario()
        radar_pulses = radar_caught = 0
        comm1_on = comm1_caught = 0
        prev_bands = set()
        settling_remaining = {}
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for band in bands:
                blocked = False
                if cost > 0:
                    if band not in prev_bands:
                        settling_remaining[band] = cost
                    if settling_remaining.get(band, 0) > 0:
                        settling_remaining[band] -= 1
                        blocked = True
                if not blocked:
                    sched.update(band, status[band])
                if t > warmup:
                    if band == 5 and status[5] and not blocked:
                        radar_caught += 1
                    if band == 1 and status[1] and not blocked:
                        comm1_caught += 1
            prev_bands = set(bands)
            if t > warmup:
                if status[5]:
                    radar_pulses += 1
                if status[1]:
                    comm1_on += 1
        radar_pct = radar_caught / radar_pulses if radar_pulses else 0.0
        comm1_pct = comm1_caught / comm1_on if comm1_on else 0.0
        return radar_pct, comm1_pct

    for cost in SWITCH_COSTS:
        b_radar, _ = capture(BeliefUCBScheduler, cost)
        p_radar, p_comm1 = capture(PRIAwareScheduler, cost)
        if cost > 0:
            dwell, warmup_scaled = recommended_warmup_dwell(cost, warmup, margin=2)
            d_radar, d_comm1 = capture(PRIAwareScheduler, cost, warmup=warmup_scaled,
                                        warmup_dwell_steps=dwell, warmup_dwell_jitter=1,
                                        switch_lead_steps=cost)
            extra = f"{d_radar*100:13.1f}% | {d_comm1*100:13.1f}%"
        else:
            extra = f"{'n/a':>13s}  | {'n/a':>13s} "
        print(f"{cost:11d} | {b_radar*100:16.1f}% | {p_radar*100:15.1f}% | "
              f"{p_comm1*100:15.1f}% | {extra}")
    print("\n(NOTE: +dwell numbers are single-seed spot checks like everything else in\n"
          " this table -- see validate_warmup_dwell_fix.py for the real 30-seed picture,\n"
          " since this project has repeatedly found single-seed reads misleading.)\n")


if __name__ == "__main__":
    beacon_switches_breakdown()
    beacon_sweep()
    sparse_radar_sweep()
