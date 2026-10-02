"""
tune_confidence_threshold.py
===============================
settle_fix_interaction.py found a real, mechanistically-understood cost:
the harmonic-selection fix (pick candidates by best refined-fit RMSE)
makes PRIAwareScheduler lock on MORE EAGERLY -- with less evidence --
than the old coarse-tolerance selection did. That's exactly the right
property for the PDW dataset's fractional-PRI-vs-harmonic problem, but
it's a small, real tax (-0.3pp, won only 2/30) on the beacon scenario's
multi-step burst, where the extra confidence sometimes locks onto a
band that would've been better served by plain Markov belief.

The confidence formula's denominator scale is the direct knob for this
tradeoff:

    confidence = 1 - rmse / (confidence_scale * refined_pri)

Larger confidence_scale = more forgiving = reaches high confidence with
a looser relative fit (more eager). Smaller = requires a tighter fit
(more conservative). This sweeps a small grid of values and checks BOTH
sides of the tradeoff this fix has to balance:

  1. Beacon scenario, identical-environment comparison (reusing
     settle_fix_interaction's methodology): does a smaller scale recover
     some/all of the -0.3pp Current-vs-PlateauOnly cost at k=2, without
     costing more at k=1?
  2. PDW fractional-PRI case (reusing validate_pdw_multiseed's
     classification): does a smaller scale preserve the harmonic fix's
     whole point -- correctly locking onto band 4's true 32.505-step
     period instead of a harmonic or nothing?

A value that helps (1) but breaks (2) is not actually a fix -- it would
just be re-introducing the original coarse-tolerance selection's
conservatism through a different knob. The right answer needs to move
(1) without moving (2).

Run: python3 tune_confidence_threshold.py
     python3 tune_confidence_threshold.py --beacon-seeds 30 --pdw-seeds 20
"""

import argparse
import random
import statistics
from typing import Dict, List

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario
from validate_plateau_fix import PlateauOnlyPRIAware
from validate_pdw_multiseed import TRUE_PERIODIC_BANDS, classify
from pdw_source import PDWSource, PDWSourceError, add_window_args, window_from_args
from pdw_environment import PDWReplayEnvironment

CANDIDATE_SCALES = [0.25, 0.20, 0.17, 0.15, 0.12, 0.10]  # 0.25 = current/original


# ----------------------------------------------------------------------
# Check 1: beacon scenario, identical environments (settle_fix_interaction
# methodology) -- Current(scale) vs PlateauOnly and vs BeliefUCB.
# ----------------------------------------------------------------------

def run_identical_env(seed, sched_cls, n_bands=8, n_steps=4000, k=2, **kw):
    scenario = make_scenario(n_bands)
    random.seed(seed)
    sched = sched_cls(n_bands, ucb_c=0.5, **kw)
    stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
    return stats.report()["interception_ratio"]


def beacon_check(scale, seeds, k):
    results = {"BeliefUCB": [], "PlateauOnly": [], f"Current(scale={scale})": []}
    for seed in seeds:
        results["BeliefUCB"].append(run_identical_env(seed, BeliefUCBScheduler, k=k))
        results["PlateauOnly"].append(run_identical_env(seed, PlateauOnlyPRIAware, k=k))
        results[f"Current(scale={scale})"].append(
            run_identical_env(seed, PRIAwareScheduler, k=k, confidence_scale=scale))
    cur = results[f"Current(scale={scale})"]
    plateau = results["PlateauOnly"]
    belief = results["BeliefUCB"]
    d_vs_plateau = [c - p for c, p in zip(cur, plateau)]
    d_vs_belief = [c - b for c, b in zip(cur, belief)]
    return {
        "vs_plateau_mean": statistics.mean(d_vs_plateau) * 100,
        "vs_plateau_wins": sum(1 for d in d_vs_plateau if d > 0),
        "vs_belief_mean": statistics.mean(d_vs_belief) * 100,
        "vs_belief_wins": sum(1 for d in d_vs_belief if d > 0),
        "n": len(seeds),
    }


# ----------------------------------------------------------------------
# Check 2: PDW fractional-PRI case (band 4) -- does the scale preserve
# correct lock-on (not regress toward the pre-harmonic-fix's failures)?
# ----------------------------------------------------------------------

def pdw_check(scale, seeds, n_bands=8, dwell_us=20.0, k=1, source=None, band=None,
              true_pri=None):
    """Lock-on classification on the fractional-PRI band as confidence_scale varies.

    With the synthetic stand-in this is band 4 (650us -> 32.505 steps).
    With --h5 the band and its true period come from the file's own
    metadata instead, because band 4 of an arbitrary recording has
    nothing to do with the stand-in's 650us emitter."""
    source = source or PDWSource(n_bands=n_bands)
    if band is None:
        band, true_pri = 4, TRUE_PERIODIC_BANDS[4]
    correct = harmonic = no_lock = wrong = 0
    for seed in seeds:
        pdw = source.for_seed(seed)

        def env_factory(pdw=pdw):
            return PDWReplayEnvironment(pdw, n_bands=n_bands, dwell_us=dwell_us,
                                         freq_range_mhz=source.freq_range_mhz,
                                         t0_us=source.t0_us)

        n_steps = env_factory().n_steps
        sched = PRIAwareScheduler(n_bands, ucb_c=0.5, confidence_scale=scale)
        run_episode(env_factory, sched, n_steps, n_bands, k_channels=k)
        verdict = classify(sched.pri_estimate[band], dwell_us, true_pri,
                            sched.confidence[band], sched.min_confidence)
        correct += verdict == "CORRECT"
        harmonic += verdict == "HARMONIC"
        no_lock += verdict == "NO LOCK"
        wrong += verdict == "WRONG"
    return {"correct": correct, "harmonic": harmonic, "no_lock": no_lock, "wrong": wrong, "n": len(seeds)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--beacon-seeds", type=int, default=20)
    ap.add_argument("--pdw-seeds", type=int, default=15)
    ap.add_argument("--h5", default=None,
                     help="Run the PDW half of the sweep against a real TSRD .h5 (truth "
                          "from its metadata). The beacon half is a controlled synthetic "
                          "scenario and is unaffected. Load failure is fatal.")
    ap.add_argument("--n-bands", type=int, default=8)
    ap.add_argument("--dwell-us", type=float, default=20.0)
    add_window_args(ap)
    args = ap.parse_args()

    try:
        source = PDWSource(h5_path=args.h5, n_bands=args.n_bands,
                           window_s=window_from_args(args))
    except PDWSourceError as exc:
        raise SystemExit(f"FATAL: {exc}")
    truth, _ = source.true_periodic_bands(args.n_bands)
    if source.kind == "synthetic":
        pdw_band, pdw_true = 4, TRUE_PERIODIC_BANDS[4]
    elif truth:
        # Pick the band with the finest resolvable period at this dwell --
        # the closest real analogue of the stand-in's fractional-PRI case.
        pdw_band = min(truth, key=lambda b: abs(truth[b] / args.dwell_us - round(truth[b] / args.dwell_us)) * -1)
        pdw_true = truth[pdw_band]
        print(source.banner(args.n_bands, args.dwell_us) + "\n")
        print(f"PDW half of the sweep uses band {pdw_band} (true period {pdw_true:.2f} us "
              f"= {pdw_true/args.dwell_us:.3f} steps at dwell {args.dwell_us} us)\n")
    else:
        raise SystemExit("FATAL: no defensible true period in this .h5 -- the PDW half of "
                         "this sweep would be scoring against a number that does not exist.")

    beacon_seeds = list(range(1, args.beacon_seeds + 1))
    pdw_seeds = list(range(0, args.pdw_seeds))

    print(f"Sweeping confidence_scale over {CANDIDATE_SCALES}\n"
          f"Beacon check: {args.beacon_seeds} seeds, identical-environment methodology, k=1 and k=2\n"
          f"PDW check: {args.pdw_seeds} seeds, band {pdw_band} (true PRI={pdw_true:.0f}us) lock-on classification\n")

    print(f"{'scale':>7s} | {'k=1 vs Plateau':>15s} | {'k=2 vs Plateau':>15s} | "
          f"{'k=2 vs BeliefUCB':>17s} | {'PDW band correct':>18s} | {'PDW harmonic':>13s} | {'PDW no-lock':>12s}")
    print("-" * 115)

    rows = []
    for scale in CANDIDATE_SCALES:
        b1 = beacon_check(scale, beacon_seeds, k=1)
        b2 = beacon_check(scale, beacon_seeds, k=2)
        p = pdw_check(scale, pdw_seeds, n_bands=args.n_bands, dwell_us=args.dwell_us,
                       source=source, band=pdw_band, true_pri=pdw_true)
        rows.append((scale, b1, b2, p))
        print(f"{scale:7.2f} | {b1['vs_plateau_mean']:+6.1f}pp ({b1['vs_plateau_wins']:2d}/{b1['n']}) | "
              f"{b2['vs_plateau_mean']:+6.1f}pp ({b2['vs_plateau_wins']:2d}/{b2['n']}) | "
              f"{b2['vs_belief_mean']:+7.1f}pp ({b2['vs_belief_wins']:2d}/{b2['n']}) | "
              f"{p['correct']:15d}/{p['n']} | {p['harmonic']:10d}/{p['n']} | {p['no_lock']:9d}/{p['n']}")

    print("\nReading this table: we want, relative to scale=0.25 (the current/original value):\n"
          "  - k=2 vs Plateau delta to move toward 0 or positive (currently -0.3pp/2-3 wins out of ~30\n"
          "    in the full validation -- here on a smaller 20-seed sweep sample)\n"
          "  - k=1 vs Plateau delta to not get meaningfully worse\n"
          "  - PDW band correct-lock count to stay at or above scale=0.25's count (NOT regress\n"
          "    toward PlateauOnly's pre-fix 14/20 -- see validate_pdw_multiseed.py)\n")

    baseline = rows[0]
    assert baseline[0] == 0.25
    print(f"Baseline (scale=0.25): k=1 vs Plateau {baseline[1]['vs_plateau_mean']:+.1f}pp, "
          f"k=2 vs Plateau {baseline[2]['vs_plateau_mean']:+.1f}pp, "
          f"PDW band correct {baseline[3]['correct']}/{baseline[3]['n']}\n")

    best = None
    for scale, b1, b2, p in rows[1:]:
        improves_k2 = b2["vs_plateau_mean"] > baseline[2]["vs_plateau_mean"]
        no_worse_k1 = b1["vs_plateau_mean"] >= baseline[1]["vs_plateau_mean"] - 0.5
        preserves_pdw = p["correct"] >= baseline[3]["correct"]
        print(f"  scale={scale:.2f}: k=2 improves={improves_k2} (delta {b2['vs_plateau_mean']:+.1f}pp), "
              f"k=1 no-worse={no_worse_k1} (delta {b1['vs_plateau_mean']:+.1f}pp), "
              f"PDW preserved={preserves_pdw} ({p['correct']}/{p['n']} vs baseline {baseline[3]['correct']}/{baseline[3]['n']})")
        if improves_k2 and no_worse_k1 and preserves_pdw and best is None:
            best = scale

    if best is not None:
        print(f"\nSelected confidence_scale = {best} -- improves the beacon k=2 eagerness cost "
              f"without regressing k=1 or the PDW fractional-PRI lock-on.")
    else:
        print("\nNo candidate strictly improved on all three fronts -- keeping confidence_scale=0.25 "
              "(the original value) rather than trading away the PDW benefit for a beacon-only gain.")

    return best


if __name__ == "__main__":
    main()
