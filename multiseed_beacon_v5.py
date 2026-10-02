"""
multiseed_beacon_v5.py
========================
Full 30-seed beacon validation for HedgeBlendedPRIAwareScheduler (v5),
closing the one item flagged after the sparse-radar coin-flip scare:
beacon had only ever been checked single-seed (seed=7) throughout the
entire v5 build, even after that scare proved how much a single seed
can hide.

Reuses beacon_seed() from multiseed_alpha_default.py (already correctly
resets random.seed(seed) immediately before each scheduler's own run,
avoiding the shared-random-stream confound this project has hit and
fixed at least 3 times before).

Reports mean +/- stdev (matching project convention) AND paired
win-counts against both PRIAware (v3) and PersistentPRIAware (v4)
specifically -- v4 is the more relevant baseline since v5 is now built
on top of it and the single-seed check showed v5 matching/beating v4,
not v3, which is the correct comparison to scale up.

Run:  python3 multiseed_beacon_v5.py
"""

import statistics
from multiseed_alpha_default import beacon_seed as _beacon_seed_base, N_BANDS
from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler
from scan_scheduler_prototype import make_scenario
import random

N_SEEDS = 30

# Local scheduler list -- multiseed_alpha_default.SCHEDULERS omits v4,
# which is needed here for the v5-vs-v4 comparison (the more relevant
# baseline, since v5 is built on top of it).
SCHEDULERS = [
    ("BeliefUCB", BeliefUCBScheduler, {}),
    ("PRIAware (v3)", PRIAwareScheduler, {}),
    ("PersistentPRIAware (v4)", PersistentPRIAwareScheduler, {}),
    ("HedgeBlended (v5, alpha=0.1)", HedgeBlendedPRIAwareScheduler, {}),
]


def beacon_seed(seed, k):
    n_steps = 4000
    scenario = make_scenario(N_BANDS)
    out = {}
    for name, cls, kw in SCHEDULERS:
        random.seed(seed)
        sched = cls(N_BANDS, ucb_c=0.5, **kw)
        stats = run_episode(scenario, sched, n_steps, N_BANDS, k_channels=k)
        out[name] = stats.report()["interception_ratio"] * 100
    return out


def run(k):
    per_seed = {name: [] for name, _, _ in SCHEDULERS}
    for s in range(1, N_SEEDS + 1):
        r = beacon_seed(s, k)
        for name in per_seed:
            per_seed[name].append(r[name])
    return per_seed


def summarize(vals):
    return f"{statistics.mean(vals):5.1f} +/- {statistics.stdev(vals):4.1f}"


def win_count(a_vals, b_vals):
    """How many seeds a beats (or ties) b, out of len(a_vals)."""
    wins = sum(1 for a, b in zip(a_vals, b_vals) if a >= b)
    return f"{wins}/{len(a_vals)}"


if __name__ == "__main__":
    names = [name for name, _, _ in SCHEDULERS]
    v3_name = "PRIAware (v3)"
    v4_name = "PersistentPRIAware (v4)"
    v5_name = "HedgeBlended (v5, alpha=0.1)"

    for k in (1, 2):
        print(f"=== Beacon scenario, k={k}, {N_SEEDS} seeds ===")
        per_seed = run(k)
        for name in names:
            print(f"  {name:30s}: {summarize(per_seed[name])}")
        print(f"  v5 vs v3 win-count (v5 >= v3 per seed): "
              f"{win_count(per_seed[v5_name], per_seed[v3_name])}")
        print(f"  v5 vs v4 win-count (v5 >= v4 per seed): "
              f"{win_count(per_seed[v5_name], per_seed[v4_name])}")
        print(f"  v4 vs v3 win-count (v4 >= v3 per seed), for context on "
              f"the pre-existing v4 trade-off: "
              f"{win_count(per_seed[v4_name], per_seed[v3_name])}")
        print()
