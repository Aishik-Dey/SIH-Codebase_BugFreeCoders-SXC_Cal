"""
run_on_turing_dataset.py
==========================
Runs the FULL improved scheduler stack -- RoundRobin / Random baselines,
BeliefUCB (Markov + UCB exploration), PRIAware (+ periodicity
detection), and PersistentPRIAware (the seed-robustness fix from
diagnose_pri_lockon.py) -- against a Turing Synthetic Radar Dataset
(TSRD) pulse train, with multi-channel scanning, a warm-up sweep, and
optional per-band threat priority all wired through.

This supersedes two earlier versions of this script: the first only ran
the old single-channel, fixed-epsilon BeliefScheduler from
scan_scheduler_prototype.py; the second added BeliefUCB/PRIAware but
was never repointed to PersistentPRIAwareScheduler once that fix landed
in scan_scheduler_v4_persistent.py. That mattered here specifically:
the same 8-confirmed-hit threshold that made the sparse-radar toy
scenario's lock-on a coin flip applies just as much to a real/synthetic
PDW stream's low-duty fixed-PRI emitters -- nothing before this
actually confirmed the persistent fix helps on that path rather than
just the toy scenario it was diagnosed on.

switch_cost_steps / switch_lead_steps / warmup_dwell_steps (the receiver
re-tune settling cost from switch_cost_comparison.py, its
switch_lead_steps countermeasure, and the warmup_dwell_steps +
warmup_dwell_jitter fix from validate_warmup_dwell_fix.py) are wired
through here too, all default-off / backward compatible. IMPORTANT:
this wiring itself has only been exercised against the local synthetic
PDW stand-in, never against a real downloaded TSRD --h5 pulse train --
the dwell+jitter fix was validated on the toy sparse-radar/beacon
scenarios in scan_scheduler_prototype.py, and separately confirmed
scenario-specific there (helps a starved, low-duty emitter like a
sparse radar; hurts a dense multi-step beacon -- see
validate_beacon_switchcost_dwell.py). Whether real PDW data's low-duty
fixed-PRI emitters behave like the sparse-radar case or something else
entirely is untested. Treat any --switch-cost-steps > 0 result here as
unvalidated until it's been run against real data and, ideally, over
multiple seeds (this script is still single-seed, like everything else
that hasn't gone through a dedicated multi_seed_*.py harness).

Usage:
    python3 run_on_turing_dataset.py                          # local synthetic stand-in
    python3 run_on_turing_dataset.py --h5 path.h5              # a real downloaded pulse train
                                                                # (needs turing_deinterleaving_challenge
                                                                #  installed -- see pdw_loader.py)
    python3 run_on_turing_dataset.py --k-channels 2 --warmup-steps 500
    python3 run_on_turing_dataset.py --priority "1,1,1,1,5,1,1,1"   # weight band 4 as 5x priority
    python3 run_on_turing_dataset.py --switch-cost-steps 1 --switch-lead-steps 1 \\
        --warmup-dwell-steps 3 --warmup-dwell-jitter 1
                                                                # manual switch-cost knobs
    python3 run_on_turing_dataset.py --switch-cost-steps 1 --auto-dwell
                                                                # same, but dwell/lead/warmup-steps
                                                                # auto-derived via
                                                                # recommended_warmup_dwell()
                                                                # (UNTESTED on real PDW data --
                                                                # see module docstring)
"""

import argparse
import random

from scan_scheduler_v2 import (
    RoundRobinScheduler, RandomScheduler, BeliefUCBScheduler, run_episode,
    recommended_warmup_dwell
)
from scan_scheduler_v3_pri import PRIAwareScheduler
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler
from scan_scheduler_whittle import WhittleIndexScheduler
from pdw_environment import PDWReplayEnvironment
from pdw_source import (PDWSource, PDWSourceError, add_window_args,
                        window_from_args, suggest_windows)


def parse_priority(spec, n_bands):
    if not spec:
        return None
    values = [float(x) for x in spec.split(",")]
    if len(values) != n_bands:
        raise ValueError(f"--priority needs exactly {n_bands} comma-separated values, got {len(values)}")
    return values


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--h5", default=None,
                     help="Path to a real TSRD .h5 pulse train. A load failure here is "
                          "FATAL -- this script no longer falls back to the synthetic "
                          "stand-in, because a run that asked for real data and quietly "
                          "got fake data is worse than one that crashes.")
    ap.add_argument("--max-steps", type=int, default=0,
                     help="Cap the replay at this many scan steps (0 = no cap). A real "
                          "recording spans tens of seconds, so at a PRI-resolving dwell "
                          "(20 us) it is ~10^6 steps -- orders of magnitude longer than "
                          "any episode this codebase has ever run. Cap it, or raise "
                          "--dwell-us, and say which you did.")
    ap.add_argument("--n-bands", type=int, default=36, help="Number of receiver sub-bands")
    ap.add_argument("--dwell-us", type=float, default=200.0,
                     help="Receiver dwell time per scan step, in microseconds")
    ap.add_argument("--k-channels", type=int, default=1,
                     help="Number of bands the receiver can dwell on simultaneously per step")
    ap.add_argument("--warmup-steps", type=int, default=0,
                     help="Shuffled round-robin sweep steps before switching to learned scoring "
                          "(needed to reliably learn a period on rare/low-duty emitters)")
    ap.add_argument("--ucb-c", type=float, default=0.5, help="UCB exploration constant")
    ap.add_argument("--confidence-scale", type=float, default=0.25,
                     help="PRI confidence formula's denominator scale (confidence = 1 - rmse / "
                          "(confidence_scale * period)). Smaller = requires a tighter fit before "
                          "trusting a candidate period (more conservative); larger = more eager to "
                          "lock on. Default (0.25) is tuned for real/synthetic PDW data -- see "
                          "tune_confidence_threshold.py for the sweep and its trade-off against the "
                          "beacon toy scenario (a smaller value modestly helps that scenario but "
                          "costs real fractional-PRI lock-on reliability here).")
    ap.add_argument("--min-cycles", type=int, default=4,
                     help="Minimum DISTINCT observed cycles required before a periodicity lock "
                          "is accepted (counts cycles, not raw hits). Guards against the "
                          "degenerate-fit bug found on real dense-burst data: history_len sizes "
                          "the hit window in HITS, so a bursty emitter can fill it with only 2-3 "
                          "independent looks at the period, letting a line fit through cluster "
                          "centroids report a wildly wrong period at high confidence (seen on "
                          "config_169.h5 band 1: PRI=6354 steps at confidence 0.98 against a true "
                          "700us, before this guard). The 8-hit history threshold alone does not "
                          "catch this since it counts hits, not cycles.")
    ap.add_argument("--max-blend-confidence", type=float, default=1.0,
                     help="Caps the confidence value used in the score BLEND only (never the lock "
                          "decision itself). At 1.0 (default, byte-for-byte identical to every "
                          "prior run), a confident staggered-PRI lock can zero out belief's weight "
                          "entirely, making the scheduler ignore an emitter between its narrow "
                          "periodicity spikes even though nothing better exists to switch to -- "
                          "seen on config_169.h5 band 1, where a real, exact stagger lock still "
                          "made interception worse (44.3%% vs BeliefUCB's 93.7%%). A confirmed Pareto "
                          "trade-off, same pattern as --confidence-scale: no single value both "
                          "helps this case and preserves the sparse-radar headline (cap<=0.8 helps "
                          "but costs the headline; cap=0.9 preserves it but gives zero improvement "
                          "here) -- deployment-specific dial, not tuned further.")
    ap.add_argument("--eta", type=float, default=4.0,
                     help="HedgeBlended only: Hedge multiplicative-weights learning rate for the "
                          "per-band, per-episode belief-vs-periodicity trust weight (replaces "
                          "--max-blend-confidence's single global cap with a learned one). Swept "
                          "in sweep_eta.py against all four references: 4.0 (the default, never "
                          "chosen for any reason beyond being a plausible starting point until "
                          "that sweep) turned out to be the ONLY value achieving perfect PDW "
                          "band-4 fractional-PRI lock reliability (5/5 seeds; every other tested "
                          "value, both lower and higher, drops to 3/5 or 4/5) -- band-4 has been "
                          "fixed and re-fixed more than any other single case in this project's "
                          "history, so that reliability was kept even though real config_169.h5 "
                          "band-1 alone would prefer eta>=6 (99.6%% vs 98.0%% at eta=4, a smaller "
                          "trade than band-4's reliability is worth). No effect on any other "
                          "scheduler.")
    ap.add_argument("--with-whittle", action="store_true",
                     help="Also run WhittleIndexScheduler (restless-bandit index policy). Opt-in "
                          "because it was measured at ~199s per run on the full real config_169.h5 "
                          "(vs. seconds for everything else) -- too slow for the default table. "
                          "Its real-file result on record: 93.7% (k=1, warmup=0).")
    ap.add_argument("--class-balance-alpha", type=float, default=0.1,
                     help="HedgeBlended only: linearly interpolates the Hedge loss between "
                          "unweighted (0.0) and fully class-balanced (1.0) -- see "
                          "sweep_class_balance_alpha.py. Fixes a real bug where an UNLOCKED "
                          "periodicity expert's placeholder-0 prediction could win the weight "
                          "competition against calibrated belief purely from class imbalance on "
                          "any low-duty band (alpha=0.0 reproduces that: PDW band-4 never locks). "
                          "The relationship is a sharp THRESHOLD, not a smooth trade-off: alpha=0.02 "
                          "still fails to lock band-4, alpha=0.05 already matches full balancing's "
                          "lock quality exactly. The default (0.1) sits just above that threshold "
                          "with a safety margin, trading real band-1's 99.6%% (at full alpha=1.0 "
                          "balancing, which costs 94.7%%) for 98.0%% -- recovering most of the cost "
                          "of fixing band-4 rather than paying the full amount.")
    ap.add_argument("--priority", default=None,
                     help="Comma-separated per-band priority weights, e.g. '1,1,1,1,5,1,1,1' "
                          "to weight band 4 as 5x -- lets you trade some easy-target interception "
                          "for guaranteed capture of a specific band")
    ap.add_argument("--seed", type=int, default=0, help="Seed for the synthetic stand-in")
    ap.add_argument("--switch-cost-steps", type=int, default=0,
                     help="Steps of receiver re-tune settling time charged whenever a channel "
                          "moves to a band it wasn't scanning last step (see run_episode's "
                          "docstring in scan_scheduler_v2.py). Default 0 = free/instant "
                          "switching, byte-for-byte identical to every prior run of this script. "
                          "UNTESTED against real PDW data at > 0 -- see module docstring.")
    ap.add_argument("--switch-lead-steps", type=int, default=0,
                     help="PRIAware/PersistentPRIAware only: start favoring a periodic band this "
                          "many steps before its predicted pulse, so a switch's settling time "
                          "(--switch-cost-steps) finishes right as the pulse arrives instead of "
                          "the receiver still settling when it hits. Set equal to "
                          "--switch-cost-steps as a starting point, or use --auto-dwell. Has no "
                          "effect on RoundRobin/Random/BeliefUCB (no periodicity model to lead).")
    ap.add_argument("--warmup-dwell-steps", type=int, default=1,
                     help="Repeat each warm-up sweep band-visit this many steps (+jitter) instead "
                          "of advancing every step, so the sweep survives --switch-cost-steps "
                          "settling delay instead of never getting a valid look. Default 1 = "
                          "original every-step sweep. Only useful once --switch-cost-steps > 0 -- "
                          "see recommended_warmup_dwell() / --auto-dwell for how to size this and "
                          "--warmup-steps together.")
    ap.add_argument("--warmup-dwell-jitter", type=int, default=1,
                     help="Random 0..N extra steps added to each warm-up dwell visit. Load-"
                          "bearing whenever --warmup-dwell-steps > 1: validated (30 seeds, the toy "
                          "sparse-radar scenario) that dwelling with jitter=0 fails deterministically "
                          "(a fixed settling/valid-step parity some seeds' true pulse phase can "
                          "never land on). Ignored when --warmup-dwell-steps is 1.")
    ap.add_argument("--auto-dwell", action="store_true",
                     help="When --switch-cost-steps > 0, ignore --warmup-dwell-steps/"
                          "--switch-lead-steps and instead derive them (plus a scaled-up "
                          "--warmup-steps) from recommended_warmup_dwell(), the same helper "
                          "switch_cost_comparison.py uses. Convenience only, not a validated "
                          "default for real PDW data -- see module docstring.")
    add_window_args(ap)
    args = ap.parse_args()

    try:
        source = PDWSource(h5_path=args.h5, n_bands=args.n_bands,
                           window_s=window_from_args(args))
    except PDWSourceError as exc:
        raise SystemExit(f"FATAL: {exc}")
    pdw = source.for_seed(args.seed)
    # Seeds every scheduler's OWN internal randomness (warm-up sweep
    # shuffle order, warmup_dwell_jitter) -- found missing while adding
    # --eta/--class-balance-alpha: running the exact same command twice
    # gave different HedgeBlended numbers (25.6% then 23.9%), because
    # --seed only ever reached source.for_seed() (which uses its own
    # independent np.random.default_rng(seed), confirmed unaffected by
    # this call) -- the scheduler-side `random` module was never seeded
    # at all, drawing from OS entropy fresh every process invocation.
    # Every scheduler that uses warm-up (BeliefUCB and everything built
    # on it) was affected whenever --warmup-steps > 0, not just the
    # newly-added HedgeBlended entry. Placed after source.for_seed()
    # so environment/data generation (numpy-seeded, independent) is
    # provably unaffected by this.
    random.seed(args.seed)
    print(source.banner(args.n_bands, args.dwell_us) + "\n")
    priority = parse_priority(args.priority, args.n_bands)

    warmup_steps = args.warmup_steps
    warmup_dwell_steps = args.warmup_dwell_steps
    warmup_dwell_jitter = args.warmup_dwell_jitter
    switch_lead_steps = args.switch_lead_steps
    if args.switch_cost_steps > 0 and args.auto_dwell:
        warmup_dwell_steps, warmup_steps = recommended_warmup_dwell(
            args.switch_cost_steps, args.warmup_steps, margin=2)
        warmup_dwell_jitter = 1
        switch_lead_steps = args.switch_cost_steps
        print(f"--auto-dwell: derived warmup_dwell_steps={warmup_dwell_steps}, "
              f"warmup_steps={args.warmup_steps}->{warmup_steps}, "
              f"switch_lead_steps={switch_lead_steps} from switch_cost_steps="
              f"{args.switch_cost_steps} (margin=2)\n")

    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=args.n_bands, dwell_us=args.dwell_us,
                                     freq_range_mhz=source.freq_range_mhz,
                                     t0_us=source.t0_us)

    probe = env_factory()
    n_steps = probe.n_steps
    if n_steps == 0:
        print("No pulses found in the loaded data -- nothing to replay.")
        return
    occ = probe.occupancy
    dead = [b for b in range(args.n_bands) if occ[b] == 0.0]
    print("Band occupancy (fraction of steps ON): " +
          ", ".join(f"b{b}={occ[b]*100:.3f}%" for b in range(args.n_bands)))
    if dead:
        print(f"  NOTE: bands {dead} are ON in 0% of steps -- permanently dead channels. "
              f"A learned scheduler beats round-robin partly just by noticing them, which "
              f"is a trivial win; discount the headline gap accordingly.")
    if args.max_steps and n_steps > args.max_steps:
        print(f"  Capping replay at --max-steps {args.max_steps} of {n_steps} available steps "
              f"({args.max_steps * args.dwell_us / 1e6:.2f} s of "
              f"{n_steps * args.dwell_us / 1e6:.2f} s).")
        n_steps = args.max_steps
    print()

    print(f"Replaying {n_steps} scan steps across {args.n_bands} bands "
          f"(dwell = {args.dwell_us} us, {n_steps * args.dwell_us / 1e6:.2f} s of data, "
          f"k_channels = {args.k_channels}, warmup_steps = {warmup_steps}, "
          f"switch_cost_steps = {args.switch_cost_steps})\n")
    if args.switch_cost_steps > 0:
        print("NOTE: switch_cost_steps > 0 -- this path (and the dwell/lead settings feeding "
              "it) has only been validated on toy scenarios, never against real PDW data. "
              "Treat these numbers as unvalidated. See module docstring.\n")

    schedulers = {
        "RoundRobin (open-loop baseline)": RoundRobinScheduler(args.n_bands),
        "Random (naive baseline)": RandomScheduler(args.n_bands),
        "BeliefUCB (Markov + UCB, learned)": BeliefUCBScheduler(
            args.n_bands, ucb_c=args.ucb_c, warmup_steps=warmup_steps, priority=priority,
            warmup_dwell_steps=warmup_dwell_steps, warmup_dwell_jitter=warmup_dwell_jitter),
        "PRIAware (Markov + periodicity, learned)": PRIAwareScheduler(
            args.n_bands, ucb_c=args.ucb_c, warmup_steps=warmup_steps, priority=priority,
            confidence_scale=args.confidence_scale, switch_lead_steps=switch_lead_steps,
            warmup_dwell_steps=warmup_dwell_steps, warmup_dwell_jitter=warmup_dwell_jitter,
            min_cycles=args.min_cycles, max_blend_confidence=args.max_blend_confidence),
        "PersistentPRIAware (seed-robust fix)": PersistentPRIAwareScheduler(
            args.n_bands, ucb_c=args.ucb_c, warmup_steps=warmup_steps, priority=priority,
            confidence_scale=args.confidence_scale, switch_lead_steps=switch_lead_steps,
            warmup_dwell_steps=warmup_dwell_steps, warmup_dwell_jitter=warmup_dwell_jitter,
            min_cycles=args.min_cycles, max_blend_confidence=args.max_blend_confidence),
        "HedgeBlended (adaptive belief/periodicity blend)": HedgeBlendedPRIAwareScheduler(
            args.n_bands, ucb_c=args.ucb_c, warmup_steps=warmup_steps, priority=priority,
            confidence_scale=args.confidence_scale, switch_lead_steps=switch_lead_steps,
            warmup_dwell_steps=warmup_dwell_steps, warmup_dwell_jitter=warmup_dwell_jitter,
            min_cycles=args.min_cycles, eta=args.eta,
            class_balance_alpha=args.class_balance_alpha),
    }
    if args.with_whittle:
        schedulers["WhittleIndex (restless-bandit index, slow)"] = WhittleIndexScheduler(
            args.n_bands, ucb_c=args.ucb_c, warmup_steps=warmup_steps, priority=priority,
            warmup_dwell_steps=warmup_dwell_steps, warmup_dwell_jitter=warmup_dwell_jitter)

    header = (f"{'Scheduler':40s} | {'Interception %':>15s} | "
              f"{'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s} | "
              f"{'Switches':>8s} | {'Wasted (settling)':>18s}")
    print(header)
    print("-" * len(header))
    pri_scheds = {}
    for name, sched in schedulers.items():
        stats = run_episode(env_factory, sched, n_steps, args.n_bands, k_channels=args.k_channels,
                             switch_cost_steps=args.switch_cost_steps)
        r = stats.report()
        print(f"{name:40s} | {r['interception_ratio']*100:14.1f}% | "
              f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s} | "
              f"{r['switches']:8d} | {r['wasted_scans']:18d}")
        if isinstance(sched, PRIAwareScheduler):
            pri_scheds[name] = sched

    for name, sched in pri_scheds.items():
        print(f"\nPRI diagnostic for {name} -- any bands where a stable period was detected "
              "(rest either aren't periodic, or didn't get enough samples this run):")
        found_any = False
        for b in range(args.n_bands):
            pri, conf = sched.pri_estimate[b], sched.confidence[b]
            if pri is not None:
                found_any = True
                print(f"  band {b}: estimated PRI = {pri} scan-steps "
                      f"(~{pri * args.dwell_us:.1f} us), confidence = {conf:.2f}")
        if not found_any:
            print("  none -- try --warmup-steps and/or a longer run if you expect "
                  "fixed-PRI emitters in this band assignment.")


if __name__ == "__main__":
    main()
