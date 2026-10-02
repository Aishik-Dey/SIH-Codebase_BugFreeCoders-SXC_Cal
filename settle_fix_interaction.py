"""
settle_fix_interaction.py
============================
The project's established seeding convention (one random.seed(seed) call,
then every scheduler in a comparison run back to back off that one
continuously-advancing stream) is what validate_plateau_fix.py used, and
it reproduced the documented numbers exactly. But run_episode()
constructs a FRESH environment every call, and MarkovEmitter/AgileEmitter
draw from `random` on every single step -- so schedulers running 4th and
5th in that shared sequence (PlateauOnly, Current) are actually facing
DIFFERENT underlying environment realizations, not the same one. The
aggregate statistics across many seeds are still valid (any position bias
should wash out over 30 independent trials), but a single-seed deep dive
into "why does Current do worse than PlateauOnly on seed 7" is
confounded: their scan decisions differ, but so does the ground-truth
comm/agile activity they're each reacting to.

This script fixes that for the beacon scenario specifically: with
warmup_steps=0 (the beacon suite's setting), NONE of BeliefUCB /
Original / PlateauOnly / Current consume any of their own randomness
(random.shuffle only fires inside the warmup branch, which never
triggers). So resetting random.seed(seed) immediately before EACH
scheduler's run_episode() call gives every scheduler the IDENTICAL
environment trajectory for that seed -- isolating the algorithmic
difference cleanly, at the cost of no longer matching the original
suite_c_beacon numbers exactly (this is a different, stricter pairing,
not a reproduction of the original headline numbers).

Run: python3 settle_fix_interaction.py
     python3 settle_fix_interaction.py --seeds 30
"""

import argparse
import random
import statistics
from typing import Dict, List

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario
from validate_plateau_fix import OriginalPRIAware, PlateauOnlyPRIAware


def run_identical_env(seed, sched_cls, n_bands=8, n_steps=4000, k=2, **kw):
    """Reset the seed immediately before constructing+running this one
    scheduler, so its environment trajectory is reproducible independent
    of what ran before it -- the key difference from the project's usual
    sequential-shared-stream convention."""
    scenario = make_scenario(n_bands)
    random.seed(seed)
    sched = sched_cls(n_bands, ucb_c=0.5, **kw)
    stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
    return stats.report()["interception_ratio"], sched


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--seed-start", type=int, default=1)
    ap.add_argument("--k", type=int, default=2)
    args = ap.parse_args()
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    k = args.k

    print(f"Paired-identical-environment comparison, beacon scenario, k={k}, "
          f"{len(seeds)} seeds ({seeds[0]}..{seeds[-1]}).\n"
          f"Every scheduler below sees the EXACT SAME ground-truth environment "
          f"trajectory for a given seed (verified: none of these schedulers "
          f"consume their own randomness with warmup_steps=0).\n")

    results: Dict[str, List[float]] = {
        "BeliefUCB (Markov-only)": [],
        "Original (pre-both-fixes)": [],
        "PlateauOnly (fix 1 only)": [],
        "Current (both fixes)": [],
    }
    schedulers_by_seed = {}  # seed -> {name: scheduler instance}, for later inspection

    for seed in seeds:
        by_name = {}
        for name, cls in [
            ("BeliefUCB (Markov-only)", BeliefUCBScheduler),
            ("Original (pre-both-fixes)", OriginalPRIAware),
            ("PlateauOnly (fix 1 only)", PlateauOnlyPRIAware),
            ("Current (both fixes)", PRIAwareScheduler),
        ]:
            ratio, sched = run_identical_env(seed, cls, k=k)
            results[name].append(ratio)
            by_name[name] = sched
        schedulers_by_seed[seed] = by_name

    print(f"{'Scheduler':30s} | {'mean':>7s} | {'stdev':>6s} | {'min':>6s} | {'max':>6s}")
    print("-" * 65)
    for name, vals in results.items():
        print(f"{name:30s} | {statistics.mean(vals)*100:6.1f}% | {statistics.stdev(vals)*100:5.1f}% | "
              f"{min(vals)*100:5.1f}% | {max(vals)*100:5.1f}%")

    def delta(a, b):
        diffs = [x - y for x, y in zip(results[a], results[b])]
        wins = sum(1 for d in diffs if d > 0)
        return statistics.mean(diffs), statistics.stdev(diffs), wins, len(diffs)

    print()
    for label, a, b in [
        ("PlateauOnly vs Original (fix 1's contribution, IDENTICAL envs)", "PlateauOnly (fix 1 only)", "Original (pre-both-fixes)"),
        ("Current vs PlateauOnly (fix 2's ADDED effect, IDENTICAL envs)", "Current (both fixes)", "PlateauOnly (fix 1 only)"),
        ("Current vs Original (both fixes combined, IDENTICAL envs)", "Current (both fixes)", "Original (pre-both-fixes)"),
        ("Current vs BeliefUCB (net vs baseline, IDENTICAL envs)", "Current (both fixes)", "BeliefUCB (Markov-only)"),
    ]:
        m, s, w, n = delta(a, b)
        print(f"  {label:56s}: {m*100:+5.1f}pp +/- {s*100:4.1f}pp  -- won {w}/{n}")

    # Find the single seed where Current vs PlateauOnly diverges most, and
    # show exactly what differs in their final per-band model state --
    # THIS time on an environment we know is identical between them.
    diffs_cp = [(c - p, seed) for c, p, seed in
                zip(results["Current (both fixes)"], results["PlateauOnly (fix 1 only)"], seeds)]
    diffs_cp.sort()
    worst_diff, worst_seed = diffs_cp[0]
    print(f"\nWorst Current-vs-PlateauOnly seed under IDENTICAL environments: "
          f"seed {worst_seed} ({worst_diff*100:+.1f}pp)")
    plateau_sched = schedulers_by_seed[worst_seed]["PlateauOnly (fix 1 only)"]
    current_sched = schedulers_by_seed[worst_seed]["Current (both fixes)"]
    for b in (2, 5, 6):
        print(f"  band {b}: PlateauOnly pri={plateau_sched.pri_estimate[b]} "
              f"conf={plateau_sched.confidence[b]:.2f} jitter={plateau_sched.jitter_estimate[b]:.2f} | "
              f"Current pri={current_sched.pri_estimate[b]} "
              f"conf={current_sched.confidence[b]:.2f} jitter={current_sched.jitter_estimate[b]:.2f}")


if __name__ == "__main__":
    main()
