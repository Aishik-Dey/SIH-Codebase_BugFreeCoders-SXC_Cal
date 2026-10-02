"""
multi_seed_robustness.py
=========================
Reruns every existing scheduler comparison (from scan_scheduler_prototype.py,
scan_scheduler_v2.py, scan_scheduler_v3_pri.py, and run_on_turing_dataset.py)
across N_SEEDS different random seeds instead of one fixed seed, and reports
mean +/- standard deviation (plus min/max and a paired win-count) for each
scheduler's interception ratio.

Why this matters: every number quoted so far (BeliefUCB beating RoundRobin,
PRIAware catching 100% of the sparse radar, the fractional-PRI fix, etc.)
came from a single seeded run each. Given how many subtle bugs were found
along the way purely by inspection, some of those "wins" could in principle
be a favorable draw of the random scenario/exploration noise rather than a
real, robust effect. This script settles that empirically instead of by
argument.

Design note on seeding: each existing script calls random.seed(seed) ONCE
per full comparison, then runs every scheduler in that comparison back to
back off the same continuously-advancing global `random` stream (this is
how the original scripts are written -- see e.g. scan_scheduler_v2.main()).
This harness replicates that convention exactly for each seed, so results
here are directly comparable to the single-seed numbers already reported.

Run:  python3 multi_seed_robustness.py
      python3 multi_seed_robustness.py --seeds 20      # more seeds
      python3 multi_seed_robustness.py --seeds 10 --seed-start 100
"""

import argparse
import random
import statistics
from typing import Callable, Dict, List

from scan_scheduler_prototype import (
    RoundRobinScheduler as V1RoundRobin,
    RandomScheduler as V1Random,
    BeliefScheduler,
    run_episode as run_episode_v1,
    make_scenario,
)
from scan_scheduler_v2 import (
    RoundRobinScheduler,
    RandomScheduler,
    BeliefUCBScheduler,
    run_episode,
)
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario, SparsePeriodicEmitter
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
from scan_aware_scheduler import ScanAwarePRIScheduler
from spatial_scan_emitter import SpatiallyScanningEmitter
from scan_scheduler_prototype import MarkovEmitter, AgileEmitter, Environment
from pdw_loader import generate_synthetic_pdw_stream
from pdw_source import PDWSource, PDWSourceError, add_window_args, window_from_args

# Rebound in main(); module-level default keeps the synthetic behaviour
# identical for any caller that imports a suite directly.
SOURCE = None
_FALLBACK_SOURCE = None


def _src():
    """The active PDW source, defaulting to the synthetic stand-in."""
    global _FALLBACK_SOURCE
    if SOURCE is not None:
        return SOURCE
    if _FALLBACK_SOURCE is None:
        _FALLBACK_SOURCE = PDWSource(n_bands=8)
    return _FALLBACK_SOURCE
from pdw_environment import PDWReplayEnvironment


# ----------------------------------------------------------------------
# Stats helpers
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
    """a - b, per seed (paired, since both used the same seed sequence)."""
    diffs = [a - b for a, b in zip(a_vals, b_vals)]
    wins = sum(1 for d in diffs if d > 0)
    s = summarize(diffs)
    s["wins"] = wins
    s["n_seeds"] = len(diffs)
    return s


def print_delta(label: str, delta: Dict, scale: float = 100.0):
    print(f"  {label:46s}: {delta['mean']*scale:+5.1f}pp +/- {delta['stdev']*scale:4.1f}pp "
          f"  (min {delta['min']*scale:+5.1f}pp, max {delta['max']*scale:+5.1f}pp)  "
          f"-- won in {delta['wins']}/{delta['n_seeds']} seeds")


# ----------------------------------------------------------------------
# Suite A: original prototype comparison (scan_scheduler_prototype.py)
# ----------------------------------------------------------------------

def suite_a_prototype(seeds: List[int], n_bands: int = 8, n_steps: int = 4000):
    scenario = make_scenario(n_bands)
    builders = {
        "RoundRobin (open-loop)": lambda: V1RoundRobin(n_bands),
        "Random (naive)": lambda: V1Random(n_bands),
        "BeliefScheduler (learned)": lambda: BeliefScheduler(n_bands, epsilon=0.08),
    }
    raw: Dict[str, List[float]] = {name: [] for name in builders}
    for seed in seeds:
        random.seed(seed)
        for name, build in builders.items():
            stats = run_episode_v1(scenario, build(), n_steps, n_bands)
            raw[name].append(stats.report()["interception_ratio"])

    print_summary_table(
        f"[A] Original prototype, single-channel, {len(seeds)} seeds "
        f"({n_steps} steps each)", {n: summarize(v) for n, v in raw.items()})
    print_delta("BeliefScheduler vs RoundRobin",
                paired_delta(raw["BeliefScheduler (learned)"], raw["RoundRobin (open-loop)"]))
    return raw


# ----------------------------------------------------------------------
# Suite B: multi-channel comparison (scan_scheduler_v2.py)
# ----------------------------------------------------------------------

def suite_b_multichannel(seeds: List[int], n_bands: int = 8, n_steps: int = 4000):
    scenario = make_scenario(n_bands)
    all_raw = {}
    for k in (1, 2, 3):
        builders = {
            "RoundRobin (open-loop)": lambda: RoundRobinScheduler(n_bands),
            "Random (naive)": lambda: RandomScheduler(n_bands),
            "BeliefUCB (learned)": lambda: BeliefUCBScheduler(n_bands, ucb_c=0.5),
        }
        raw: Dict[str, List[float]] = {name: [] for name in builders}
        for seed in seeds:
            random.seed(seed)
            for name, build in builders.items():
                stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=k)
                raw[name].append(stats.report()["interception_ratio"])
        print_summary_table(
            f"[B] Multi-channel (v2), k_channels={k}, {len(seeds)} seeds "
            f"({n_steps} steps each)", {n: summarize(v) for n, v in raw.items()})
        print_delta("BeliefUCB vs RoundRobin",
                    paired_delta(raw["BeliefUCB (learned)"], raw["RoundRobin (open-loop)"]))
        all_raw[k] = raw
    return all_raw


# ----------------------------------------------------------------------
# Suite C: beacon scenario, PRI-aware vs BeliefUCB (scan_scheduler_v3_pri.py)
# ----------------------------------------------------------------------

def suite_c_beacon(seeds: List[int], n_bands: int = 8, n_steps: int = 4000):
    scenario = make_scenario(n_bands)
    all_raw = {}
    for k in (1, 2):
        builders = {
            "RoundRobin (open-loop)": lambda: RoundRobinScheduler(n_bands),
            "BeliefUCB (Markov-only)": lambda: BeliefUCBScheduler(n_bands, ucb_c=0.5),
            "PRIAware (Markov+periodicity)": lambda: PRIAwareScheduler(n_bands, ucb_c=0.5),
        }
        raw: Dict[str, List[float]] = {name: [] for name in builders}
        for seed in seeds:
            random.seed(seed)
            for name, build in builders.items():
                stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=k)
                raw[name].append(stats.report()["interception_ratio"])
        print_summary_table(
            f"[C] Beacon scenario (v3), k_channels={k}, {len(seeds)} seeds "
            f"({n_steps} steps each)", {n: summarize(v) for n, v in raw.items()})
        print_delta("PRIAware vs BeliefUCB",
                    paired_delta(raw["PRIAware (Markov+periodicity)"], raw["BeliefUCB (Markov-only)"]))
        all_raw[k] = raw
    return all_raw


# ----------------------------------------------------------------------
# Suite D: sparse fixed-PRI radar scenario + per-emitter capture (v3_pri)
# ----------------------------------------------------------------------

def suite_d_sparse(seeds: List[int], n_bands: int = 8, n_steps: int = 4000, warmup: int = 800):
    scenario = make_sparse_scenario(n_bands)
    all_raw = {}
    for k in (1, 2):
        builders = {
            "RoundRobin (open-loop)": lambda: RoundRobinScheduler(n_bands),
            "BeliefUCB (Markov-only)": lambda: BeliefUCBScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
            "PRIAware (Markov+periodicity)": lambda: PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
        }
        raw: Dict[str, List[float]] = {name: [] for name in builders}
        for seed in seeds:
            random.seed(seed)
            for name, build in builders.items():
                stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=k)
                raw[name].append(stats.report()["interception_ratio"])
        print_summary_table(
            f"[D] Sparse fixed-PRI radar (v3), k_channels={k}, {len(seeds)} seeds, "
            f"{warmup}-step warmup ({n_steps} steps each)", {n: summarize(v) for n, v in raw.items()})
        print_delta("PRIAware vs BeliefUCB (blended %)",
                    paired_delta(raw["PRIAware (Markov+periodicity)"], raw["BeliefUCB (Markov-only)"]))
        all_raw[k] = raw

    # Per-emitter capture: this is the metric that actually mattered in the
    # single-seed run (blended % was misleading; radar vs comm-1 capture
    # told the real story). Rerun that across seeds too.
    def per_emitter_capture(sched_cls, seed):
        random.seed(seed)
        sched = sched_cls(n_bands, ucb_c=0.5, warmup_steps=warmup)
        env = scenario()
        radar_pulses = radar_caught = 0
        comm1_on = comm1_caught = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
            if t > warmup:
                if status[5]:
                    radar_pulses += 1
                    if 5 in bands:
                        radar_caught += 1
                if status[1]:
                    comm1_on += 1
                    if 1 in bands:
                        comm1_caught += 1
        radar_pct = radar_caught / radar_pulses if radar_pulses else 0.0
        comm1_pct = comm1_caught / comm1_on if comm1_on else 0.0
        return radar_pct, comm1_pct

    radar_raw: Dict[str, List[float]] = {"BeliefUCB": [], "PRIAware": []}
    comm1_raw: Dict[str, List[float]] = {"BeliefUCB": [], "PRIAware": []}
    for seed in seeds:
        for name, cls in [("BeliefUCB", BeliefUCBScheduler), ("PRIAware", PRIAwareScheduler)]:
            radar_pct, comm1_pct = per_emitter_capture(cls, seed)
            radar_raw[name].append(radar_pct)
            comm1_raw[name].append(comm1_pct)

    print(f"\n[D] Per-emitter capture, k_channels=1, {len(seeds)} seeds, {warmup}-step warmup "
          f"-- the metric that actually matters (blended % hides this)")
    print_summary_table("  Fixed-PRI radar (band 5) capture rate", {n: summarize(v) for n, v in radar_raw.items()})
    print_summary_table("  Comm-1 (band 1) capture rate", {n: summarize(v) for n, v in comm1_raw.items()})
    print_delta("PRIAware vs BeliefUCB on radar capture", paired_delta(radar_raw["PRIAware"], radar_raw["BeliefUCB"]))
    print_delta("PRIAware vs BeliefUCB on comm-1 capture (expected cost)",
                paired_delta(comm1_raw["PRIAware"], comm1_raw["BeliefUCB"]))
    all_raw["per_emitter_radar"] = radar_raw
    all_raw["per_emitter_comm1"] = comm1_raw
    return all_raw


# ----------------------------------------------------------------------
# Suite F: v4 fix validation -- PRIAware (original) vs PersistentPRIAware
# (the fix for the seed-sensitive lock-on bug found in suite D) on the
# same sparse fixed-PRI radar scenario, per-emitter capture only (that's
# the metric the bug actually showed up in).
# ----------------------------------------------------------------------

def suite_f_persistent_fix(seeds: List[int], n_bands: int = 8, n_steps: int = 4000, warmup: int = 800):
    scenario = make_sparse_scenario(n_bands)

    def per_emitter_capture(sched_cls, seed):
        random.seed(seed)
        sched = sched_cls(n_bands, ucb_c=0.5, warmup_steps=warmup)
        env = scenario()
        radar_pulses = radar_caught = 0
        comm1_on = comm1_caught = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
            if t > warmup:
                if status[5]:
                    radar_pulses += 1
                    if 5 in bands:
                        radar_caught += 1
                if status[1]:
                    comm1_on += 1
                    if 1 in bands:
                        comm1_caught += 1
        radar_pct = radar_caught / radar_pulses if radar_pulses else 0.0
        comm1_pct = comm1_caught / comm1_on if comm1_on else 0.0
        return radar_pct, comm1_pct

    radar_raw: Dict[str, List[float]] = {"PRIAware (original)": [], "Persistent (fixed)": []}
    comm1_raw: Dict[str, List[float]] = {"PRIAware (original)": [], "Persistent (fixed)": []}
    for seed in seeds:
        for name, cls in [("PRIAware (original)", PRIAwareScheduler),
                           ("Persistent (fixed)", PersistentPRIAwareScheduler)]:
            radar_pct, comm1_pct = per_emitter_capture(cls, seed)
            radar_raw[name].append(radar_pct)
            comm1_raw[name].append(comm1_pct)

    print(f"\n[F] Fix validation: PRIAware (original) vs Persistent (fixed), "
          f"per-emitter capture, {len(seeds)} seeds, {warmup}-step warmup")
    print_summary_table("  Fixed-PRI radar (band 5) capture rate", {n: summarize(v) for n, v in radar_raw.items()})
    print_summary_table("  Comm-1 (band 1) capture rate", {n: summarize(v) for n, v in comm1_raw.items()})
    orig_locked = sum(1 for v in radar_raw["PRIAware (original)"] if v > 0.5)
    fixed_locked = sum(1 for v in radar_raw["Persistent (fixed)"] if v > 0.5)
    print(f"  Seeds with radar capture > 50%: original {orig_locked}/{len(seeds)}, "
          f"fixed {fixed_locked}/{len(seeds)}")
    return {"radar": radar_raw, "comm1": comm1_raw}


# ----------------------------------------------------------------------
# Suite E: Turing synthetic PDW dataset stand-in (run_on_turing_dataset.py)
# ----------------------------------------------------------------------

def suite_e_turing(seeds: List[int], n_bands: int = 8, dwell_us: float = 200.0):
    builders = {
        "RoundRobin (open-loop)": lambda: RoundRobinScheduler(n_bands),
        "Random (naive)": lambda: RandomScheduler(n_bands),
        "BeliefUCB (Markov+UCB)": lambda: BeliefUCBScheduler(n_bands, ucb_c=0.5),
        "PRIAware (Markov+periodicity)": lambda: PRIAwareScheduler(n_bands, ucb_c=0.5),
    }
    raw: Dict[str, List[float]] = {name: [] for name in builders}
    for seed in seeds:
        # With the synthetic stand-in, each seed also generates a
        # DIFFERENT PDW stream, so this checks robustness to both
        # scenario draw and exploration noise. With --h5 there is one
        # fixed recording, so seeds vary ONLY exploration noise -- a
        # weaker claim, which is why source.seed_semantics is printed
        # and written into the CSV rather than left implicit.
        pdw = _src().for_seed(seed)

        def env_factory(pdw=pdw):
            return PDWReplayEnvironment(pdw, n_bands=n_bands, dwell_us=dwell_us,
                                         freq_range_mhz=_src().freq_range_mhz,
                                         t0_us=_src().t0_us)

        n_steps = env_factory().n_steps
        random.seed(seed)
        for name, build in builders.items():
            stats = run_episode(env_factory, build(), n_steps, n_bands, k_channels=1)
            raw[name].append(stats.report()["interception_ratio"])

    label = (f"real TSRD data ({_src().provenance})" if _src().kind == "h5"
              else "synthetic PDW stand-in")
    seed_note = ("scheduler randomness only -- one fixed recording" if _src().kind == "h5"
                 else "each seed = a different synthetic pulse stream")
    print_summary_table(
        f"[E] Turing {label}, k_channels=1, dwell={dwell_us}us, "
        f"{len(seeds)} seeds ({seed_note})",
        {n: summarize(v) for n, v in raw.items()})
    print_delta("BeliefUCB vs RoundRobin",
                paired_delta(raw["BeliefUCB (Markov+UCB)"], raw["RoundRobin (open-loop)"]))
    print_delta("PRIAware vs BeliefUCB",
                paired_delta(raw["PRIAware (Markov+periodicity)"], raw["BeliefUCB (Markov+UCB)"]))
    return raw


# ----------------------------------------------------------------------
# Suite G: ScanAwarePRIScheduler on the spatially-scanning radar, mixed
# competitive scenario (scan_aware_scheduler.py / validate_scan_aware_mixed.py).
# Tests both the headline metrics (overall + radar-band capture vs
# PRIAware/BeliefUCB/RoundRobin) AND, explicitly, whether the lock-
# stability fixes actually hold up on seeds beyond the 10 checked by
# hand during debugging -- that's the whole point of a broader sweep:
# every prior "bad lock" (seeds 1, 5, then 7) was found by manually
# instrumenting ONE seed at a time, which doesn't prove there isn't an
# 8th still out there. This suite checks the scheduler's own internal
# state (scan_period_estimate, beam_dwell_estimate) against known
# ground truth on every seed, not just the headline interception numbers.
# ----------------------------------------------------------------------

TRUE_SCAN_PERIOD = 40.0
TRUE_BEAM_DWELL = 6
RADAR_BAND = 5


def _scan_aware_mixed_scenario(n_bands=8):
    def scenario():
        inner = SparsePeriodicEmitter("fixed-pri-radar", band=RADAR_BAND, pri=3)
        scanning_radar = SpatiallyScanningEmitter(
            inner, scan_period_steps=int(TRUE_SCAN_PERIOD), beam_dwell_steps=TRUE_BEAM_DWELL,
            sidelobe_leak_prob=0.02)
        emitters = [
            MarkovEmitter("comm-1", band=1, p_on_given_off=0.08, p_on_given_on=0.85),
            MarkovEmitter("comm-2", band=4, p_on_given_off=0.10, p_on_given_on=0.75),
            scanning_radar,
            AgileEmitter("agile-1", bands=[0, 3], dwell=2, duty=0.4),
            AgileEmitter("agile-2", bands=[6, 7], dwell=3, duty=0.4),
        ]
        return Environment(n_bands=n_bands, emitters=emitters)
    return scenario


def suite_g_scan_aware(seeds: List[int], n_bands: int = 8, n_steps: int = 8000):
    scenario = _scan_aware_mixed_scenario(n_bands)
    priority = [1.0] * n_bands
    priority[RADAR_BAND] = 4.0

    builders = {
        "RoundRobin (open-loop)": lambda: RoundRobinScheduler(n_bands),
        "BeliefUCB (no periodicity)": lambda: BeliefUCBScheduler(n_bands, ucb_c=0.5, priority=priority),
        "PRIAware (single-periodicity)": lambda: PRIAwareScheduler(n_bands, ucb_c=0.5, priority=priority),
        "ScanAwarePRIScheduler (two-tier)": lambda: ScanAwarePRIScheduler(n_bands, ucb_c=0.5, priority=priority),
    }

    def run_one(build, seed):
        """Runs one episode and, for ScanAwarePRIScheduler specifically,
        also reads back its internal lock state at the end -- the
        cheapest possible check for a repeat of the bad-lock failure
        mode without re-instrumenting every seed by hand."""
        random.seed(seed)
        env = scenario()
        sched = build()
        radar_pulses = radar_caught = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
            if status[RADAR_BAND]:
                radar_pulses += 1
                if RADAR_BAND in bands:
                    radar_caught += 1
        overall = None  # computed separately via run_episode below for parity with other suites
        radar_pct = radar_caught / radar_pulses if radar_pulses else 0.0

        lock_info = None
        if isinstance(sched, ScanAwarePRIScheduler):
            period = sched.scan_period_estimate[RADAR_BAND]
            dwell = sched.beam_dwell_estimate[RADAR_BAND]
            conf = sched.scan_confidence[RADAR_BAND]
            period_off = (abs(period - TRUE_SCAN_PERIOD) / TRUE_SCAN_PERIOD
                          if period else None)
            # Only flag a lock as "bad" if it's actually LIVE (non-zero
            # confidence, i.e. currently trusted and feeding
            # choose_bands' periodicity score) -- found directly (seed
            # 11): a wrong candidate can get published transiently at
            # cold start, self-correct one call later via the same
            # stability gate, and leave scan_confidence at 0.0
            # afterward. That stale-but-inert state isn't a live bug
            # (_periodicity_score already gates on scan_conf <= 0), so
            # checking period_est alone without the confidence gate
            # produces a false positive.
            bad_lock = (conf > 0 and (period is None or period_off is None
                        or period_off > 0.10 or dwell > 3 * TRUE_BEAM_DWELL))
            lock_info = dict(period=period, dwell=dwell, period_off=period_off,
                              conf=conf, bad_lock=bad_lock)
        return radar_pct, lock_info

    radar_raw: Dict[str, List[float]] = {name: [] for name in builders}
    overall_raw: Dict[str, List[float]] = {name: [] for name in builders}
    lock_flags: List[Dict] = []

    for seed in seeds:
        for name, build in builders.items():
            random.seed(seed)
            stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=1)
            overall_raw[name].append(stats.report()["interception_ratio"])
        for name, build in builders.items():
            radar_pct, lock_info = run_one(build, seed)
            radar_raw[name].append(radar_pct)
            if lock_info is not None:
                lock_flags.append(dict(seed=seed, **lock_info))

    print(f"\n[G] ScanAwarePRIScheduler, spatially-scanning radar in mixed traffic, "
          f"{len(seeds)} seeds ({n_steps} steps each, radar priority weight={priority[RADAR_BAND]})")
    print_summary_table("  Overall interception", {n: summarize(v) for n, v in overall_raw.items()})
    print_summary_table("  Radar-band (band 5) capture rate", {n: summarize(v) for n, v in radar_raw.items()})
    print_delta("ScanAware vs PRIAware on radar capture",
                paired_delta(radar_raw["ScanAwarePRIScheduler (two-tier)"], radar_raw["PRIAware (single-periodicity)"]))
    print_delta("ScanAware vs PRIAware on overall interception (the cost)",
                paired_delta(overall_raw["ScanAwarePRIScheduler (two-tier)"], overall_raw["PRIAware (single-periodicity)"]))

    n_bad = sum(1 for f in lock_flags if f["bad_lock"])
    print(f"\n  Lock-sanity check (scan_period_estimate within 10% of true {TRUE_SCAN_PERIOD:.0f}, "
          f"beam_dwell_estimate <= {3*TRUE_BEAM_DWELL}): {len(lock_flags) - n_bad}/{len(lock_flags)} seeds clean")
    if n_bad:
        print("  Seeds with a bad lock:")
        for f in lock_flags:
            if f["bad_lock"]:
                print(f"    seed={f['seed']}: period_est={f['period']} "
                      f"(off by {f['period_off']*100 if f['period_off'] is not None else float('nan'):.0f}%), "
                      f"beam_dwell_est={f['dwell']}, scan_conf={f['conf']:.2f}")
    else:
        print("  No bad locks found in this sweep.")

    return dict(overall=overall_raw, radar=radar_raw, lock_flags=lock_flags)




def write_csv(path: str, suite_label: str, raw: Dict[str, List[float]], seeds: List[int],
              provenance: str = "synthetic", seed_semantics: str = None):
    """Append one suite's results to the shared CSV.

    provenance/seed_semantics default to the synthetic stand-in's own
    values -- correct for every suite EXCEPT E, which is the only one
    that reads from `_src()` and can be a real .h5. Earlier this
    function always stamped `_src().provenance`/`_src().seed_semantics`
    on every row regardless of suite, so a run with --h5 mislabelled
    suites A-D/F/G (which never touch _src(), they're hardcoded
    synthetic scenarios) as if they'd come from the real file. Caught
    by inspecting an interrupted run's partial CSV directly.
    """
    import csv
    import os
    if seed_semantics is None:
        seed_semantics = ("environment+scheduler (each seed is a different environment)"
                          if provenance == "synthetic" else seed_semantics)
    write_header = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["data_source", "seed_semantics", "suite", "scheduler",
                       "seed", "interception_ratio"])
        for name, vals in raw.items():
            for seed, v in zip(seeds, vals):
                w.writerow([provenance, seed_semantics, suite_label, name, seed, v])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=10, help="Number of seeds to run")
    ap.add_argument("--seed-start", type=int, default=1, help="First seed value (seeds are consecutive integers)")
    ap.add_argument("--csv", default="multi_seed_results.csv", help="Path to write raw per-seed CSV")
    ap.add_argument("--h5", default=None,
                     help="Point suite E (the PDW replay suite) at a real TSRD .h5. Suites "
                          "A-D and F-G are controlled synthetic scenarios with declared "
                          "ground truth and are deliberately left alone -- an arbitrary .h5 "
                          "does not have a beacon on band 5 with a 12-step period, so "
                          "feeding one in would not validate them, it would just silently "
                          "change what they measure. Load failure is fatal.")
    add_window_args(ap)
    args = ap.parse_args()

    global SOURCE
    try:
        SOURCE = PDWSource(h5_path=args.h5, n_bands=8, window_s=window_from_args(args))
    except PDWSourceError as exc:
        raise SystemExit(f"FATAL: {exc}")
    if args.h5:
        print(SOURCE.banner(8, 20.0) + "\n")
        print("NOTE: --h5 affects suite E only; A-D and F-G remain synthetic by design.\n")

    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    print(f"Running every comparison across {len(seeds)} seeds: {seeds}\n")
    print("=" * 100)

    import os
    if os.path.exists(args.csv):
        os.remove(args.csv)

    raw_a = suite_a_prototype(seeds)
    write_csv(args.csv, "A_prototype", raw_a, seeds)
    print("\n" + "=" * 100)

    raw_b = suite_b_multichannel(seeds)
    for k, raw in raw_b.items():
        write_csv(args.csv, f"B_multichannel_k{k}", raw, seeds)
    print("\n" + "=" * 100)

    raw_c = suite_c_beacon(seeds)
    for k, raw in raw_c.items():
        write_csv(args.csv, f"C_beacon_k{k}", raw, seeds)
    print("\n" + "=" * 100)

    raw_d = suite_d_sparse(seeds)
    for k, raw in raw_d.items():
        write_csv(args.csv, f"D_sparse_k{k}" if isinstance(k, int) else f"D_{k}", raw, seeds)
    print("\n" + "=" * 100)

    raw_e = suite_e_turing(seeds)
    write_csv(args.csv, "E_turing_pdw", raw_e, seeds,
              provenance=_src().provenance, seed_semantics=_src().seed_semantics)
    print("\n" + "=" * 100)

    raw_f = suite_f_persistent_fix(seeds)
    write_csv(args.csv, "F_fix_radar_capture", raw_f["radar"], seeds)
    write_csv(args.csv, "F_fix_comm1_capture", raw_f["comm1"], seeds)
    print("\n" + "=" * 100)

    raw_g = suite_g_scan_aware(seeds)
    write_csv(args.csv, "G_scan_aware_overall", raw_g["overall"], seeds)
    write_csv(args.csv, "G_scan_aware_radar_capture", raw_g["radar"], seeds)
    print("\n" + "=" * 100)

    print(f"\nRaw per-seed results written to {args.csv}")
    print("\nBOTTOM LINE: every 'X beats Y' delta above reports how many of the "
          f"{len(seeds)} seeds the win held in. A delta whose mean is well clear of "
          "0 relative to its stdev, and that wins in most/all seeds, is a robust "
          "effect rather than a seed-lottery artifact.")


if __name__ == "__main__":
    main()
