"""
validate_offbyone_fix.py
===========================
Multi-seed, identical-environment confirmation of THIS session's fix
(testing each candidate period's +-1 integer neighbors in
_update_pri_model, added to scan_scheduler_v3_pri.py) on the beacon
scenario -- closing the one gap flagged after that fix: it was verified
on 20 PDW seeds and one beacon seed, but never run through the same
25-30 seed identical-environment harness every other fix in this
project got (validate_plateau_fix.py, settle_fix_interaction.py).

PreOffByOneFixPRIAware below is a reconstruction of PRIAwareScheduler
with ONLY the neighbor-expansion block removed -- everything else
(plateau fix, harmonic-selection-by-best-fit, confidence_scale) stays
exactly as shipped, so this isolates precisely the one change made this
session, the same way PlateauOnlyPRIAware isolated an earlier fix.

Uses the identical-environment methodology from settle_fix_interaction.py
(reset random.seed(seed) immediately before EACH scheduler's run, not
once per comparison) since that's what a clean isolated comparison on
the beacon scenario requires -- confirmed there that with warmup_steps=0
none of these schedulers consume their own randomness, so this gives
every scheduler the identical ground-truth trajectory for a given seed.

Run: python3 validate_offbyone_fix.py
     python3 validate_offbyone_fix.py --seeds 30
"""

import argparse
import math
import random
import statistics
from collections import Counter
from functools import reduce
from typing import Dict, List

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario


class PreOffByOneFixPRIAware(PRIAwareScheduler):
    """PRIAwareScheduler as it stood at the START of this session --
    candidate generation via gcd + pairwise mode + mode's small-integer
    divisors, WITHOUT also testing each candidate's +-1 neighbors."""

    def _update_pri_model(self, band):
        times = self.hit_times[band]
        if len(times) < 8:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return
        diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]

        max_run = 1
        run = 1
        sorted_times = sorted(times)
        for a, b in zip(sorted_times[:-1], sorted_times[1:]):
            run = run + 1 if b - a == 1 else 1
            max_run = max(max_run, run)
        self.max_run_ever[band] = max(self.max_run_ever[band], max_run)
        min_candidate = max(8, 2 * max_run)

        candidate_pool = [d for d in diffs if d >= min_candidate]
        if not candidate_pool:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return

        candidates = set()
        g = reduce(math.gcd, diffs)
        if g >= min_candidate:
            candidates.add(g)
        mode_candidate, _freq = Counter(candidate_pool).most_common(1)[0]
        candidates.add(mode_candidate)
        for k in (2, 3, 4, 5, 6, 7, 8):
            sub = round(mode_candidate / k)
            if sub >= min_candidate:
                candidates.add(sub)
        # NOTE: no +-1 neighbor expansion here -- this is the fix being isolated.

        best_base, best_rmse, best_rel = None, None, None
        for c in candidates:
            refined, rmse = self._refine_pri(sorted_times, c)
            if refined is None or rmse is None or refined < min_candidate * 0.5:
                continue
            rel = rmse / refined
            if best_rel is None or rel < best_rel:
                best_base, best_rmse, best_rel = refined, rmse, rel

        if best_base is None:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return
        refined_pri, rmse = best_base, best_rmse

        if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return

        confidence = min(1.0, max(0.0, 1.0 - rmse / (self.confidence_scale * refined_pri)))
        if confidence >= self.min_confidence:
            self.pri_estimate[band] = refined_pri
            self.jitter_estimate[band] = max(0.5, rmse, self.max_run_ever[band] / 2.0)
            self.confidence[band] = confidence
        else:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0


def run_identical_env(seed, sched_cls, n_bands=8, n_steps=4000, k=2, **kw):
    scenario = make_scenario(n_bands)
    random.seed(seed)
    sched = sched_cls(n_bands, ucb_c=0.5, **kw)
    stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
    return stats.report()["interception_ratio"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--seed-start", type=int, default=1)
    args = ap.parse_args()
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))

    print(f"Off-by-one-fix confirmation, beacon scenario, identical-environment "
          f"methodology, {len(seeds)} seeds ({seeds[0]}..{seeds[-1]}), k=1 and k=2.\n")

    for k in (1, 2):
        results: Dict[str, List[float]] = {
            "BeliefUCB": [],
            "PreOffByOneFix (session start)": [],
            "Current (with off-by-one fix)": [],
        }
        for seed in seeds:
            results["BeliefUCB"].append(run_identical_env(seed, BeliefUCBScheduler, k=k))
            results["PreOffByOneFix (session start)"].append(
                run_identical_env(seed, PreOffByOneFixPRIAware, k=k))
            results["Current (with off-by-one fix)"].append(
                run_identical_env(seed, PRIAwareScheduler, k=k))

        print(f"--- k={k} ---")
        print(f"{'Scheduler':32s} | {'mean':>7s} | {'stdev':>6s} | {'min':>6s} | {'max':>6s}")
        print("-" * 65)
        for name, vals in results.items():
            print(f"{name:32s} | {statistics.mean(vals)*100:6.1f}% | {statistics.stdev(vals)*100:5.1f}% | "
                  f"{min(vals)*100:5.1f}% | {max(vals)*100:5.1f}%")

        def delta(a, b):
            diffs = [x - y for x, y in zip(results[a], results[b])]
            wins = sum(1 for d in diffs if d > 0)
            return statistics.mean(diffs), statistics.stdev(diffs), wins, len(diffs)

        for label, a, b in [
            ("Current vs PreOffByOneFix (this session's fix, isolated)",
             "Current (with off-by-one fix)", "PreOffByOneFix (session start)"),
            ("Current vs BeliefUCB (net vs baseline)",
             "Current (with off-by-one fix)", "BeliefUCB"),
        ]:
            m, s, w, n = delta(a, b)
            print(f"  {label:58s}: {m*100:+5.1f}pp +/- {s*100:4.1f}pp  -- won {w}/{n}")
        print()


if __name__ == "__main__":
    main()
