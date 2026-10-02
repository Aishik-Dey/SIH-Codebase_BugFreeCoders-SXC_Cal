"""
validate_warmup_dwell_fix.py
==============================
Multi-seed validation of the warmup_dwell_steps (+ jitter) fix for the
"warmup devastation under switch cost" bug found by switch_cost_comparison.py
and switch_lead_steps' own docstring: the warmup sweep switches bands on
literally every step, so under any real switch_cost_steps>0 it is stuck
settling forever and can NEVER accumulate a valid (post-settling)
observation -- lock-on doesn't just get worse, it can't happen at all.

This script deliberately checks variants that this project's own history
warns are easy to conflate on a single seed:

  A. dwell=1            (the original, broken-under-switch-cost behaviour)
  B. dwell>1, jitter=0, warmup unscaled (dwell only)
  C. dwell>1, jitter=0, warmup scaled   (dwell + budget compensation, no jitter)
  D. dwell>1, jitter=1, warmup scaled   (dwell + jitter + budget -- PRIAware)
  E. same as D but on PersistentPRIAwareScheduler (v4) instead of plain
     PRIAwareScheduler -- v4's characterization bonus targets exactly the
     residual sample-starvation coin-flip that D still shows (see results:
     D locks on a real majority of seeds but not all; E closes the gap).

...at multiple switch costs, over many seeds, with switch_lead_steps set
to match cost (the earlier, already-validated re-acquisition fix) so this
test isolates the LOCK-ON question specifically, not re-acquisition.

Run: python3 validate_warmup_dwell_fix.py
"""

import random
import statistics
from typing import List

from scan_scheduler_v2 import BeliefUCBScheduler, recommended_warmup_dwell
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler

N_BANDS = 36
N_STEPS = 4000
WARMUP = 800
SEEDS = list(range(1, 31))  # 30 seeds -- this project has repeatedly found
                              # single-seed and even 10-seed reads misleading


def capture(sched_cls, cost: int, seed: int, warmup: int = WARMUP, **kw):
    """Same methodology as switch_cost_comparison.py's capture(): switch
    cost is applied from t=0 (i.e. contaminates warmup too), which is the
    realistic case -- a real receiver's hardware doesn't know it's still
    in a 'warmup' phase."""
    scenario = make_sparse_scenario(N_BANDS)
    random.seed(seed)
    sched = sched_cls(N_BANDS, ucb_c=0.5, warmup_steps=warmup, **kw)
    env = scenario()
    radar_pulses = radar_caught = 0
    comm1_on = comm1_caught = 0
    prev_bands = set()
    settling_remaining = {}
    for t in range(N_STEPS):
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
    radar_pct = 100 * radar_caught / radar_pulses if radar_pulses else 0.0
    comm1_pct = 100 * comm1_caught / comm1_on if comm1_on else 0.0
    return radar_pct, comm1_pct, sched.confidence[5]


def summarize(label: str, vals: List[float]):
    mean = statistics.mean(vals)
    sd = statistics.pstdev(vals)
    locked = sum(1 for v in vals if v > 50.0)
    print(f"  {label:34s}: {mean:6.1f}% +/- {sd:5.1f}%   "
          f"(locked-on >50% in {locked}/{len(vals)} seeds,  "
          f"min={min(vals):5.1f}%  max={max(vals):5.1f}%)")


def main():
    for cost in (1, 2):
        lead = cost  # reuse the already-validated re-acquisition fix

        # Diagnosed directly (see chat): dwell=cost+1 alone still leaves the
        # per-band expected-hit count under the 8-hit lock-on threshold,
        # because dwelling means fewer warmup LAPS fit in the same fixed
        # step budget. dwell=cost+2 with the warmup budget scaled up by
        # roughly dwell/(dwell-cost) (to compensate for the settling steps
        # that no longer count as valid observations) restores a comparable
        # expected-hit count to the original dwell=1/no-switch-cost case.
        dwell = cost + 2
        warmup_scaled = int(WARMUP * dwell / (dwell - cost))
        assert recommended_warmup_dwell(cost, WARMUP, margin=2) == (dwell, warmup_scaled), \
            "recommended_warmup_dwell() drifted from this script's own derivation"

        print(f"{'='*100}\nswitch_cost_steps = {cost}   (warmup_dwell_steps = {dwell}, "
              f"warmup_steps scaled {WARMUP} -> {warmup_scaled}, switch_lead_steps = {lead})"
              f"\n{'='*100}")

        variants = {
            "A) dwell=1, warmup=800 (original, broken)": (WARMUP, PRIAwareScheduler, dict(
                warmup_dwell_steps=1, switch_lead_steps=lead)),
            "B) dwell, jitter=0, warmup=800 (dwell only, unscaled)": (WARMUP, PRIAwareScheduler, dict(
                warmup_dwell_steps=dwell, warmup_dwell_jitter=0, switch_lead_steps=lead)),
            "C) dwell, jitter=0, warmup scaled (no jitter)": (warmup_scaled, PRIAwareScheduler, dict(
                warmup_dwell_steps=dwell, warmup_dwell_jitter=0, switch_lead_steps=lead)),
            "D) dwell, jitter=1, warmup scaled (PRIAware)": (warmup_scaled, PRIAwareScheduler, dict(
                warmup_dwell_steps=dwell, warmup_dwell_jitter=1, switch_lead_steps=lead)),
            "E) dwell, jitter=1, warmup scaled + v4 persistent (FULL FIX)": (
                warmup_scaled, PersistentPRIAwareScheduler, dict(
                    warmup_dwell_steps=dwell, warmup_dwell_jitter=1, switch_lead_steps=lead)),
        }

        results = {name: {"radar": [], "comm1": [], "conf": []} for name in variants}
        for seed in SEEDS:
            for name, (warmup, cls, kw) in variants.items():
                radar_pct, comm1_pct, conf = capture(cls, cost, seed,
                                                      warmup=warmup, **kw)
                results[name]["radar"].append(radar_pct)
                results[name]["comm1"].append(comm1_pct)
                results[name]["conf"].append(conf)

        print(f"\nRadar capture (band 5, {len(SEEDS)} seeds):")
        for name in variants:
            summarize(name, results[name]["radar"])

        print(f"\nComm-1 capture (band 1, the cost, {len(SEEDS)} seeds):")
        for name in variants:
            summarize(name, results[name]["comm1"])

        print(f"\nFinal periodicity confidence on band 5 ({len(SEEDS)} seeds):")
        for name in variants:
            vals = results[name]["conf"]
            print(f"  {name:46s}: mean={statistics.mean(vals):.2f}  "
                  f"locked(>=0.5) in {sum(1 for v in vals if v >= 0.5)}/{len(vals)} seeds")
        print()

    print(f"{'='*100}\nSanity check: cost=0 must reproduce the exact existing headline "
          f"(100.0% / 79.0%), all variants collapse to the same thing since dwell/jitter "
          f"only matter when there's something to settle from\n{'='*100}")
    for name, kw in {
        "dwell=1 (default)": dict(warmup_dwell_steps=1),
        "dwell=2, jitter=1": dict(warmup_dwell_steps=2, warmup_dwell_jitter=1),
    }.items():
        radar_pct, comm1_pct, conf = capture(PRIAwareScheduler, 0, seed=11, **kw)
        print(f"  {name:22s}: radar={radar_pct:.1f}%  comm1={comm1_pct:.1f}%  conf={conf:.2f}")


if __name__ == "__main__":
    main()
