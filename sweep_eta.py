"""
sweep_eta.py
=============
Sweeps HedgeBlendedPRIAwareScheduler's eta (Hedge multiplicative-weights
learning rate, default 4.0 -- never swept until now) against all four
established references. This is the one scoped item from the original
v5 build that was left untouched through every fix/rebase/alpha-sweep
since (class_balance_alpha, the confidence gate, the v4 rebase).

Only HedgeBlended has eta, so BeliefUCB/PRIAware/PersistentPRIAware are
NOT re-run per eta value -- their numbers are already established:
  sparse-radar (post-v4-rebase, 30 seeds): BeliefUCB 0.2%/86.9%,
      PRIAware 50.0%+/-50.9% (bimodal), shown here as context only.
  beacon k=1/k=2 (single-seed=7): PRIAware 27.5%/53.4%,
      PersistentPRIAware 25.0%/45.5% (v4's own known cost, NOT eta-
      dependent, included only as the floor HedgeBlended should stay
      at or above).
  PDW band-4 fractional-PRI: PRIAware locks conf~0.79-0.90.
  real config_169.h5 band-1: BeliefUCB 99.7%, PRIAware 69.7%.

Sparse-radar and PDW band-4 are lightly multi-seeded here (5 seeds
each) rather than single-seed, since eta plausibly affects HOW FAST
the char_bonus-driven characterization and the Hedge weights converge
-- exactly the kind of thing a single seed could hide, per the alpha
sweep's own lesson.

Run:  python3 sweep_eta.py
"""

import sys
import random
import statistics

from scan_scheduler_v2 import run_episode
from scan_scheduler_v3_pri import make_sparse_scenario
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
ETAS = [1.0, 2.0, 4.0, 6.0, 8.0, 12.0]
N_SEEDS_SPARSE = 5
N_SEEDS_PDW = 5


def sparse_radar(eta, seed):
    n_steps, warmup = 4000, 800
    scenario = make_sparse_scenario(N_BANDS)
    random.seed(seed)
    env = scenario()
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=warmup, eta=eta)
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
    return (100 * radar_c / radar_p if radar_p else 0.0,
            100 * comm1_c / comm1_on if comm1_on else 0.0)


def beacon(eta, k):
    n_steps = 4000
    scenario = make_scenario(N_BANDS)
    random.seed(7)
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, eta=eta)
    stats = run_episode(scenario, sched, n_steps, N_BANDS, k_channels=k)
    return stats.report()["interception_ratio"] * 100


def pdw_band4(eta, seed):
    dwell_us, warmup = 20.0, 800
    source = PDWSource(h5_path=None, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(seed)
    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=dwell_us,
                                     freq_range_mhz=source.freq_range_mhz, t0_us=source.t0_us)
    probe = env_factory()
    n_steps = probe.n_steps
    random.seed(seed)
    env = env_factory()
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=warmup, eta=eta)
    for t in range(n_steps):
        status = env.step()
        bands = sched.choose_bands(1)
        for b in bands:
            sched.update(b, status[b])
    return sched.confidence[4]


def real_band1(eta):
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
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=0, eta=eta)
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
    print(f"{'eta':>5} | {'radar% (5s)':>14} {'comm1% (5s)':>14} | "
          f"{'beac.k1%':>8} {'beac.k2%':>8} | {'band4 lock rate':>16} "
          f"{'band4 mean conf':>16} | {'realband1%':>10}")
    print("-" * 118)
    for eta in ETAS:
        radar_vals, comm1_vals = [], []
        for s in range(1, N_SEEDS_SPARSE + 1):
            r, c = sparse_radar(eta, s)
            radar_vals.append(r)
            comm1_vals.append(c)
        b1 = beacon(eta, 1)
        b2 = beacon(eta, 2)
        confs = [pdw_band4(eta, s) for s in range(1, N_SEEDS_PDW + 1)]
        locked = [c for c in confs if c > 0]
        lock_rate = f"{len(locked)}/{N_SEEDS_PDW}"
        mean_conf = f"{statistics.mean(locked):.2f}" if locked else "n/a"
        rb1 = real_band1(eta)
        print(f"{eta:>5.1f} | {statistics.mean(radar_vals):>7.1f}+/-{statistics.stdev(radar_vals):>5.1f} "
              f"{statistics.mean(comm1_vals):>7.1f}+/-{statistics.stdev(comm1_vals):>5.1f} | "
              f"{b1:>8.1f} {b2:>8.1f} | {lock_rate:>16} {mean_conf:>16} | {rb1:>10.1f}")
