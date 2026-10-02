"""
validate_pdw_multiseed.py
============================
Multi-seed validation of the harmonic-lock-on fix (candidate selection
by best refined-fit RMSE, not the coarse tolerance test) specifically on
the Turing synthetic PDW stand-in -- this is the dataset the fix was
actually diagnosed and motivated on (diagnose_beacon_regression.py found
it while checking run_on_turing_dataset.py, via a single seed where the
old selection locked onto ~65 instead of the true ~32.5). Until now it's
only been spot-checked on a handful of individual seeds, never run
through a proper multi-seed harness on THIS dataset -- suite E of
multi_seed_robustness.py predates the harmonic fix, and the 30-seed
validation in validate_plateau_fix.py / settle_fix_interaction.py only
covers the beacon scenario, not PDW data.

generate_synthetic_pdw_stream() has three fixed-frequency constant-PRI
emitters with real (~2%) PRI jitter, which land in three known receiver
bands at n_bands=8:

    band 1: cf=2400 MHz, true PRI = 1000 us
    band 4: cf=9200 MHz, true PRI =  650 us  (the fractional case: at
            dwell=20us this is 32.505 scan-steps -- not an integer,
            which is exactly the condition that let a harmonic (65,
            i.e. 2x) out-score the true fundamental under the OLD
            coarse tolerance-based candidate selection)
    band 6: cf=14300 MHz, true PRI = 1500 us

Two frequency-agile hoppers are also present, spread across several
bands each -- they should NOT lock onto periodicity confidently on any
single band (a negative control, same role the comm/agile bands played
in the beacon-scenario validation).

Compares four scheduler states:
    BeliefUCB              -- no periodicity model at all (baseline)
    PlateauOnly             -- plateau fix only, OLD coarse-tolerance
                               candidate selection (pre-harmonic-fix
                               reconstruction, reused from
                               validate_plateau_fix.py)
    PRIAware (current)      -- both fixes, as shipped
    PersistentPRIAware (v4) -- both fixes + the sample-starvation fix

For each of the 3 known periodic bands and each seed, classifies the
scheduler's result as:
    CORRECT   -- locked on (confidence >= min_confidence) within 5% of
                 the true period
    HARMONIC  -- locked on, but on a ~0.5x/2x/3x multiple of the truth
    WRONG     -- locked on to something else entirely
    NO LOCK   -- never reached min_confidence

Since generate_synthetic_pdw_stream()'s data is fully determined by its
own numpy seed (independent of Python's `random` module), and every
scheduler here runs with warmup_steps=0 (so none of them consume their
own randomness either -- same fact `settle_fix_interaction.py`
established for the beacon scenario), every scheduler sees a byte-
identical environment for a given seed regardless of build/run order.
No confound to guard against here, unlike the beacon scenario.

Run: python3 validate_pdw_multiseed.py
     python3 validate_pdw_multiseed.py --seeds 20 --dwell-us 20
"""

import argparse
import random
import statistics
from typing import Dict, List

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
from validate_plateau_fix import PlateauOnlyPRIAware
from pdw_environment import PDWReplayEnvironment
from pdw_source import (PDWSource, PDWSourceError, add_window_args,
                        window_from_args, suggest_windows)

# (band, true_pri_us) at n_bands=8, freq_range (0,18000) -- see module
# docstring for how these map from generate_synthetic_pdw_stream's fixed
# emitters via PDWReplayEnvironment's band binning.
TRUE_PERIODIC_BANDS = {1: 1000.0, 4: 650.0, 6: 1500.0}

# NOTE: the constant above is ONLY valid for the synthetic stand-in, and
# only at n_bands=8 / freq_range (0, 18000). With --h5 the truth is
# derived instead from the real file's own transmitter metadata
# (PDWSource.true_periodic_bands), and a band that cannot be defended --
# shared by two emitters, fed by a frequency hopper, or on a PRI mode
# with no single period -- gets NO truth entry rather than being scored
# against a number borrowed from a different emitter entirely.


def classify(estimated_pri_steps, dwell_us, true_pri_us, confidence, min_confidence):
    if confidence < min_confidence or estimated_pri_steps is None:
        return "NO LOCK"
    true_steps = true_pri_us / dwell_us
    ratio = estimated_pri_steps / true_steps
    if abs(ratio - 1.0) <= 0.05:
        return "CORRECT"
    for h in (0.5, 2.0, 3.0, 1.0 / 3.0):
        if abs(ratio - h) <= 0.05:
            return "HARMONIC"
    return "WRONG"


def run_one(seed, cls, n_bands, dwell_us, k, extra_kwargs=None, source=None):
    source = source or PDWSource(n_bands=n_bands)
    pdw = source.for_seed(seed)

    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=n_bands, dwell_us=dwell_us,
                                     freq_range_mhz=source.freq_range_mhz,
                                     t0_us=source.t0_us)

    n_steps = env_factory().n_steps
    random.seed(seed)  # no-op for randomness (warmup_steps=0), kept for clarity/consistency
    sched = cls(n_bands, ucb_c=0.5, **(extra_kwargs or {}))
    stats = run_episode(env_factory, sched, n_steps, n_bands, k_channels=k)
    return stats.report()["interception_ratio"], sched


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--dwell-us", type=float, default=20.0,
                     help="Fine dwell to match the fractional-PRI headline test "
                          "(650us/20us = 32.505 steps, non-integer)")
    ap.add_argument("--n-bands", type=int, default=8)
    ap.add_argument("--h5", default=None,
                     help="Run against a real TSRD .h5 instead of the synthetic stand-in. "
                          "Ground truth is then derived from the file's own metadata, and "
                          "seeds stop varying the environment (one fixed recording) -- they "
                          "only vary scheduler randomness. A load failure is fatal.")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--csv", default="pdw_multiseed_results.csv")
    add_window_args(ap)
    args = ap.parse_args()

    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    n_bands = args.n_bands
    dwell_us = args.dwell_us
    k = args.k

    try:
        source = PDWSource(h5_path=args.h5, n_bands=n_bands,
                           window_s=window_from_args(args))
    except PDWSourceError as exc:
        raise SystemExit(f"FATAL: {exc}")
    truth, truth_notes = source.true_periodic_bands(n_bands)

    print(source.banner(n_bands, dwell_us) + "\n")
    print(f"PDW multi-seed validation of the harmonic-lock-on fix, {len(seeds)} seeds "
          f"({seeds[0]}..{seeds[-1]}), dwell={dwell_us}us, k={k}")
    print(f"True periodic bands in use: {truth}\n")
    if not truth:
        raise SystemExit(
            "FATAL: no band in this source has a defensible true period, so every "
            "CORRECT/HARMONIC/WRONG verdict this script produces would be meaningless. "
            "Reasons per band are printed above.")

    builders = {
        "BeliefUCB": (BeliefUCBScheduler, {}),
        "PlateauOnly (pre-harmonic-fix)": (PlateauOnlyPRIAware, {}),
        "PRIAware (current, both fixes)": (PRIAwareScheduler, {}),
        "PersistentPRIAware (v4)": (PersistentPRIAwareScheduler, {}),
    }

    interception: Dict[str, List[float]] = {name: [] for name in builders}
    # classification[name][band] -> list of classify() results, one per seed
    classification: Dict[str, Dict[int, List[str]]] = {
        name: {b: [] for b in truth} for name in builders
    }

    for seed in seeds:
        for name, (cls, kw) in builders.items():
            ratio, sched = run_one(seed, cls, n_bands, dwell_us, k, kw, source=source)
            interception[name].append(ratio)
            if hasattr(sched, "pri_estimate"):
                for band, true_pri in truth.items():
                    verdict = classify(sched.pri_estimate[band], dwell_us, true_pri,
                                        sched.confidence[band], sched.min_confidence)
                    classification[name][band].append(verdict)

    print(f"{'Scheduler':32s} | {'Interception %':>18s}")
    print("-" * 55)
    for name, vals in interception.items():
        print(f"{name:32s} | {statistics.mean(vals)*100:8.1f}% +/- {statistics.stdev(vals)*100:4.1f}pp")

    print(f"\nPer-band lock-on classification across {len(seeds)} seeds "
          f"(CORRECT = within 5% of true period; HARMONIC = locked on a ~0.5x/2x/3x multiple "
          f"of the truth; WRONG = locked on something else; NO LOCK = never reached confidence "
          f">= min_confidence):\n")
    for name in builders:
        if not any(classification[name][b] for b in truth):
            continue
        print(f"{name}:")
        for band, true_pri in truth.items():
            verdicts = classification[name][band]
            counts = {v: verdicts.count(v) for v in ("CORRECT", "HARMONIC", "WRONG", "NO LOCK")}
            true_steps = true_pri / dwell_us
            print(f"  band {band} (true PRI={true_pri:.0f}us = {true_steps:.3f} steps): "
                  f"CORRECT={counts['CORRECT']:2d}  HARMONIC={counts['HARMONIC']:2d}  "
                  f"WRONG={counts['WRONG']:2d}  NO LOCK={counts['NO LOCK']:2d}  "
                  f"(/{len(seeds)} seeds)")
        print()

    # The fractional-PRI case (band 4, non-integer step period) is the one
    # the harmonic fix specifically targets -- highlight it directly.
    if 4 in truth and source.kind == "synthetic":
        print("Headline comparison for the fractional-PRI band (band 4, true = 32.505 steps) -- "
              "this is exactly the case the harmonic-selection fix was built for:")
        for name in ("PlateauOnly (pre-harmonic-fix)", "PRIAware (current, both fixes)"):
            v = classification[name][4]
            correct = v.count("CORRECT")
            harmonic = v.count("HARMONIC")
            print(f"  {name:32s}: {correct}/{len(seeds)} correct, {harmonic}/{len(seeds)} harmonic-locked")

    import csv
    import os
    if os.path.exists(args.csv):
        os.remove(args.csv)
    with open(args.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["data_source", "seed_semantics", "scheduler", "seed",
                    "interception_ratio"] + [f"band{b}_verdict" for b in truth])
        for name in builders:
            for i, seed in enumerate(seeds):
                row = [source.provenance, source.seed_semantics, name, seed,
                       interception[name][i]]
                row += [classification[name][b][i] if classification[name][b] else ""
                        for b in truth]
                w.writerow(row)
    print(f"\nRaw per-seed results written to {args.csv}")


if __name__ == "__main__":
    main()
