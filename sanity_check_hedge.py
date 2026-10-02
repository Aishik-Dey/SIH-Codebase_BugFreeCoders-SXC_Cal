"""
sanity_check_hedge.py
======================
First-pass, single-seed check of HedgeBlendedPRIAwareScheduler against
all four established reference points, before investing in multi-seed
validation. Not a substitute for that validation -- a gate: if this
doesn't at least look directionally sane, multi-seeding it is wasted
effort.

  1. Sparse-radar headline (synthetic) -- reference: PRIAware 100.0%
     radar / 79.0-79.4% comm-1.
  2. Beacon scenario (synthetic), k=1 and k=2 -- reference: PRIAware
     roughly neutral to slightly negative vs BeliefUCB (documented
     Pareto trade-off, not expected to fully vanish here).
  3. Synthetic PDW stand-in, band 4 fractional-PRI -- reference:
     PRIAware recovers ~32.5 scan-steps at confidence ~0.89.
  4. Real config_169.h5, band 1 -- reference: BeliefUCB 99.7%,
     PRIAware/PersistentPRIAware 69.7% (the regression this class
     exists to close).
"""
import sys
import random

from scan_scheduler_v2 import RoundRobinScheduler, BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
from scan_scheduler_prototype import make_scenario
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler
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


def pct(a, b):
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


# --- 1: sparse-radar per-emitter headline ---------------------------------
def check_sparse_radar():
    print("=== 1. Sparse-radar headline (synthetic) ===")
    n_steps, warmup = 4000, 800
    scenario = make_sparse_scenario(N_BANDS)

    def per_emitter(cls):
        random.seed(11)
        sched = cls(N_BANDS, ucb_c=0.5, warmup_steps=warmup)
        env = scenario()
        rp = rc = cp = cc = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
            if t > warmup:
                if status[5]:
                    rp += 1
                    if 5 in bands:
                        rc += 1
                if status[1]:
                    cp += 1
                    if 1 in bands:
                        cc += 1
        return rp, rc, cp, cc

    for name, cls in [("PRIAware", PRIAwareScheduler), ("HedgeBlended", HedgeBlendedPRIAwareScheduler)]:
        rp, rc, cp, cc = per_emitter(cls)
        print(f"  {name:14s}: radar {pct(rc, rp)} ({rc}/{rp})   comm-1 {pct(cc, cp)} ({cc}/{cp})")
    print()


# --- 2: beacon scenario -----------------------------------------------------
def check_beacon():
    print("=== 2. Beacon scenario (synthetic) ===")
    n_steps = 4000
    scenario = make_scenario(N_BANDS)
    for k in (1, 2):
        random.seed(7)
        results = {}
        for name, cls in [("BeliefUCB", lambda: BeliefUCBScheduler(N_BANDS, ucb_c=0.5)),
                           ("PRIAware", lambda: PRIAwareScheduler(N_BANDS, ucb_c=0.5)),
                           ("HedgeBlended", lambda: HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5))]:
            random.seed(7)
            stats = run_episode(scenario, cls(), n_steps, N_BANDS, k_channels=k)
            results[name] = stats.report()["interception_ratio"]
        print(f"  k={k}: " + "   ".join(f"{n}={v*100:.1f}%" for n, v in results.items()))
    print()


# --- 3: synthetic PDW stand-in, band 4 --------------------------------------
def check_synthetic_pdw():
    print("=== 3. Synthetic PDW stand-in, band 4 ===")
    dwell_us = 20.0
    n_steps_cap = 40000
    for name, cls in [("PRIAware", PRIAwareScheduler), ("HedgeBlended", HedgeBlendedPRIAwareScheduler)]:
        random.seed(0)
        source = PDWSource(h5_path=None, n_bands=N_BANDS, window_s=None)
        pdw = source.for_seed(0)
        env = PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=dwell_us,
                                   freq_range_mhz=source.freq_range_mhz,
                                   t0_us=source.t0_us)
        sched = cls(N_BANDS, ucb_c=0.5, warmup_steps=800)
        n_steps = min(env.n_steps, n_steps_cap)
        hits = total = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
                if status[b]:
                    hits += 1
            total += sum(1 for v in status.values() if v)
        pri = sched.pri_estimate[4]
        conf = sched.confidence[4]
        print(f"  {name:14s}: overall {pct(hits, total)}   band4 PRI={pri}  conf={conf:.2f}")
    print()


# --- 4: real config_169.h5, band 1 -----------------------------------------
def check_real_band1():
    print("=== 4. Real config_169.h5, band 1 (the actual regression) ===")
    try:
        source = PDWSource(h5_path=H5, n_bands=N_BANDS, window_s=None)
    except Exception as exc:
        # An explicit --h5 that can't be loaded is fatal (same rule as
        # the rest of the real-data scripts: no silent fallback, and no
        # exit-0 that lets run_all.py report [OK] for a check that never
        # ran). Only the bare no-argument default may still skip.
        if any(t == "--h5" or t.startswith("--h5=") for t in sys.argv[1:]):
            print(f"  FATAL -- could not load --h5 file {H5!r}: {exc}")
            sys.exit(1)
        print(f"  SKIPPED -- config_169.h5 not available here ({exc})")
        print()
        return
    pdw = source.for_seed(0)

    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=20.0,
                                     freq_range_mhz=source.freq_range_mhz,
                                     t0_us=source.t0_us)
    probe = env_factory()
    n_steps = probe.n_steps

    for name, cls in [("BeliefUCB", BeliefUCBScheduler),
                       ("PRIAware", PRIAwareScheduler),
                       ("HedgeBlended", HedgeBlendedPRIAwareScheduler)]:
        sched = cls(N_BANDS, ucb_c=0.5, warmup_steps=0)
        env = env_factory()
        b1_on = b1_hit = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
                if b == 1 and status[1]:
                    b1_hit += 1
            if status[1]:
                b1_on += 1
        extra = ""
        if hasattr(sched, "w_belief"):
            extra = f"  [w_belief={sched.w_belief[1]:.2f} w_pri={sched.w_pri[1]:.2f}]"
        print(f"  {name:14s}: band1 {pct(b1_hit, b1_on)} ({b1_hit}/{b1_on}){extra}")
    print()


if __name__ == "__main__":
    check_sparse_radar()
    check_beacon()
    check_synthetic_pdw()
    check_real_band1()
