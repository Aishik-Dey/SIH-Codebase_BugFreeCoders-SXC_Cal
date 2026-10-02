"""
oracle_ceiling.py
====================
Answers a concrete question raised about the RL item on the open list:
"only worth it once heuristics plateau -- how do we know they have?"
This is the empirical half of that answer (the other half -- held-out
generalization on the 5 untouched real .h5 files -- needs a file this
session doesn't have).

GENIE ORACLE: a scheduler that sees the TRUE on/off status of every
band before choosing (no belief, no learning, no periodicity model --
just greedy top-k selection of whichever bands are actually
transmitting this exact step). This is a real, non-trivial upper bound
on interception_ratio, NOT "100%" -- it is still capped by the
environment's own structure: whenever more than k bands transmit
simultaneously, even the genie can only catch k of them. The gap
between a real scheduler and this ceiling isolates POLICY imperfection
from the environment's own inherent information limit. If that gap is
already small, no amount of further heuristic tuning (or RL) can close
much more of it -- the ceiling itself is the wall, not the algorithm.

Run:  python3 oracle_ceiling.py
"""

import random
import sys

from scan_scheduler_v2 import BeliefUCBScheduler
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler
from scan_scheduler_whittle import WhittleIndexScheduler
from scan_scheduler_prototype import make_scenario
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


def run_oracle(env_factory, n_steps, k=1):
    env = env_factory()
    hits = on = 0
    for t in range(n_steps):
        status = env.step()
        on_bands = [b for b in range(N_BANDS) if status[b]]
        on += len(on_bands)
        hits += min(len(on_bands), k)  # genie catches up to k of them, always the right k
    return hits, on


def run_real_scheduler(cls, env_factory, n_steps, k=1, **kw):
    env = env_factory()
    sched = cls(N_BANDS, ucb_c=0.5, **kw)
    hits = on = 0
    for t in range(n_steps):
        status = env.step()
        bands = sched.choose_bands(k)
        for b in bands:
            sched.update(b, status[b])
            if status[b]:
                hits += 1
        on += sum(1 for b in range(N_BANDS) if status[b])
    return hits, on


def pct(a, b):
    return 100.0 * a / b if b else 0.0


if __name__ == "__main__":
    print("=== Sparse-radar headline (synthetic, seed=11, k=1, warmup=800) ===")
    n_steps, warmup = 4000, 800
    scenario = make_sparse_scenario(N_BANDS)

    random.seed(11)
    oh, oo = run_oracle(scenario, n_steps, k=1)
    print(f"  GENIE ORACLE (ceiling): {pct(oh, oo):.1f}%")
    for name, cls in [("BeliefUCB", BeliefUCBScheduler), ("PRIAware", PRIAwareScheduler),
                      ("HedgeBlended", HedgeBlendedPRIAwareScheduler), ("WhittleIndex", WhittleIndexScheduler)]:
        random.seed(11)
        h, o = run_real_scheduler(cls, scenario, n_steps, k=1, warmup_steps=warmup)
        print(f"  {name:15s}: {pct(h, o):5.1f}%   (gap to ceiling: {pct(oh,oo)-pct(h,o):.1f}pp)")

    for k in (1, 2):
        print(f"\n=== Beacon scenario (synthetic, seed=7), k={k} ===")
        scenario2 = make_scenario(N_BANDS)
        random.seed(7)
        oh, oo = run_oracle(scenario2, n_steps, k=k)
        print(f"  GENIE ORACLE (ceiling): {pct(oh, oo):.1f}%")
        for name, cls in [("BeliefUCB", BeliefUCBScheduler), ("PRIAware", PRIAwareScheduler),
                          ("HedgeBlended", HedgeBlendedPRIAwareScheduler), ("WhittleIndex", WhittleIndexScheduler)]:
            random.seed(7)
            h, o = run_real_scheduler(cls, scenario2, n_steps, k=k)
            print(f"  {name:15s}: {pct(h, o):5.1f}%   (gap to ceiling: {pct(oh,oo)-pct(h,o):.1f}pp)")

    print("\n=== Real config_169.h5, k=1, warmup=0 ===")
    source = PDWSource(h5_path=H5, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(0)
    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=20.0,
                                     freq_range_mhz=source.freq_range_mhz, t0_us=source.t0_us)
    oh, oo = run_oracle(env_factory, env_factory().n_steps, k=1)
    print(f"  GENIE ORACLE (ceiling): {pct(oh, oo):.1f}%")
    for name, cls in [("BeliefUCB", BeliefUCBScheduler), ("PRIAware", PRIAwareScheduler),
                      ("HedgeBlended", HedgeBlendedPRIAwareScheduler)]:
        # WhittleIndex skipped here -- confirmed ~199s/run earlier, too
        # slow to include in this multi-scheduler pass; its real-file
        # number (93.7%) is already on record from a prior session.
        random.seed(1)
        h, o = run_real_scheduler(cls, env_factory, env_factory().n_steps, k=1, warmup_steps=0)
        print(f"  {name:15s}: {pct(h, o):5.1f}%   (gap to ceiling: {pct(oh,oo)-pct(h,o):.1f}pp)")
