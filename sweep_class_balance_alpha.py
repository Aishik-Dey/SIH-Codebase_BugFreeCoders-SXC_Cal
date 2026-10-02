"""
sweep_class_balance_alpha.py
=============================
Sweeps HedgeBlendedPRIAwareScheduler's class_balance_alpha (0.0 =
unweighted loss, 1.0 = full class-balanced loss) across all four
established references, single seed each -- same discipline as every
prior sweep in this project (confidence_scale, tune_confidence_threshold.py).

alpha=0.0 and alpha=1.0 are the two already-measured extremes:
  alpha=0.0 (unweighted):     real band-1 99.6%, PDW band-4 never locks
  alpha=1.0 (full balance):   real band-1 94.7%, PDW band-4 locks (conf=0.89)

The question this answers: is there a single alpha that keeps BOTH close
to their best, or is this a genuine Pareto frontier (matching the pattern
already found for confidence_scale/max_blend_confidence) where no single
value serves both regimes?

Run:  python3 sweep_class_balance_alpha.py
"""

import sys
import random

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
from scan_scheduler_prototype import make_scenario
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler
from pdw_source import PDWSource
from pdw_environment import PDWReplayEnvironment

def _h5_arg(default="config_169.h5"):
    """--h5 PATH / --h5=PATH override (so run_all.py can point this at the
    real dataset's actual location instead of a flattened bare filename)."""
    argv = sys.argv
    for i, tok in enumerate(argv):
        if tok == "--h5" and i + 1 < len(argv):
            return argv[i + 1]
        if tok.startswith("--h5="):
            return tok[len("--h5="):]
    return default


H5 = _h5_arg()

N_BANDS = 36
ALPHAS = [0.0, 0.25, 0.5, 0.7, 0.85, 1.0]


def sparse_radar(alpha):
    n_steps, warmup = 4000, 800
    scenario = make_sparse_scenario(N_BANDS)
    random.seed(11)
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=warmup,
                                           class_balance_alpha=alpha)
    env = scenario()
    radar_p = radar_c = comm1_on = comm1_c = 0
    for t in range(n_steps):
        status = env.step()
        bands = sched.choose_bands(1)
        for b in bands:
            sched.update(b, status[b])
        if t > warmup:
            if status[5]:
                radar_p += 1
                if 5 in bands:
                    radar_c += 1
            if status[1]:
                comm1_on += 1
                if 1 in bands:
                    comm1_c += 1
    return 100 * radar_c / radar_p, 100 * comm1_c / comm1_on


def beacon(alpha, k):
    n_steps = 4000
    scenario = make_scenario(N_BANDS)
    random.seed(7)
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, class_balance_alpha=alpha)
    stats = run_episode(scenario, sched, n_steps, N_BANDS, k_channels=k)
    return stats.report()["interception_ratio"] * 100


def pdw_band4(alpha):
    dwell_us, warmup = 20.0, 800
    source = PDWSource(h5_path=None, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(1)
    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=dwell_us,
                                     freq_range_mhz=source.freq_range_mhz, t0_us=source.t0_us)
    probe = env_factory()
    n_steps = probe.n_steps
    random.seed(1)
    env = env_factory()
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=warmup,
                                           class_balance_alpha=alpha)
    for t in range(n_steps):
        status = env.step()
        bands = sched.choose_bands(1)
        for b in bands:
            sched.update(b, status[b])
    return sched.confidence[4], sched.pri_estimate[4]


def real_band1(alpha):
    dwell_us = 20.0
    source = PDWSource(h5_path=H5, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(0)
    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=dwell_us,
                                     freq_range_mhz=source.freq_range_mhz, t0_us=source.t0_us)
    probe = env_factory()
    n_steps = probe.n_steps
    random.seed(1)
    env = env_factory()
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=0,
                                           class_balance_alpha=alpha)
    band1_hits = band1_on = 0
    for t in range(n_steps):
        status = env.step()
        bands = sched.choose_bands(1)
        for b in bands:
            sched.update(b, status[b])
        if status[1]:
            band1_on += 1
            if 1 in bands:
                band1_hits += 1
    return 100 * band1_hits / band1_on


if __name__ == "__main__":
    print(f"{'alpha':>6} | {'radar%':>7} {'comm1%':>7} | {'beac.k1%':>8} {'beac.k2%':>8} "
          f"| {'band4 conf':>10} {'band4 PRI':>10} | {'realband1%':>10}")
    print("-" * 88)
    for a in ALPHAS:
        r, c = sparse_radar(a)
        b1 = beacon(a, 1)
        b2 = beacon(a, 2)
        conf4, pri4 = pdw_band4(a)
        rb1 = real_band1(a)
        pri4_str = f"{pri4:.2f}" if pri4 else "None"
        print(f"{a:>6.2f} | {r:>7.1f} {c:>7.1f} | {b1:>8.1f} {b2:>8.1f} "
              f"| {conf4:>10.2f} {pri4_str:>10} | {rb1:>10.1f}")
