"""
prediction_accuracy_metrics.py
================================
Reports the two problem-statement figures of merit that the codebase
already computes almost all the raw ingredients for, but never rolls up
into a standalone number:

  - "percentage of correct predictions" -- reuses
    validate_pdw_multiseed.classify()'s per-band, per-seed verdict
    (CORRECT / HARMONIC / WRONG / NO LOCK against the true PRI), and
    reports %CORRECT across all (scheduler, band, seed) instances as one
    headline number per scheduler. Almost pure aggregation of an
    existing function -- no new modeling.

  - "average intercept time error" -- NOT the same thing as the already-
    reported avg_intercept_delay (which measures reactive detection
    latency: how many steps after a transmission *started* did the
    scheduler notice it). This measures predictive accuracy instead:
    every time a PRI-aware scheduler locks onto a band and confirms a
    hit, it implicitly predicts the next occurrence at
    (this hit's step + pri_estimate). We check that prediction against
    PDWReplayEnvironment's ground truth (via next_transmission_after,
    which reads steps the receiver never even scanned) and record the
    error in microseconds. The scheduler itself never sees this ground
    truth -- it's evaluation-only, same as classify() already is.

Run: python3 prediction_accuracy_metrics.py
     python3 prediction_accuracy_metrics.py --seeds 30 --dwell-us 20
"""

import argparse
import statistics
from typing import Dict, List

from pdw_environment import PDWReplayEnvironment
from pdw_source import (PDWSource, PDWSourceError, add_window_args,
                        window_from_args)
from scan_scheduler_v3_pri import PRIAwareScheduler
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
from scan_aware_scheduler import ScanAwarePRIScheduler
from validate_pdw_multiseed import TRUE_PERIODIC_BANDS, classify

# Rebound in main(): SOURCE is the active PDWSource (None -> synthetic
# stand-in built fresh per call); TRUTH is (band -> true period) --
# TRUE_PERIODIC_BANDS with the synthetic stand-in, or derived from the
# real file's own metadata with --h5 (see PDWSource.true_periodic_bands
# in pdw_source.py for why an arbitrary .h5's truth can't just reuse
# the stand-in's constant).
SOURCE = None
TRUTH = TRUE_PERIODIC_BANDS


def _predict_next(sched, band, t):
    """The scheduler's own implicit prediction for the NEXT occurrence
    on `band`, given it just confirmed a hit at `t`.

    For a uniform-PRI lock this is simply t + pri_estimate. For a
    STAGGERED lock, pri_estimate is the group-sum PERIOD (needed for
    confidence/gating and for _periodicity_score's multi-point scoring)
    -- NOT the gap to the very next pulse, which is usually much
    shorter than a full cycle (5-9 steps here, vs a 35-step period).
    Using the flat PRI formula for a staggered band would score every
    prediction as being off by nearly a full cycle even though the
    scheduler's own stagger_pattern/stagger_phase already know the
    right answer -- same kind of unfair-to-the-scheduler mismatch
    run_one_with_predictions_scanaware's docstring describes for
    ScanAwarePRIScheduler, fixed the same way: predict off what the
    scheduler itself actually trusts, not a formula that happens to fit
    a simpler model."""
    if (getattr(sched, "is_staggered", [False] * len(sched.pri_estimate))[band]
            and sched.stagger_pattern[band] is not None
            and sched.stagger_phase[band] is not None):
        pattern = sched.stagger_pattern[band]
        return t + pattern[sched.stagger_phase[band] % len(pattern)]
    return t + sched.pri_estimate[band]


def run_one_with_predictions(seed, cls, n_bands, dwell_us, k, extra_kwargs=None):
    """Like validate_pdw_multiseed.run_one(), but also walks the episode
    manually so we can capture each phase prediction the instant it's
    made and check it against ground truth."""
    source = SOURCE or PDWSource(n_bands=n_bands)
    pdw = source.for_seed(seed)
    env = PDWReplayEnvironment(pdw, n_bands=n_bands, dwell_us=dwell_us,
                                freq_range_mhz=source.freq_range_mhz,
                                t0_us=source.t0_us)
    sched = cls(n_bands, ucb_c=0.5, **(extra_kwargs or {}))

    errors_us: Dict[int, List[float]] = {b: [] for b in TRUTH}

    for t in range(env.n_steps):
        status = env.step()
        bands = sched.choose_bands(k)
        for band in bands:
            observed_on = status[band]
            sched.update(band, observed_on)
            if not observed_on or band not in TRUTH:
                continue
            if not hasattr(sched, "pri_estimate"):
                continue
            if sched.confidence[band] < sched.min_confidence:
                continue
            pri = sched.pri_estimate[band]
            if pri is None:
                continue
            # This hit was just appended by update(), so hit_times[-1] == t.
            predicted_next = _predict_next(sched, band, t)
            true_next = env.next_transmission_after(band, t)
            if true_next is not None:
                errors_us[band].append(abs(predicted_next - true_next) * dwell_us)

    return sched, errors_us


def run_one_with_predictions_scanaware(seed, cls, n_bands, dwell_us, k, extra_kwargs=None):
    """ScanAwarePRIScheduler-specific variant of run_one_with_predictions.

    ScanAwarePRIScheduler tracks TWO periodicities (scan_period_estimate
    for when the next burst starts, pri_estimate for pulse timing WITHIN
    a burst) and its self.confidence is synced to scan_confidence, not
    pri_confidence (see scan_aware_scheduler.py's _update_scan_model).
    Reusing run_one_with_predictions' single-tier "predicted_next = t +
    pri_estimate" formula against this scheduler is not a fair test: on
    a target with no real nested burst structure (confirmed directly,
    fixed-PRI band 1 of this scenario, seed 0), pri_estimate degenerates
    into noise from the scheduler's own sparse, self-selected sampling,
    while scan_period_estimate correctly converges on the true period
    -- so predicting off pri_estimate produces large, spurious errors
    even though the scheduler's own periodicity model has, in effect,
    already found the right answer under a different name. This variant
    predicts the next BURST ONSET from scan_period_estimate/
    burst_starts (what the scheduler itself trusts and gates
    self.confidence on), matching what ScanAwarePRIScheduler is actually
    designed to estimate.

    burst_starts entries are the scheduler's internal absolute clock
    (self.t), which runs one step ahead of this function's physical
    loop variable `t` -- confirmed directly by tracing band 6 (true
    PRI=1500us/75 steps): the raw anchor always came out as `t + 1`,
    collapsing the prediction to "now" instead of one cycle ahead until
    corrected by subtracting 1 before mixing it with `t` or with
    env.next_transmission_after's physical-unit result. The original
    PRI-based formula above does NOT have this issue -- pri is a
    duration, not an absolute timestamp, so the offset cancels out
    algebraically there. This anchor-conversion issue is scoped to this
    scan-aware absolute-timestamp arithmetic, not the codebase at
    large."""
    source = SOURCE or PDWSource(n_bands=n_bands)
    pdw = source.for_seed(seed)
    env = PDWReplayEnvironment(pdw, n_bands=n_bands, dwell_us=dwell_us,
                                freq_range_mhz=source.freq_range_mhz,
                                t0_us=source.t0_us)
    sched = cls(n_bands, ucb_c=0.5, **(extra_kwargs or {}))

    errors_us: Dict[int, List[float]] = {b: [] for b in TRUTH}

    for t in range(env.n_steps):
        status = env.step()
        bands = sched.choose_bands(k)
        for band in bands:
            observed_on = status[band]
            sched.update(band, observed_on)
            if not observed_on or band not in TRUTH:
                continue
            if sched.confidence[band] < sched.min_confidence:
                continue
            period = sched.scan_period_estimate[band]
            starts = sched.burst_starts[band]
            if period is None or period <= 0 or not starts:
                continue
            # burst_starts holds the scheduler's own internal absolute
            # clock (self.t, incremented at the top of choose_bands
            # before this loop's hit is recorded), which runs exactly
            # one step ahead of this loop's `t` (the physical/env row
            # index just read by env.step()). Confirmed directly: the
            # unconverted anchor always came out as `t + 1`. A period
            # (a difference of two such timestamps) is unaffected by
            # the offset, but the absolute anchor itself must be
            # converted back to physical units before mixing with `t`
            # or with env.next_transmission_after's physical result --
            # skipping that conversion previously collapsed the
            # prediction to "now" instead of one cycle ahead.
            last_burst_phys = starts[-1] - 1
            gap = t - last_burst_phys
            n_cycles = int(gap // period) + 1 if gap >= 0 else 0
            predicted_next = last_burst_phys + n_cycles * period
            true_next = env.next_transmission_after(band, t)
            if true_next is not None:
                errors_us[band].append(abs(predicted_next - true_next) * dwell_us)

    return sched, errors_us


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--dwell-us", type=float, default=20.0)
    ap.add_argument("--n-bands", type=int, default=8)
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--h5", default=None,
                     help="Run against a real TSRD .h5 instead of the synthetic "
                          "stand-in. True periods are derived from the file's own "
                          "metadata (see pdw_source.PDWSource.true_periodic_bands) "
                          "rather than the stand-in's hard-coded constant. Load "
                          "failure is fatal.")
    add_window_args(ap)
    args = ap.parse_args()

    global SOURCE, TRUTH
    try:
        SOURCE = PDWSource(h5_path=args.h5, n_bands=args.n_bands,
                           window_s=window_from_args(args))
    except PDWSourceError as exc:
        raise SystemExit(f"FATAL: {exc}")
    if args.h5:
        TRUTH, _ = SOURCE.true_periodic_bands(args.n_bands)
        print(SOURCE.banner(args.n_bands, args.dwell_us) + "\n")
        if not TRUTH:
            raise SystemExit(
                "FATAL: no band in this source has a defensible true period, so "
                "every prediction-accuracy number this script produces would be "
                "meaningless. Reasons per band are printed above.")

    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    n_bands, dwell_us, k = args.n_bands, args.dwell_us, args.k

    builders = {
        "PRIAware (current, both fixes)": (PRIAwareScheduler, {}),
        "PersistentPRIAware (v4)": (PersistentPRIAwareScheduler, {}),
        "ScanAwarePRIScheduler (Gap #2)": (ScanAwarePRIScheduler, {}),
    }

    print(f"Prediction-accuracy metrics, {len(seeds)} seeds ({seeds[0]}..{seeds[-1]}), "
          f"dwell={dwell_us}us\n")

    for name, (cls, kw) in builders.items():
        # ScanAwarePRIScheduler needs its own evaluation path -- see
        # run_one_with_predictions_scanaware's docstring for why.
        scan_aware = issubclass(cls, ScanAwarePRIScheduler)

        # %CORRECT across all (band, seed) classify() verdicts.
        verdicts: List[str] = []
        all_errors: Dict[int, List[float]] = {b: [] for b in TRUTH}

        for seed in seeds:
            if scan_aware:
                sched, errors_us = run_one_with_predictions_scanaware(
                    seed, cls, n_bands, dwell_us, k, kw)
                period_estimate = sched.scan_period_estimate
            else:
                sched, errors_us = run_one_with_predictions(seed, cls, n_bands, dwell_us, k, kw)
                period_estimate = sched.pri_estimate
            for band, true_pri in TRUTH.items():
                verdicts.append(classify(period_estimate[band], dwell_us, true_pri,
                                          sched.confidence[band], sched.min_confidence))
                all_errors[band].extend(errors_us[band])

        pct_correct = 100.0 * verdicts.count("CORRECT") / len(verdicts)

        print(f"{name}")
        print(f"  Percentage of correct predictions (final-state lock-on, "
              f"all bands/seeds): {pct_correct:.1f}%  "
              f"({verdicts.count('CORRECT')}/{len(verdicts)})")

        flat_errors = [e for band_errs in all_errors.values() for e in band_errs]
        if flat_errors:
            print(f"  Average intercept time error (predicted-vs-true next occurrence): "
                  f"{statistics.mean(flat_errors):.2f} us  "
                  f"(n={len(flat_errors)} predictions, stdev={statistics.stdev(flat_errors):.2f} us)")
        else:
            print("  Average intercept time error: no predictions were ever made "
                  "(scheduler never reached min_confidence)")

        for band, true_pri in TRUTH.items():
            errs = all_errors[band]
            if errs:
                print(f"    band {band} (true PRI={true_pri:.0f}us): "
                      f"mean err={statistics.mean(errs):6.2f}us over {len(errs)} predictions")
            else:
                print(f"    band {band} (true PRI={true_pri:.0f}us): no locked predictions")
        print()


if __name__ == "__main__":
    main()
