"""
validate_beacon_switchcost_dwell.py
=====================================
Generalizes validate_warmup_dwell_fix.py's 30-seed methodology from the
sparse single-pulse radar to the multi-step BEACON scenario (PeriodicEmitter
on bands [2,5,6], true period 12 steps, ON for 4 consecutive steps per
cycle -- see make_scenario() in scan_scheduler_prototype.py).

Important difference discovered while setting this up, worth stating up
front rather than assuming the sparse-radar recipe transfers unchanged:
this project has ALWAYS run the beacon comparison with warmup_steps=0 (no
explicit warmup phase at all) -- unlike the sparse radar, which needed an
800-step warmup to have any chance of characterizing a 1-in-12 signal.
Checked directly: even at switch_cost=0 with warmup=0, PRIAware's
periodicity confidence on bands 2/5/6 locks on inconsistently across
seeds (often 0.00/0.00/0.00, sometimes one band locks) -- the beacon's
2-state Markov belief already carries most of the interception weight,
which is exactly why the original beacon-regression work characterized
PRIAware as "roughly a wash" against plain BeliefUCB there.

So this script checks TWO separate questions, not one:
  1. Does switch_cost_steps degrade beacon interception at all under the
     project's existing warmup=0 convention (same question asked of
     RoundRobin/Random/BeliefUCB in switch_cost_comparison.py, extended
     to PRIAware/PersistentPRIAware)?
  2. Does explicitly adding the dwell+jitter+switch_lead+v4 fix combo
     (validated on the sparse radar) actually help here, or is it a
     wasted, even counterproductive, warmup investment for a scenario
     that doesn't lean on periodicity locking the way the radar does?

RESULT (30 seeds, k=1 and k=2, cost=1 and cost=2): question 2's answer is
NO -- the fix does NOT generalize, and is actively counterproductive here.
Plain PRIAware with the project's existing warmup=0 convention beats every
"+fix" variant on both interception rate AND periodicity lock-on rate, at
every (k, cost) combination tested. Isolating the mechanism (see
isolate_mechanism() below) shows the artificial warmup-dwell phase itself
is the cost, not switch_lead_steps (which is close to neutral here, same
as found earlier): the beacon's high duty cycle (ON 4 of every 12 steps,
across 3 bands) means the scheduler's ordinary online belief+UCB learning
already visits it plenty even under switch cost -- there's no sample-
starvation problem to fix. A forced, uniform, blind warmup sweep just
burns budget that the adaptive policy would otherwise have spent more
productively. The sparse-radar fix is a fix for genuinely rare,
sample-starved periodic signals specifically, not a universal switch-cost
patch -- applying it to a signal that was never starved in the first
place is a net loss.

Run: python3 validate_beacon_switchcost_dwell.py
"""

import random
import statistics
from typing import List

from scan_scheduler_v2 import (
    RoundRobinScheduler, BeliefUCBScheduler, run_episode, recommended_warmup_dwell
)
from scan_scheduler_v3_pri import PRIAwareScheduler
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
from scan_scheduler_prototype import make_scenario

N_BANDS = 36
N_STEPS = 4000
SEEDS = list(range(1, 31))
BASE_WARMUP = 800  # only used by the "+fix" variants, matching the radar validation


def run_one(cls, seed, k, cost, **kw):
    random.seed(seed)
    scenario = make_scenario(N_BANDS)
    if cls is RoundRobinScheduler:
        sched = cls(N_BANDS)
    elif cls is BeliefUCBScheduler:
        sched = cls(N_BANDS, ucb_c=0.5, **kw)
    else:
        sched = cls(N_BANDS, ucb_c=0.5, **kw)
    stats = run_episode(scenario, sched, N_STEPS, N_BANDS, k_channels=k, switch_cost_steps=cost)
    r = stats.report()
    beacon_conf = max(sched.confidence[b] for b in (2, 5, 6)) if hasattr(sched, "confidence") else 0.0
    return r["interception_ratio"] * 100, beacon_conf


def summarize(label, vals):
    mean = statistics.mean(vals)
    sd = statistics.pstdev(vals)
    print(f"  {label:52s}: {mean:6.1f}% +/- {sd:5.1f}%   (min={min(vals):5.1f}%  max={max(vals):5.1f}%)")


def main(ks=(1, 2)):
    for k in ks:
        print(f"{'='*100}\nBeacon scenario, k_channels={k}  ({len(SEEDS)} seeds)\n{'='*100}")
        for cost in (0, 1, 2):
            dwell, warmup_scaled = recommended_warmup_dwell(cost, BASE_WARMUP, margin=2) \
                if cost > 0 else (1, 0)
            print(f"\n--- switch_cost_steps = {cost} "
                  f"{'(fix variants use warmup_dwell_steps=' + str(dwell) + ', warmup_steps=' + str(warmup_scaled) + ', switch_lead_steps=' + str(cost) + ')' if cost > 0 else '(baseline, no fix applicable)'} ---")

            variants = {
                "RoundRobin (open-loop reference)": (RoundRobinScheduler, {}),
                "BeliefUCB (Markov-only)": (BeliefUCBScheduler, {}),
                "PRIAware, warmup=0 (project's existing convention)": (PRIAwareScheduler, {}),
            }
            if cost > 0:
                fix_kw = dict(warmup_steps=warmup_scaled, warmup_dwell_steps=dwell,
                               warmup_dwell_jitter=1, switch_lead_steps=cost)
                variants["PRIAware + dwell/jitter/lead fix"] = (PRIAwareScheduler, fix_kw)
                variants["PersistentPRIAware(v4) + dwell/jitter/lead fix"] = (
                    PersistentPRIAwareScheduler, fix_kw)

            results = {name: {"intercept": [], "conf": []} for name in variants}
            for seed in SEEDS:
                for name, (cls, kw) in variants.items():
                    pct, conf = run_one(cls, seed, k, cost, **kw)
                    results[name]["intercept"].append(pct)
                    results[name]["conf"].append(conf)

            for name in variants:
                summarize(name, results[name]["intercept"])
            print("  beacon periodicity lock-on (max confidence across bands 2/5/6):")
            for name in variants:
                vals = results[name]["conf"]
                locked = sum(1 for v in vals if v >= 0.5)
                print(f"    {name:50s}: mean_conf={statistics.mean(vals):.2f}  "
                      f"locked(>=0.5) in {locked}/{len(SEEDS)} seeds")
        print()


def isolate_mechanism(cost: int = 1, k: int = 1, seeds=range(1, 11)):
    """Which piece of the sparse-radar fix is actually responsible for the
    beacon regression -- the artificial warmup-dwell phase, or
    switch_lead_steps? Isolates them independently."""
    scenario = make_scenario(N_BANDS)
    dwell, warmup_scaled = recommended_warmup_dwell(cost, BASE_WARMUP, margin=2)
    configs = {
        "1) baseline: warmup=0, lead=0": dict(),
        f"2) dwell-fix only: warmup={warmup_scaled},dwell={dwell},jit=1, lead=0": dict(
            warmup_steps=warmup_scaled, warmup_dwell_steps=dwell, warmup_dwell_jitter=1),
        f"3) lead only: warmup=0, lead={cost}": dict(switch_lead_steps=cost),
        "4) both (the combo tested above)": dict(
            warmup_steps=warmup_scaled, warmup_dwell_steps=dwell, warmup_dwell_jitter=1,
            switch_lead_steps=cost),
    }
    print(f"\n{'='*100}\nMechanism isolation (cost={cost}, k={k}): which piece of the fix "
          f"actually costs interception?\n{'='*100}")
    for name, kw in configs.items():
        intercepts = []
        for seed in seeds:
            random.seed(seed)
            sched = PRIAwareScheduler(N_BANDS, ucb_c=0.5, **kw)
            stats = run_episode(scenario, sched, N_STEPS, N_BANDS, k_channels=k,
                                 switch_cost_steps=cost)
            intercepts.append(stats.report()["interception_ratio"] * 100)
        print(f"  {name:60s}: {statistics.mean(intercepts):5.1f}% +/- "
              f"{statistics.pstdev(intercepts):4.1f}%")


if __name__ == "__main__":
    import sys
    ks = tuple(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else (1, 2)
    main(ks)
    if ks == (1, 2) or 1 in ks:
        isolate_mechanism(cost=1, k=1)
