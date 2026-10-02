"""
diagnose_pri_lockon.py
=======================
Digs into WHY PRIAwareScheduler's lock-on on the sparse fixed-PRI radar
(band 5, true period 12, single-step pulse) is so seed-sensitive --
30.0% +/- 48.3% capture across 10 seeds, per multi_seed_robustness.py.

Approach: instrument the scheduler internals directly (scan counts, hit
counts, and every intermediate value _update_pri_model computes for band
5) across many seeds, and look at what actually differs between seeds
that lock on and seeds that don't.

Run: python3 diagnose_pri_lockon.py
"""

import random
import statistics
from collections import Counter

from scan_scheduler_v2 import BeliefUCBScheduler
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario

N_BANDS = 36
N_STEPS = 4000
WARMUP = 800
RADAR_BAND = 5
TRUE_PRI = 12
N_SEEDS = 40


class InstrumentedPRIAware(PRIAwareScheduler):
    """Same as PRIAwareScheduler, but logs every _update_pri_model call
    for RADAR_BAND (seed candidate, refined pri, rmse, confidence) so we
    can see exactly why a given seed did or didn't lock on."""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.log = []  # list of dicts, one per _update_pri_model(RADAR_BAND) call

    def _update_pri_model(self, band):
        before_len = len(self.hit_times[band])
        super()._update_pri_model(band)
        if band == RADAR_BAND:
            self.log.append({
                "t": self.t,
                "n_hits_so_far": before_len,
                "pri_estimate": self.pri_estimate[band],
                "confidence": self.confidence[band],
            })


def run_one(seed):
    scenario = make_sparse_scenario(N_BANDS)
    random.seed(seed)
    sched = InstrumentedPRIAware(N_BANDS, ucb_c=0.5, warmup_steps=WARMUP)
    env = scenario()

    scans_on_band5_warmup = 0
    hits_on_band5_warmup = 0      # band5 scanned AND on, during warmup
    actual_pulses_warmup = 0      # band5 actually on, during warmup (whether scanned or not)
    scans_on_band5_post = 0
    hits_on_band5_post = 0
    actual_pulses_post = 0

    for t in range(N_STEPS):
        status = env.step()
        bands = sched.choose_bands(1)
        for b in bands:
            sched.update(b, status[b])

        in_warmup = t < WARMUP
        if status[RADAR_BAND]:
            if in_warmup:
                actual_pulses_warmup += 1
            else:
                actual_pulses_post += 1
        if RADAR_BAND in bands:
            if in_warmup:
                scans_on_band5_warmup += 1
                if status[RADAR_BAND]:
                    hits_on_band5_warmup += 1
            else:
                scans_on_band5_post += 1
                if status[RADAR_BAND]:
                    hits_on_band5_post += 1

    return {
        "seed": seed,
        "scans_warmup": scans_on_band5_warmup,
        "hits_warmup": hits_on_band5_warmup,
        "pulses_warmup": actual_pulses_warmup,
        "scans_post": scans_on_band5_post,
        "hits_post": hits_on_band5_post,
        "pulses_post": actual_pulses_post,
        "final_hit_times_len": len(sched.hit_times[RADAR_BAND]),
        "final_pri": sched.pri_estimate[RADAR_BAND],
        "final_confidence": sched.confidence[RADAR_BAND],
        "log": sched.log,
        "radar_capture_pct": hits_on_band5_post / actual_pulses_post if actual_pulses_post else 0.0,
    }


def main():
    print(f"Sparse radar: band {RADAR_BAND}, true PRI = {TRUE_PRI} steps, "
          f"warmup = {WARMUP} steps, {N_STEPS} steps total, {N_SEEDS} seeds\n")
    print("Theory check: warmup uses a shuffled full sweep over 8 bands each lap, "
          f"so band {RADAR_BAND} gets scanned ~{WARMUP // N_BANDS} times during warmup "
          f"(exactly once per lap). The radar is ON for only 1/{TRUE_PRI} of all steps, "
          f"so if warmup scans landed on band {RADAR_BAND} at effectively random step "
          f"offsets, the EXPECTED number of confirmed hits during warmup is roughly "
          f"{WARMUP // N_BANDS} / {TRUE_PRI} = {(WARMUP // N_BANDS) / TRUE_PRI:.1f}.\n"
          f"_update_pri_model requires >= 8 confirmed hits before it will even attempt "
          f"an estimate. That expected count sits right AT the threshold -- so whether "
          f"a seed clears 8 hits by the end of warmup is a coin-flip, not a robust "
          f"property of the scheduler.\n")

    results = [run_one(s) for s in range(1, N_SEEDS + 1)]

    hits_warmup_vals = [r["hits_warmup"] for r in results]
    scans_warmup_vals = [r["scans_warmup"] for r in results]
    print(f"Confirmed hits on band {RADAR_BAND} accumulated DURING warmup, across {N_SEEDS} seeds:")
    print(f"  mean = {statistics.mean(hits_warmup_vals):.2f}, stdev = {statistics.stdev(hits_warmup_vals):.2f}, "
          f"min = {min(hits_warmup_vals)}, max = {max(hits_warmup_vals)}")
    print(f"  (scans on band {RADAR_BAND} during warmup: mean = {statistics.mean(scans_warmup_vals):.1f}, "
          f"expected ~{WARMUP // N_BANDS})")
    below_8 = sum(1 for h in hits_warmup_vals if h < 8)
    print(f"  seeds with < 8 confirmed hits by END of warmup: {below_8}/{N_SEEDS}\n")

    locked = [r for r in results if r["final_confidence"] >= 0.75]
    not_locked = [r for r in results if r["final_confidence"] < 0.75]
    print(f"Final lock-on outcome: {len(locked)}/{N_SEEDS} seeds reached confidence >= 0.75 "
          f"by end of run; {len(not_locked)}/{N_SEEDS} never did.\n")

    print(f"{'seed':>5s} | {'hits@warmup':>11s} | {'final_hits':>10s} | {'final_pri':>10s} | "
          f"{'confidence':>10s} | {'radar_capture%':>14s}")
    print("-" * 75)
    for r in results:
        pri_s = f"{r['final_pri']:.2f}" if r['final_pri'] is not None else "None"
        print(f"{r['seed']:5d} | {r['hits_warmup']:11d} | {r['final_hit_times_len']:10d} | "
              f"{pri_s:>10s} | {r['final_confidence']:10.2f} | {r['radar_capture_pct']*100:13.1f}%")

    # Look at HOW EARLY it locks on, for seeds that do lock on -- if it's
    # locking on late (well after warmup ends), that means the ~800-step
    # warmup budget isn't actually enough, and post-warmup scanning is
    # what's really tipping it over the threshold in a lucky subset of seeds.
    print("\nFor seeds that DID lock on (confidence >= 0.75), when did that happen "
          "relative to warmup end (t=800)?")
    for r in locked:
        first_lock = next((e for e in r["log"] if e["confidence"] >= 0.75), None)
        if first_lock:
            print(f"  seed {r['seed']:3d}: first locked at t={first_lock['t']:5d} "
                  f"({'during warmup' if first_lock['t'] <= WARMUP else 'AFTER warmup, delta=' + str(first_lock['t'] - WARMUP)}), "
                  f"n_hits at that point = {first_lock['n_hits_so_far']}")

    # For seeds that never locked on, show the closest they got and why
    # (not enough hits at all vs. enough hits but wrong candidate/high rmse).
    print("\nFor seeds that NEVER locked on, what happened instead?")
    for r in not_locked:
        if not r["log"]:
            print(f"  seed {r['seed']:3d}: never reached 8 confirmed hits at all "
                  f"(final count = {r['final_hit_times_len']})")
        else:
            best = max(r["log"], key=lambda e: e["confidence"])
            print(f"  seed {r['seed']:3d}: best attempt reached confidence={best['confidence']:.2f} "
                  f"pri_estimate={best['pri_estimate']} at t={best['t']} "
                  f"(n_hits={best['n_hits_so_far']}, final count={r['final_hit_times_len']})")


if __name__ == "__main__":
    main()
