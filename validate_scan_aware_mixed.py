"""
validate_scan_aware_mixed.py
==============================
The isolated single-emitter test in scan_aware_scheduler.py's __main__
under-tests the design: with nothing else to scan, even a single-
periodicity model does fine by just camping on the scanning radar's
band. The real case for separating scan_period from PRI is opportunity
cost -- during the radar's long out-of-beam dead window, a scheduler
that doesn't know precisely when the beam returns either wastes scans
re-checking a silent band, or gives up on it too coarsely and misses
the next burst. Either way that's scan time stolen from OTHER emitters
competing for the same k=1 receiver.

Scenario: 8 bands, k=1 (forced trade-off, can't cover two bands at
once).
  band 1: MarkovEmitter comm (bursty, easy, "cheap" hits)
  band 4: MarkovEmitter comm (bursty, easy, "cheap" hits)
  band 5: spatially-scanning fixed-PRI radar (scan_period=40,
          beam_dwell=6, inner PRI=3, 2% sidelobe leak) -- the rare,
          disciplined target these schedulers are actually meant to
          prioritize
  bands 0,3,6,7: AgileEmitter (frequency-agile, no exploitable
          periodicity -- background noise/distractor load)

`priority` weights band 5 above the comms bands (same mechanism
BeliefUCBScheduler already supports), so raw hit-count alone can't
substitute for actually predicting the radar -- the question is how
much scan time each scheduler wastes/spends around band 5's dead time
while still covering it.

Run: python3 validate_scan_aware_mixed.py
"""

import random
import statistics

from scan_scheduler_prototype import Environment, MarkovEmitter, AgileEmitter
from scan_scheduler_v2 import run_episode, RoundRobinScheduler, BeliefUCBScheduler
from scan_scheduler_v3_pri import PRIAwareScheduler, SparsePeriodicEmitter
from scan_aware_scheduler import ScanAwarePRIScheduler
from spatial_scan_emitter import SpatiallyScanningEmitter

N_BANDS = 36
N_STEPS = 8000
RADAR_BAND = 5


def scenario():
    inner = SparsePeriodicEmitter("fixed-pri-radar", band=RADAR_BAND, pri=3)
    scanning_radar = SpatiallyScanningEmitter(
        inner, scan_period_steps=40, beam_dwell_steps=6, sidelobe_leak_prob=0.02)
    emitters = [
        MarkovEmitter("comm-1", band=1, p_on_given_off=0.08, p_on_given_on=0.85),
        MarkovEmitter("comm-2", band=4, p_on_given_off=0.10, p_on_given_on=0.75),
        scanning_radar,
        AgileEmitter("agile-1", bands=[0, 3], dwell=2, duty=0.4),
        AgileEmitter("agile-2", bands=[6, 7], dwell=3, duty=0.4),
    ]
    return Environment(n_bands=N_BANDS, emitters=emitters)


def radar_band_stats(sched_cls, kwargs, seed):
    """Runs one episode with a hook that separately tracks hits/misses
    on the radar's band specifically, not just overall interception."""
    random.seed(seed)
    env = scenario()
    sched = sched_cls(N_BANDS, **kwargs)
    radar_hits = 0
    radar_transmissions = 0

    for t in range(N_STEPS):
        status = env.step()
        if status[RADAR_BAND]:
            radar_transmissions += 1
        bands = sched.choose_bands(1)
        for band in bands:
            observed_on = status[band]
            sched.update(band, observed_on)
            if band == RADAR_BAND and observed_on:
                radar_hits += 1

    return radar_hits, radar_transmissions


def main():
    priority = [1.0] * N_BANDS
    priority[RADAR_BAND] = 4.0  # rare/disciplined target outranks loud comms

    builders = {
        "RoundRobin (open-loop baseline)": (RoundRobinScheduler, {}),
        "BeliefUCB (no periodicity model)": (BeliefUCBScheduler, dict(ucb_c=0.5, priority=priority)),
        "PRIAware (single-periodicity)": (PRIAwareScheduler, dict(ucb_c=0.5, priority=priority)),
        "ScanAwarePRIScheduler (two-tier)": (ScanAwarePRIScheduler, dict(ucb_c=0.5, priority=priority)),
    }

    seeds = list(range(10))
    print(f"Mixed competitive scenario, {N_STEPS} steps, k=1, {len(seeds)} seeds, "
          f"radar priority weight={priority[RADAR_BAND]}\n")

    header = f"{'Scheduler':36s} | {'Overall %':>10s} | {'Radar-band %':>13s}"
    print(header)
    print("-" * len(header))

    for name, (cls, kw) in builders.items():
        overall_ratios, radar_ratios = [], []
        for seed in seeds:
            random.seed(seed)
            stats = run_episode(scenario, cls(N_BANDS, **kw), N_STEPS, N_BANDS, k_channels=1)
            overall_ratios.append(stats.report()["interception_ratio"])
            rh, rt = radar_band_stats(cls, kw, seed)
            radar_ratios.append(rh / max(1, rt))
        print(f"{name:36s} | {statistics.mean(overall_ratios)*100:8.1f}%  | "
              f"{statistics.mean(radar_ratios)*100:11.1f}%")


if __name__ == "__main__":
    main()
