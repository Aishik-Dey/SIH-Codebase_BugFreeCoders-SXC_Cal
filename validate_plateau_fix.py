"""
validate_plateau_fix.py
==========================
Multi-seed validation of the burst-plateau jitter fix to
PRIAwareScheduler (diagnosed in diagnose_beacon_regression.py), run
through the same rigor as multi_seed_robustness.py's suite C rather
than the informal single-script spot-check this fix originally got.

Two fixes landed in scan_scheduler_v3_pri.py in the same session, back
to back:
  1. The burst-plateau jitter fix (widen the phase-bump width using a
     persistent `max_run_ever` estimate, so a multi-step burst isn't
     modeled as an instantaneous point event).
  2. A harmonic-lock-on fix (pick the PRI candidate by best refined fit
     across ALL candidates, not the coarse tolerance-test winner).

Because both touch _update_pri_model, a "before vs after" comparison
using only the ORIGINAL and CURRENT classes conflates their two
effects. This script reconstructs an intermediate PLATEAU-ONLY variant
(fix 1 applied, fix 2 not yet applied) as literal frozen copies of
_update_pri_model at each stage, so fix 1's contribution can be
isolated:

    BeliefUCB (Markov-only)      -- no periodicity model at all
    Original   (pre-both-fixes)  -- shipped in the uploaded zip
    PlateauOnly (fix 1 only)     -- reconstructed, not shipped anywhere
    Current    (both fixes)      -- scan_scheduler_v3_pri.PRIAwareScheduler

All four run on the SAME beacon scenario, SAME seeds, using the
project's established seeding convention (one random.seed(seed) call
per full comparison block, schedulers constructed and run back to back
off that one continuously-advancing stream) so results are directly
comparable to the original suite C numbers already reported:

    (pre-fix, from the uploaded zip's multi_seed_robustness.py run)
    k=1: PRIAware +1.5pp vs BeliefUCB, won 8/10 seeds
    k=2: PRIAware -1.5pp vs BeliefUCB, won 1/10 seeds

Run: python3 validate_plateau_fix.py
     python3 validate_plateau_fix.py --seeds 30
"""

import argparse
import math
import random
import statistics
from collections import Counter
from functools import reduce
from typing import Dict, List

from scan_scheduler_v2 import RoundRobinScheduler, BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario


# ----------------------------------------------------------------------
# Reconstructed intermediate scheduler states, for isolating fix 1
# ----------------------------------------------------------------------

class OriginalPRIAware(PRIAwareScheduler):
    """Exact reconstruction of _update_pri_model as shipped in the
    uploaded zip -- old single-seed 'excess over chance' candidate
    selection, AND the narrow rmse-only jitter floor (no burst-plateau
    widening). This is the "before" for both fixes."""

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
        min_candidate = max(8, 2 * max_run)

        candidate_pool = [d for d in diffs if d >= min_candidate]
        if not candidate_pool:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return
        tol = 1

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

        def _excess_over_chance(c):
            score = self._score_candidate(diffs, c, tol)
            chance = min(1.0, (2 * tol + 1) / c)
            return score - chance

        seed = max(candidates, key=_excess_over_chance)
        refined_pri, rmse = self._refine_pri(sorted_times, seed)

        if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return

        confidence = min(1.0, max(0.0, 1.0 - rmse / (0.25 * refined_pri)))
        if confidence >= self.min_confidence:
            self.pri_estimate[band] = refined_pri
            self.jitter_estimate[band] = max(0.5, rmse)   # OLD: no plateau widening
            self.confidence[band] = confidence
        else:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0


class PlateauOnlyPRIAware(PRIAwareScheduler):
    """Fix 1 (burst-plateau jitter widening) applied, fix 2 (harmonic-
    lock-on candidate selection) NOT applied -- still uses the old
    single-seed 'excess over chance' selection. Isolates fix 1's own
    contribution to the beacon-scenario result."""

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
        self.max_run_ever[band] = max(self.max_run_ever[band], max_run)   # NEW: persistent tracking
        min_candidate = max(8, 2 * max_run)

        candidate_pool = [d for d in diffs if d >= min_candidate]
        if not candidate_pool:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return
        tol = 1

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

        def _excess_over_chance(c):   # OLD selection, unchanged from Original
            score = self._score_candidate(diffs, c, tol)
            chance = min(1.0, (2 * tol + 1) / c)
            return score - chance

        seed = max(candidates, key=_excess_over_chance)
        refined_pri, rmse = self._refine_pri(sorted_times, seed)

        if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return

        confidence = min(1.0, max(0.0, 1.0 - rmse / (0.25 * refined_pri)))
        if confidence >= self.min_confidence:
            self.pri_estimate[band] = refined_pri
            # NEW: plateau-widened jitter floor -- the ONLY change vs Original
            self.jitter_estimate[band] = max(0.5, rmse, self.max_run_ever[band] / 2.0)
            self.confidence[band] = confidence
        else:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0


# ----------------------------------------------------------------------
# Harness helpers (matching multi_seed_robustness.py's conventions)
# ----------------------------------------------------------------------

def summarize(values: List[float]) -> Dict:
    n = len(values)
    return {
        "n": n,
        "mean": statistics.mean(values),
        "stdev": statistics.stdev(values) if n > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def print_summary_table(title: str, summaries: Dict[str, Dict], unit: str = "%", scale: float = 100.0):
    print(f"\n{title}")
    header = f"{'Scheduler':42s} | {'mean +/- stdev':>18s} | {'min':>8s} | {'max':>8s}"
    print(header)
    print("-" * len(header))
    for name, s in summaries.items():
        mean_s = f"{s['mean']*scale:5.1f}{unit}"
        stdev_s = f"{s['stdev']*scale:4.1f}{unit}"
        print(f"{name:42s} | {mean_s:>8s} +/- {stdev_s:<7s} | "
              f"{s['min']*scale:6.1f}{unit} | {s['max']*scale:6.1f}{unit}")


def paired_delta(a_vals: List[float], b_vals: List[float]) -> Dict:
    diffs = [a - b for a, b in zip(a_vals, b_vals)]
    wins = sum(1 for d in diffs if d > 0)
    s = summarize(diffs)
    s["wins"] = wins
    s["n_seeds"] = len(diffs)
    return s


def print_delta(label: str, delta: Dict, scale: float = 100.0):
    print(f"  {label:42s}: {delta['mean']*scale:+5.1f}pp +/- {delta['stdev']*scale:4.1f}pp "
          f"  (min {delta['min']*scale:+5.1f}pp, max {delta['max']*scale:+5.1f}pp)  "
          f"-- won in {delta['wins']}/{delta['n_seeds']} seeds")


# ----------------------------------------------------------------------
# Suite: beacon scenario, 4-way comparison, matching suite_c_beacon's
# exact seeding convention (one seed per full comparison block, all
# schedulers run back to back off that one stream).
# ----------------------------------------------------------------------

def suite_plateau_validation(seeds: List[int], n_bands: int = 8, n_steps: int = 4000,
                              csv_path: str = None):
    scenario = make_scenario(n_bands)
    all_raw = {}
    for k in (1, 2):
        builders = {
            "RoundRobin (open-loop)": lambda: RoundRobinScheduler(n_bands),
            "BeliefUCB (Markov-only)": lambda: BeliefUCBScheduler(n_bands, ucb_c=0.5),
            "Original (pre-both-fixes)": lambda: OriginalPRIAware(n_bands, ucb_c=0.5),
            "PlateauOnly (fix 1 only)": lambda: PlateauOnlyPRIAware(n_bands, ucb_c=0.5),
            "Current (both fixes)": lambda: PRIAwareScheduler(n_bands, ucb_c=0.5),
        }
        raw: Dict[str, List[float]] = {name: [] for name in builders}
        for seed in seeds:
            random.seed(seed)
            for name, build in builders.items():
                stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=k)
                raw[name].append(stats.report()["interception_ratio"])

        print_summary_table(
            f"[Plateau validation] Beacon scenario, k_channels={k}, {len(seeds)} seeds "
            f"({n_steps} steps each)", {n: summarize(v) for n, v in raw.items()})

        print_delta("Original vs BeliefUCB (baseline, pre-fix)",
                    paired_delta(raw["Original (pre-both-fixes)"], raw["BeliefUCB (Markov-only)"]))
        print_delta("PlateauOnly vs BeliefUCB (fix 1 alone)",
                    paired_delta(raw["PlateauOnly (fix 1 only)"], raw["BeliefUCB (Markov-only)"]))
        print_delta("PlateauOnly vs Original (fix 1's OWN contribution)",
                    paired_delta(raw["PlateauOnly (fix 1 only)"], raw["Original (pre-both-fixes)"]))
        print_delta("Current vs BeliefUCB (both fixes, shipped state)",
                    paired_delta(raw["Current (both fixes)"], raw["BeliefUCB (Markov-only)"]))
        all_raw[k] = raw

        if csv_path:
            write_csv(csv_path, f"plateau_validation_k{k}", raw, seeds)
    return all_raw


def write_csv(path: str, suite_label: str, raw: Dict[str, List[float]], seeds: List[int]):
    import csv
    import os
    write_header = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["suite", "scheduler", "seed", "interception_ratio"])
        for name, vals in raw.items():
            for seed, v in zip(seeds, vals):
                w.writerow([suite_label, name, seed, v])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=20, help="Number of seeds to test")
    ap.add_argument("--seed-start", type=int, default=1, help="First seed value")
    ap.add_argument("--csv", default="plateau_validation_results.csv",
                     help="Path to append raw per-seed results to (set to '' to skip)")
    args = ap.parse_args()

    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    print(f"Validating the burst-plateau jitter fix in isolation from the later "
          f"harmonic-selection fix, across {len(seeds)} seeds ({seeds[0]}..{seeds[-1]}).\n")
    suite_plateau_validation(seeds, csv_path=args.csv or None)


if __name__ == "__main__":
    main()
