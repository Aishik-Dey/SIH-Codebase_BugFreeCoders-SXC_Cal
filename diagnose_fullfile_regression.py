"""
diagnose_fullfile_regression.py
================================
Diagnoses the full-config_169.h5 gap found by run_on_turing_dataset.py:
BeliefUCB 97.1% vs PRIAware/PersistentPRIAware both 67.7% -- identical
to each other, both far below plain belief. Band 1 (staggered PRI,
700us) is 6521/6668 = 97.8% of all pulses in this file, so the overall
interception number is almost entirely a band-1 story; band 0 (fixed
PRI, 1693.24us) is the only other periodic band and has just 94 pulses.

This script:
  1. Reproduces the default run's per-band capture (not just the
     blended aggregate) for BeliefUCB vs PRIAware vs PersistentPRIAware,
     to confirm band 1 is where the gap lives and quantify it exactly.
  2. Checks whether PersistentPRIAware's characterization bonus is
     doing ANYTHING on this file (identical 67.7% for both schedulers
     is suspicious -- could mean the bonus never fires here).
  3. Sweeps --max-blend-confidence at FULL-FILE scale (previously only
     characterized on the isolated band-1 window in an earlier session)
     to see whether the documented Pareto trade-off (cap<=0.8 helps but
     costs the sparse-radar headline; cap=0.9 preserves headline but
     doesn't help) reproduces here, or whether full-file dynamics differ.
"""
import sys
import statistics
from typing import Dict

from scan_scheduler_v2 import BeliefUCBScheduler, RoundRobinScheduler
from scan_scheduler_v3_pri import PRIAwareScheduler
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
from pdw_environment import PDWReplayEnvironment
from pdw_source import PDWSource

def _h5_arg(default="config_169.h5"):
    """--h5 PATH / --h5=PATH override (so run_all.py can point this at the
    real dataset's actual location instead of a flattened bare filename)."""
    argv = sys.argv
    for i, tok in enumerate(argv):
        if tok == "--h5" and i + 1 < len(argv):
            return argv[i + 1]
        if tok.startswith("--h5="):
            return tok[len("--h5="):]
    return default


H5 = _h5_arg()
N_BANDS = 36
DWELL_US = 20.0


def build_env():
    source = PDWSource(h5_path=H5, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(0)
    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=DWELL_US,
                                     freq_range_mhz=source.freq_range_mhz,
                                     t0_us=source.t0_us)
    probe = env_factory()
    return env_factory, probe.n_steps


def run_with_per_band_tracking(env_factory, scheduler, n_steps, k_channels=1):
    """Mirrors run_episode's loop (switch_cost_steps=0 path) but records
    per-band hit/transmission counts and, for band 1 specifically, a
    confidence trajectory sampled every 20000 steps."""
    env = env_factory()
    band_hits = [0] * N_BANDS
    band_on = [0] * N_BANDS
    on_since = [None] * N_BANDS
    credited = [False] * N_BANDS
    total_hits = 0
    total_on = 0
    band1_conf_trace = []

    for t in range(n_steps):
        status: Dict[int, bool] = env.step()
        for b in range(N_BANDS):
            if status[b]:
                band_on[b] += 1
                total_on += 1
                if on_since[b] is None:
                    on_since[b] = t
                    credited[b] = False
            else:
                on_since[b] = None
                credited[b] = False

        bands = scheduler.choose_bands(k_channels)
        for band in bands:
            observed_on = status[band]
            if observed_on:
                band_hits[band] += 1
                total_hits += 1
            scheduler.update(band, observed_on)

        if t % 20000 == 0 and hasattr(scheduler, "confidence"):
            band1_conf_trace.append((t, round(scheduler.confidence[1], 3)))

    return {
        "band_hits": band_hits,
        "band_on": band_on,
        "total_hits": total_hits,
        "total_on": total_on,
        "band1_conf_trace": band1_conf_trace,
    }


def pct(a, b):
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


def main():
    env_factory, n_steps = build_env()
    print(f"n_steps={n_steps}\n")

    schedulers = {
        "BeliefUCB": BeliefUCBScheduler(N_BANDS, ucb_c=0.5, warmup_steps=0),
        "PRIAware (default, cap=1.0)": PRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=0),
        "PersistentPRIAware (default, cap=1.0)": PersistentPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=0),
    }

    results = {}
    for name, sched in schedulers.items():
        r = run_with_per_band_tracking(env_factory, sched, n_steps)
        results[name] = r
        print(f"=== {name} ===")
        print(f"  overall: {pct(r['total_hits'], r['total_on'])} ({r['total_hits']}/{r['total_on']})")
        print(f"  band 0 (fixed PRI, 94 pulses total):    {pct(r['band_hits'][0], r['band_on'][0])} ({r['band_hits'][0]}/{r['band_on'][0]})")
        print(f"  band 1 (staggered PRI, 6521 pulses):    {pct(r['band_hits'][1], r['band_on'][1])} ({r['band_hits'][1]}/{r['band_on'][1]})")
        other_hits = sum(r['band_hits'][2:])
        other_on = sum(r['band_on'][2:])
        print(f"  bands 2-7 (agile/dead):                 {pct(other_hits, other_on)} ({other_hits}/{other_on})")
        if r["band1_conf_trace"]:
            print(f"  band-1 confidence trajectory (every 20000 steps): {r['band1_conf_trace'][:6]} ... {r['band1_conf_trace'][-3:]}")
        print()

    # --- Check #2: is v3 vs v4 actually identical, or coincidentally close? ---
    v3 = results["PRIAware (default, cap=1.0)"]
    v4 = results["PersistentPRIAware (default, cap=1.0)"]
    identical = (v3["band_hits"] == v4["band_hits"])
    print(f"v3 vs v4 per-band hits IDENTICAL: {identical}")
    if not identical:
        print(f"  v3 band_hits: {v3['band_hits']}")
        print(f"  v4 band_hits: {v4['band_hits']}")
    print()

    # --- Check #3: max_blend_confidence sweep at full-file scale ---
    print("=== max_blend_confidence sweep (PersistentPRIAware, full file) ===")
    for cap in [1.0, 0.9, 0.8, 0.5, 0.3, 0.1]:
        sched = PersistentPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=0,
                                             max_blend_confidence=cap)
        r = run_with_per_band_tracking(env_factory, sched, n_steps)
        print(f"  cap={cap:>4}: overall={pct(r['total_hits'], r['total_on'])}  "
              f"band0={pct(r['band_hits'][0], r['band_on'][0])}  "
              f"band1={pct(r['band_hits'][1], r['band_on'][1])}")


if __name__ == "__main__":
    main()
