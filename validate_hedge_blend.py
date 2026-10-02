"""
validate_hedge_blend.py
========================
First-pass sanity check for HedgeBlendedPRIAwareScheduler (v5) against
the four reference points established for this project, single seed
each as scoped -- not yet the full multi-seed harness. Only escalates
to multi-seed once this isn't obviously broken.

References:
  1. Sparse-radar headline (synthetic) -- PRIAware's flagship result
     (100.0% radar / 79.0% comm-1 at warmup=800). This is the invariant
     that has never survived a low max_blend_confidence cap; the whole
     point of v5 is to see if a LEARNED weight does better than either
     extreme.
  2. Beacon scenario (synthetic), k=1 and k=2 -- where max_blend_confidence
     and the harmonic-selection fix both showed real, opposite-direction
     costs. A belief-biased Hedge weight should, in principle, cost less
     here than a fixed eager cap.
  3. Synthetic PDW stand-in, band 4 fractional-PRI (~32.5 steps) -- the
     case max_blend_confidence=1.0 was originally added FOR.
  4. Real config_169.h5, band 1 (staggered PRI, 97.8% of the file's
     pulses) -- where the regression was actually found. BeliefUCB gets
     99.7% here; PRIAware(cap=1.0) gets 69.7%; PRIAware(cap=0.1) gets
     98.6% but costs the sparse-radar headline per the earlier sweep.
     This is the case v5 exists to fix WITHOUT a global cap trade-off.

Run:  python3 validate_hedge_blend.py
"""

import sys
import random
import statistics

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
from scan_scheduler_prototype import make_scenario
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler
from pdw_source import PDWSource
from pdw_environment import PDWReplayEnvironment

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
    return f"{100.0 * a / b:5.1f}%" if b else "  n/a"


# ---------------------------------------------------------------------
# Reference 1: sparse-radar headline (per-emitter capture)
# ---------------------------------------------------------------------
def ref1_sparse_radar():
    print("=== Reference 1: sparse-radar headline (synthetic, seed=11, warmup=800) ===")
    n_steps = 4000
    warmup = 800
    scenario = make_sparse_scenario(N_BANDS)

    def per_emitter_capture(sched_cls, **kw):
        random.seed(11)
        sched = sched_cls(N_BANDS, ucb_c=0.5, warmup_steps=warmup, **kw)
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
        return radar_pulses, radar_caught, comm1_on, comm1_caught

    for name, cls, kw in [
        ("BeliefUCB (baseline)", BeliefUCBScheduler, {}),
        ("PRIAware (v3, cap=1.0)", PRIAwareScheduler, {}),
        ("HedgeBlended (v5, default)", HedgeBlendedPRIAwareScheduler, {}),
    ]:
        rp, rc, cp, cc = per_emitter_capture(cls, **kw)
        print(f"  {name:30s}: radar {pct(rc, rp)} ({rc}/{rp})   comm-1 {pct(cc, cp)} ({cc}/{cp})")
    print()


# ---------------------------------------------------------------------
# Reference 2: beacon scenario, k=1 and k=2
# ---------------------------------------------------------------------
def ref2_beacon():
    print("=== Reference 2: beacon scenario (synthetic, seed=7), k=1 and k=2 ===")
    n_steps = 4000
    scenario = make_scenario(N_BANDS)

    for k in (1, 2):
        print(f"  --- k={k} ---")
        for name, cls, kw in [
            ("BeliefUCB (baseline)", BeliefUCBScheduler, {"ucb_c": 0.5}),
            ("PRIAware (v3, cap=1.0)", PRIAwareScheduler, {"ucb_c": 0.5}),
            ("HedgeBlended (v5, default)", HedgeBlendedPRIAwareScheduler, {"ucb_c": 0.5}),
        ]:
            random.seed(7)
            sched = cls(N_BANDS, **kw)
            stats = run_episode(scenario, sched, n_steps, N_BANDS, k_channels=k)
            r = stats.report()
            print(f"    {name:30s}: {r['interception_ratio']*100:5.1f}%")
    print()


# ---------------------------------------------------------------------
# Reference 3: synthetic PDW stand-in, band 4 fractional-PRI
# ---------------------------------------------------------------------
def ref3_synthetic_pdw():
    print("=== Reference 3: synthetic PDW stand-in, band 4 fractional-PRI (~32.5 steps) ===")
    dwell_us = 20.0
    warmup = 800
    source = PDWSource(h5_path=None, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(1)

    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=dwell_us,
                                     freq_range_mhz=source.freq_range_mhz,
                                     t0_us=source.t0_us)
    probe = env_factory()
    n_steps = probe.n_steps

    for name, cls, kw in [
        ("BeliefUCB (baseline)", BeliefUCBScheduler, {"ucb_c": 0.5, "warmup_steps": warmup}),
        ("PRIAware (v3, cap=1.0)", PRIAwareScheduler, {"ucb_c": 0.5, "warmup_steps": warmup}),
        ("HedgeBlended (v5, default)", HedgeBlendedPRIAwareScheduler,
         {"ucb_c": 0.5, "warmup_steps": warmup}),
    ]:
        env = env_factory()
        random.seed(1)
        sched = cls(N_BANDS, **kw)
        hits = on = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                obs = status[b]
                sched.update(b, obs)
                if obs:
                    hits += 1
            if status[4]:
                on += 1
        pri = getattr(sched, "pri_estimate", [None] * N_BANDS)[4]
        conf = getattr(sched, "confidence", [0.0] * N_BANDS)[4]
        print(f"  {name:30s}: overall {pct(hits, on)}   band4 PRI={pri}  conf={conf if isinstance(conf, str) else round(conf, 2)}")
    print()


# ---------------------------------------------------------------------
# Reference 4: real config_169.h5, band 1
# ---------------------------------------------------------------------
def ref4_real_file():
    print("=== Reference 4: real config_169.h5, band 1 (97.8% of the file's pulses) ===")
    dwell_us = 20.0
    source = PDWSource(h5_path=H5, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(0)

    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=dwell_us,
                                     freq_range_mhz=source.freq_range_mhz,
                                     t0_us=source.t0_us)
    probe = env_factory()
    n_steps = probe.n_steps

    for name, cls, kw in [
        ("BeliefUCB (baseline)", BeliefUCBScheduler, {"ucb_c": 0.5, "warmup_steps": 0}),
        ("PRIAware (v3, cap=1.0)", PRIAwareScheduler, {"ucb_c": 0.5, "warmup_steps": 0}),
        ("HedgeBlended (v5, default)", HedgeBlendedPRIAwareScheduler,
         {"ucb_c": 0.5, "warmup_steps": 0}),
    ]:
        env = env_factory()
        random.seed(1)
        sched = cls(N_BANDS, **kw)
        band1_hits = band1_on = total_hits = total_on = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                obs = status[b]
                sched.update(b, obs)
                if obs:
                    total_hits += 1
            if status[1]:
                band1_on += 1
                if 1 in bands:
                    band1_hits += 1
            for b in range(N_BANDS):
                if status[b]:
                    total_on += 1
        w_belief_1 = getattr(sched, "w_belief", [None] * N_BANDS)[1]
        w_pri_1 = getattr(sched, "w_pri", [None] * N_BANDS)[1]
        extra = f"  w_belief[1]={w_belief_1}, w_pri[1]={w_pri_1}" if w_belief_1 is not None else ""
        print(f"  {name:30s}: overall {pct(total_hits, total_on)}   band1 {pct(band1_hits, band1_on)}{extra}")
    print()


if __name__ == "__main__":
    ref1_sparse_radar()
    ref2_beacon()
    ref3_synthetic_pdw()
    ref4_real_file()
