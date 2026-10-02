"""
diagnose_beacon_regression.py
================================
Digs into WHY PRIAwareScheduler loses to BeliefUCBScheduler on the beacon
scenario (scan_scheduler_v3_pri.make_scenario) specifically at
k_channels=2, per multi_seed_robustness.py suite C:

    k=1: PRIAware +1.5pp vs BeliefUCB, won  8/10 seeds  (PRI-awareness helps)
    k=2: PRIAware -1.5pp vs BeliefUCB, won  1/10 seeds  (PRI-awareness hurts)

Same scheduler, same scenario, opposite sign just from adding a second
scan channel. That sign flip is the thing to explain -- and note it's
NOT explained by "periodicity detection has a fixed cost": if it were a
fixed cost from extra bookkeeping, it would show up at k=1 too.

Two things are structurally different about this scenario that don't
exist in the sparse-radar scenario diagnose_pri_lockon.py already covered:

  1. THREE bands share one periodic identity (the beacon hops
     2 -> 5 -> 6 -> 2 -> ..., dwell=4), each learning its OWN independent
     confidence/PRI estimate for what is really one physical emitter.
  2. Band 6 is loaded with BOTH the beacon AND the frequency-agile
     threat (make_scenario: AgileEmitter bands=[0,3,6,7]) -- a genuine
     collision that injects random noise into band 6's periodicity
     signal specifically.

Hypothesis: with k=1, PRIAware is forced to make a single best bet per
step, so it naturally only chases the ONE currently-due beacon band.
With k=2, a second free channel is available every step -- if the
periodicity term inflates more than one of the three beacon bands'
scores at once (e.g. the phase bump for the ending burst and the phase
bump for the next incoming burst can both be non-trivial near a
transition, given jitter sigma), PRIAware can spend BOTH of its k=2
slots on beacon-adjacent bands in a single step, at the cost of a slot
BeliefUCB would have spent on an always-productive comm band instead.

Run: python3 diagnose_beacon_regression.py
"""

import random
import statistics
from typing import List

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario

N_BANDS = 36
N_STEPS = 4000
BEACON_BANDS = {2, 5, 6}
COMM_BANDS = {1, 4}
N_SEEDS = 10


def per_band_capture(sched_cls, k, seed):
    """Run one episode, tracking: per-band capture rate, how often BOTH
    of the k=2 scanned bands fall in BEACON_BANDS simultaneously (a
    "double beacon bet"), and how often such a double bet paid off
    (>=1 hit) vs wasted both slots (0 hits)."""
    random.seed(seed)
    scenario = make_scenario(N_BANDS)
    sched = sched_cls(N_BANDS, ucb_c=0.5)
    env = scenario()

    pulses = {b: 0 for b in range(N_BANDS)}
    caught = {b: 0 for b in range(N_BANDS)}
    double_beacon_bets = 0
    double_beacon_hits = 0     # >=1 of the 2 beacon-band bets was a hit
    double_beacon_full_miss = 0  # both beacon-band bets missed

    for t in range(N_STEPS):
        status = env.step()
        for b in range(N_BANDS):
            if status[b]:
                pulses[b] += 1
        bands = sched.choose_bands(k)
        for b in bands:
            sched.update(b, status[b])
            if status[b]:
                caught[b] += 1

        if k == 2 and len(bands) == 2:
            b0, b1 = bands
            if b0 in BEACON_BANDS and b1 in BEACON_BANDS:
                double_beacon_bets += 1
                hits = int(status[b0]) + int(status[b1])
                if hits >= 1:
                    double_beacon_hits += 1
                else:
                    double_beacon_full_miss += 1

    beacon_pulses = sum(pulses[b] for b in BEACON_BANDS)
    beacon_caught = sum(caught[b] for b in BEACON_BANDS)
    comm_pulses = sum(pulses[b] for b in COMM_BANDS)
    comm_caught = sum(caught[b] for b in COMM_BANDS)

    return {
        "beacon_capture": beacon_caught / beacon_pulses if beacon_pulses else 0.0,
        "comm_capture": comm_caught / comm_pulses if comm_pulses else 0.0,
        "double_beacon_bets": double_beacon_bets,
        "double_beacon_hits": double_beacon_hits,
        "double_beacon_full_miss": double_beacon_full_miss,
        "confidence": getattr(sched, "confidence", None),
        "per_band_capture": {
            b: (caught[b] / pulses[b] if pulses[b] else 0.0) for b in BEACON_BANDS
        },
        "scan_count": list(getattr(sched, "scan_count", [0] * N_BANDS)),
    }


def summarize(vals):
    return f"{statistics.mean(vals)*100:5.1f}% +/- {statistics.stdev(vals)*100:4.1f}%" if len(vals) > 1 else f"{vals[0]*100:5.1f}%"


def main():
    print(f"Beacon scenario: bands {sorted(BEACON_BANDS)} host the periodic beacon "
          f"(band 6 ALSO hosts the frequency-agile threat -- a genuine collision), "
          f"comm bands {sorted(COMM_BANDS)}. {N_SEEDS} seeds, {N_STEPS} steps.\n")

    for k in (1, 2):
        print(f"=== k_channels = {k} ===")
        beacon_belief, beacon_pri = [], []
        comm_belief, comm_pri = [], []
        double_bet_counts = []
        double_bet_hit_rates = []

        for seed in range(1, N_SEEDS + 1):
            r_belief = per_band_capture(BeliefUCBScheduler, k, seed)
            r_pri = per_band_capture(PRIAwareScheduler, k, seed)
            beacon_belief.append(r_belief["beacon_capture"])
            beacon_pri.append(r_pri["beacon_capture"])
            comm_belief.append(r_belief["comm_capture"])
            comm_pri.append(r_pri["comm_capture"])
            if k == 2:
                double_bet_counts.append(r_pri["double_beacon_bets"])
                total = r_pri["double_beacon_bets"]
                if total > 0:
                    double_bet_hit_rates.append(r_pri["double_beacon_hits"] / total)

        print(f"  Beacon capture   -- BeliefUCB: {summarize(beacon_belief)}   PRIAware: {summarize(beacon_pri)}")
        print(f"  Comm capture     -- BeliefUCB: {summarize(comm_belief)}   PRIAware: {summarize(comm_pri)}")
        if k == 2:
            print(f"  'Double beacon bet' steps (both k=2 slots on beacon bands, PRIAware only): "
                  f"mean {statistics.mean(double_bet_counts):.0f} / {N_STEPS} steps "
                  f"({statistics.mean(double_bet_counts)/N_STEPS*100:.1f}%)")
            if double_bet_hit_rates:
                print(f"  Of those double-bet steps, fraction landing >=1 hit: "
                      f"mean {statistics.mean(double_bet_hit_rates)*100:.1f}%  "
                      f"(a hit rate here below what a comm-band bet would get "
                      f"is the direct cost of this behaviour)")
        print()

    # One seed in full detail: confirm the confidence pattern across the
    # three beacon bands (does band 6's agile-threat collision actually
    # suppress its confidence relative to 2 and 5, as hypothesized?)
    print("Per-band confidence detail, seed=1, k=2 (PRIAware):")
    random.seed(1)
    scenario = make_scenario(N_BANDS)
    sched = PRIAwareScheduler(N_BANDS, ucb_c=0.5)
    env = scenario()
    for t in range(N_STEPS):
        status = env.step()
        bands = sched.choose_bands(2)
        for b in bands:
            sched.update(b, status[b])
    for b in sorted(BEACON_BANDS):
        pri = sched.pri_estimate[b]
        conf = sched.confidence[b]
        tag = " (also hosts agile threat)" if b == 6 else ""
        print(f"  band {b}{tag}: pri_estimate={pri}, confidence={conf:.2f}")


if __name__ == "__main__":
    main()
