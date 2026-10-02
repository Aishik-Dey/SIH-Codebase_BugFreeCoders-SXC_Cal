"""
run_real_data.py
================
Runs EVERY scheduling algorithm in this project against real TSRD
test/validation .h5 files -- and ONLY real files. No synthetic scenario,
no synthetic PDW stand-in, nothing else is ever run from here.

Edit the CONFIG block below (mainly the H5_FILES list), then:

    python run_real_data.py

Files are processed one after the other, in list order. A file that is
missing or fails to load is recorded as FAILED and the run moves on to the
next one -- it is never replaced by synthetic data (the run ends with exit
code 1 if anything failed, so a failure can't pass unnoticed).

What runs on each file
----------------------
  Schedulers : RoundRobin, Random, BeliefUCB, PRIAware, PersistentPRIAware,
               ScanAwarePRI, HedgeBlended, WhittleIndex (each toggleable)
  Ceiling    : genie ORACLE (perfect knowledge of which bands are ON this
               step; still capped at k catches per step)
  Extras     : per-band capture table, PRI-lock diagnostics against the
               file's own metadata truth, and (optional) HDBSCAN
               deinterleaving V-measure on the full stream and on the pulses
               HedgeBlended actually intercepted.

Outputs (in real_results/<timestamp>/):
  report.txt   everything printed to the console
  summary.csv  one row per (file, algorithm, seed)
  per_band.csv one row per (file, algorithm, seed, band)

READ THIS BEFORE QUOTING NUMBERS
--------------------------------
* A "scan"-mode file was recorded by a receiver that was itself sweeping,
  so it is the OUTPUT of an open-loop scanner. Interception on it means
  "re-capture efficiency on a pre-filtered stream", not interception of what
  the emitters really transmitted. Each file's banner says which kind it is.
  A "stare"-mode file is the honest scoring case.
* One real file is one fixed recording: SEEDS only vary the SCHEDULERS' own
  randomness (warm-up order etc.), never the environment.
* Overall interception is dominated by whichever band has the most pulses.
  Always look at the per-band table too.
* ScanAwarePRI has never been validated on real data, and WhittleIndex was
  ~200 s per run on the 6.6k-pulse config_169.h5. Long stare files can take
  far longer -- use WINDOWS / MAX_STEPS, or switch Whittle off.
"""

import csv
import datetime
import random
import statistics
import sys
import time
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scan_scheduler_v2 import (RoundRobinScheduler, RandomScheduler,
                               BeliefUCBScheduler, run_episode)
from scan_scheduler_v3_pri import PRIAwareScheduler
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
from scan_aware_scheduler import ScanAwarePRIScheduler
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler
from scan_scheduler_whittle import WhittleIndexScheduler
from pdw_environment import PDWReplayEnvironment
from pdw_source import PDWSource, suggest_windows


# =============================================================================
# CONFIG -- edit this block
# =============================================================================

# Real TSRD test/validation files, run in this order. Relative paths are
# looked up against the current directory first, then this script's folder.
H5_FILES = [
    # "Datasets/Turing datasets/Validation/config_169.h5",
    "Datasets/Turing datasets/Validation/config_57.h5",
    # "Datasets/Turing datasets/Validation/config_1.h5",
    # "Datasets/Turing datasets/Test/config_169.h5",
    # "Datasets/Turing datasets/Test/config_57.h5",
    # "Datasets/Turing datasets/Test/config_1.h5",
]

# Optional per-file sub-window (start_s, duration_s), keyed by the EXACT
# string used in H5_FILES. Recommended for long stare-mode files: it keeps
# the fine dwell without a ~10^6-step episode. Each file's run prints
# suggested windows (SHOW_WINDOW_SUGGESTIONS) that you can paste in here.
WINDOWS = {
    # "Datasets/Turing datasets/Test/config_YYY.h5": (2.5, 0.25),
}

# --- receiver / replay ------------------------------------------------------
N_BANDS = 36
DWELL_US = 20.0         # PRI-resolving dwell used throughout this project
K_VALUES = [1, 2, 4]     # channel counts to run, iteratively, on every file
MAX_STEPS = 0           # 0 = replay the whole (windowed) file; else cap the steps
SEEDS = [0]             # scheduler-side randomness only (see docstring)
SWITCH_COST_STEPS = 0   # 0 = free switching. > 0 has never been validated on real data.

# --- scheduler settings (defaults match run_on_turing_dataset.py) ------------
WARMUP_STEPS = 0
UCB_C = 0.5
CONFIDENCE_SCALE = 0.25
MIN_CYCLES = 4
MAX_BLEND_CONFIDENCE = 1.0
ETA = 4.0                   # HedgeBlended
CLASS_BALANCE_ALPHA = 0.1   # HedgeBlended
SWITCH_LEAD_STEPS = 0
WARMUP_DWELL_STEPS = 1
WARMUP_DWELL_JITTER = 1

# Which algorithms to run (order = run order; slowest last).
ALGORITHMS = {
    "RoundRobin": True,
    "Random": True,
    "BeliefUCB": True,
    "PRIAware": True,
    "PersistentPRIAware": True,
    "ScanAwarePRI": True,
    "HedgeBlended": True,
    "WhittleIndex": True,   # slow: ~200 s on config_169.h5
}

RUN_ORACLE = True

# --- extras -----------------------------------------------------------------
RUN_DEINTERLEAVE = True             # HDBSCAN V-measure (needs scikit-learn >= 1.3)
DEINTERLEAVE_SCHEDULER = "HedgeBlended"   # whose intercepted pulses get clustered
DEINTERLEAVE_MAX_PULSES = 300_000   # skip clustering above this (use WINDOWS)
SHOW_WINDOW_SUGGESTIONS = True
OUTPUT_DIR = "real_results"

# =============================================================================
# end of CONFIG
# =============================================================================


PRI_FAMILY = ("PRIAware", "PersistentPRIAware", "ScanAwarePRI", "HedgeBlended")


def build_scheduler(name):
    """A fresh scheduler instance. Same constructor arguments as the real-data
    driver (run_on_turing_dataset.py)."""
    common = dict(ucb_c=UCB_C, warmup_steps=WARMUP_STEPS,
                  warmup_dwell_steps=WARMUP_DWELL_STEPS,
                  warmup_dwell_jitter=WARMUP_DWELL_JITTER)
    pri = dict(confidence_scale=CONFIDENCE_SCALE, switch_lead_steps=SWITCH_LEAD_STEPS)
    if name == "RoundRobin":
        return RoundRobinScheduler(N_BANDS)
    if name == "Random":
        return RandomScheduler(N_BANDS)
    if name == "BeliefUCB":
        return BeliefUCBScheduler(N_BANDS, **common)
    if name == "PRIAware":
        return PRIAwareScheduler(N_BANDS, **common, **pri, min_cycles=MIN_CYCLES,
                                 max_blend_confidence=MAX_BLEND_CONFIDENCE)
    if name == "PersistentPRIAware":
        return PersistentPRIAwareScheduler(N_BANDS, **common, **pri, min_cycles=MIN_CYCLES,
                                           max_blend_confidence=MAX_BLEND_CONFIDENCE)
    if name == "ScanAwarePRI":
        return ScanAwarePRIScheduler(N_BANDS, **common, **pri)
    if name == "HedgeBlended":
        return HedgeBlendedPRIAwareScheduler(N_BANDS, **common, **pri, min_cycles=MIN_CYCLES,
                                             eta=ETA, class_balance_alpha=CLASS_BALANCE_ALPHA)
    if name == "WhittleIndex":
        return WhittleIndexScheduler(N_BANDS, **common)
    raise ValueError(f"unknown algorithm {name!r}")


class Recorder:
    """Transparent wrapper: run_episode only calls choose_bands()/update(), so
    this records per-band hits and which (step, band) pairs were scanned
    without touching the scheduler or the episode runner."""

    def __init__(self, sched, n_steps, n_bands):
        self.sched = sched
        self.scanned = np.zeros((n_steps, n_bands), dtype=bool)
        self.hits = np.zeros(n_bands, dtype=np.int64)
        self._t = -1

    def choose_bands(self, k):
        bands = self.sched.choose_bands(k)
        self._t += 1
        if self._t < len(self.scanned):
            for b in bands:
                self.scanned[self._t, b] = True
        return bands

    def update(self, band, observed_on):
        self.sched.update(band, observed_on)
        if observed_on:
            self.hits[band] += 1

    def __getattr__(self, name):
        return getattr(self.sched, name)


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def resolve_path(item):
    p = Path(item)
    cands = [p] if p.is_absolute() else [Path.cwd() / p, Path(__file__).resolve().parent / p]
    for c in cands:
        if c.exists():
            return c.resolve()
    raise FileNotFoundError(f"file not found: {item}  (tried: {', '.join(str(c) for c in cands)})")


def mean_std(vals):
    if not vals:
        return None, None
    return statistics.mean(vals), (statistics.pstdev(vals) if len(vals) > 1 else 0.0)


def fmt_pct(vals):
    m, s = mean_std(vals)
    if m is None:
        return "n/a"
    return f"{m:6.1f}%" if len(vals) == 1 else f"{m:6.1f}% +/-{s:4.1f}"


# -----------------------------------------------------------------------------
# HDBSCAN deinterleaving (optional)
# -----------------------------------------------------------------------------

def _cluster_v(pdw, label):
    from sklearn.cluster import HDBSCAN
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import v_measure_score, homogeneity_score, completeness_score
    feats = StandardScaler().fit_transform(np.column_stack([pdw["cf"], pdw["pw"], pdw["aoa"]]))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)   # sklearn's `copy` default notice
        pred = HDBSCAN(min_cluster_size=10).fit_predict(feats)
    true = pdw["label"]
    n_found = len(set(pred)) - (1 if -1 in pred else 0)
    noise = int((pred == -1).sum())
    v = v_measure_score(true, pred)
    print(f"    {label:34s} n={len(pdw):7d}  true_emitters={len(set(true)):2d}  "
          f"clusters={n_found:3d}  noise={100 * noise / len(pdw):4.1f}%  "
          f"V={v:.3f} (hom={homogeneity_score(true, pred):.3f}, "
          f"comp={completeness_score(true, pred):.3f})")
    return v


def deinterleave_report(pdw, source, scanned, n_steps):
    print("\n  Deinterleaving (HDBSCAN on CF/PW/AoA, scored with V-measure):")
    try:
        import sklearn.cluster  # noqa: F401
        from sklearn.cluster import HDBSCAN  # noqa: F401
    except ImportError:
        print("    SKIPPED -- needs scikit-learn >= 1.3 (pip install -U scikit-learn)")
        return {}
    if "label" not in (pdw.dtype.names or ()):
        print("    SKIPPED -- no ground-truth labels in this file")
        return {}
    lo, hi = source.freq_range_mhz
    edges = np.linspace(lo, hi, N_BANDS + 1)
    band_idx = np.clip(np.digitize(pdw["cf"], edges) - 1, 0, N_BANDS - 1)
    step_idx = np.maximum(((pdw["toa"] - source.t0_us) // DWELL_US).astype(np.int64), 0)
    in_range = step_idx < n_steps
    pdw_d, band_idx, step_idx = pdw[in_range], band_idx[in_range], step_idx[in_range]
    if len(pdw_d) > DEINTERLEAVE_MAX_PULSES:
        print(f"    SKIPPED -- {len(pdw_d)} pulses > DEINTERLEAVE_MAX_PULSES "
              f"({DEINTERLEAVE_MAX_PULSES}); set a WINDOW for this file")
        return {}
    out = {"v_full": _cluster_v(pdw_d, "full stream (leaderboard-style)")}
    if scanned is not None:
        mask = scanned[step_idx, band_idx]
        print(f"    {DEINTERLEAVE_SCHEDULER} intercepted {int(mask.sum())}/{len(pdw_d)} pulses "
              f"({100 * mask.sum() / max(1, len(pdw_d)):.1f}%)")
        if mask.sum() >= 20:
            out["v_intercepted"] = _cluster_v(pdw_d[mask], f"{DEINTERLEAVE_SCHEDULER} intercepted subset")
        else:
            print("    intercepted subset too small to cluster")
    return out


# -----------------------------------------------------------------------------
# One file
# -----------------------------------------------------------------------------

_SOURCE_CACHE = {}   # (path, window) -> (source, pdw): each file is read once, reused for every k


def run_one_file(file_key, path, window, k_channels, first_pass=True):
    key = (str(path), window)
    if key not in _SOURCE_CACHE:
        source = PDWSource(h5_path=str(path), n_bands=N_BANDS, window_s=window)
        # Hard guarantee: this runner never operates on synthetic data.
        assert source.kind == "h5", "internal error: non-real data source"
        _SOURCE_CACHE[key] = (source, source.for_seed(0))
    source, pdw = _SOURCE_CACHE[key]

    if first_pass:
        print(source.banner(N_BANDS, DWELL_US))

    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=DWELL_US,
                                    freq_range_mhz=source.freq_range_mhz, t0_us=source.t0_us)

    probe = env_factory()
    n_steps = probe.n_steps
    if n_steps == 0:
        raise RuntimeError("no pulses found in the loaded data -- nothing to replay")
    if MAX_STEPS and n_steps > MAX_STEPS:
        print(f"\n  Capping replay at MAX_STEPS={MAX_STEPS} of {n_steps} steps "
              f"({MAX_STEPS * DWELL_US / 1e6:.2f} s of {n_steps * DWELL_US / 1e6:.2f} s)")
        n_steps = MAX_STEPS
    status = probe._status[:n_steps]
    on_per_band = status.sum(axis=0).astype(np.int64)
    total_on = int(on_per_band.sum())
    print(f"\n  {n_steps} scan steps at dwell {DWELL_US} us ({n_steps * DWELL_US / 1e6:.2f} s), "
          f"k={k_channels}, warmup={WARMUP_STEPS}, switch_cost={SWITCH_COST_STEPS}, seeds={SEEDS}")
    if first_pass:
        print("  Band ON-steps: " + ", ".join(f"b{b}={int(on_per_band[b])}" for b in range(N_BANDS)))
    dead = [b for b in range(N_BANDS) if on_per_band[b] == 0]
    if dead and first_pass:
        print(f"  NOTE: bands {dead} are never ON -- noticing them is a trivial win for learned schedulers.")
    if total_on == 0:
        raise RuntimeError("no band is ever ON in the replayed span")

    if SHOW_WINDOW_SUGGESTIONS and first_pass:
        try:
            sug = suggest_windows(source, N_BANDS, DWELL_US, top=3)
            if sug:
                print("  Suggested windows (band, start_s, duration_s, ~cycles) -- paste into WINDOWS:")
                for s in sug:
                    print(f"    band {s['band']}: ({s['start_s']:.4f}, {s['duration_s']:.4f})  "
                          f"~{s['cycles']:.0f} cycles, {s['pulses']} pulses")
        except Exception as exc:   # advisory only
            print(f"  (window suggestions unavailable: {exc})")

    rows, band_rows = [], []
    oracle_pct = None
    if RUN_ORACLE:
        oh = int(np.minimum(status.sum(axis=1), k_channels).sum())
        oracle_pct = 100.0 * oh / total_on
        print(f"\n  GENIE ORACLE ceiling (k={k_channels}): {oracle_pct:.1f}%")
        rows.append(dict(k=k_channels, file=file_key, algorithm="ORACLE", seed="", status="ok",
                         interception_pct=oracle_pct, avg_reward_per_step="", avg_intercept_delay="",
                         switches="", wasted_scans="", elapsed_s=0.0, oracle_pct=oracle_pct,
                         n_steps=n_steps, error=""))

    print()
    hdr = (f"  {'Algorithm':20s} | {'Interception':>17s} | {'Gap to oracle':>13s} | "
           f"{'Reward/step':>11s} | {'Switches':>8s} | {'Time (s)':>8s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    per_algo = {}          # name -> dict of seed-lists
    last_sched = {}        # name -> first successful scheduler (for diagnostics)
    deint_scanned = None

    for name, enabled in ALGORITHMS.items():
        if not enabled:
            continue
        ints, rews, times, sws = [], [], [], []
        errors = []
        for seed in SEEDS:
            random.seed(seed)
            try:
                sched = build_scheduler(name)
                rec = Recorder(sched, n_steps, N_BANDS)
                t0 = time.time()
                stats = run_episode(env_factory, rec, n_steps, N_BANDS,
                                    k_channels=k_channels, switch_cost_steps=SWITCH_COST_STEPS)
                elapsed = time.time() - t0
            except Exception as exc:
                traceback.print_exc()
                errors.append(f"seed {seed}: {type(exc).__name__}: {exc}")
                rows.append(dict(k=k_channels, file=file_key, algorithm=name, seed=seed, status="FAILED",
                                 interception_pct="", avg_reward_per_step="", avg_intercept_delay="",
                                 switches="", wasted_scans="", elapsed_s="", oracle_pct=oracle_pct,
                                 n_steps=n_steps, error=errors[-1]))
                continue
            pct = 100.0 * stats.hits / max(1, stats.total_band_transmissions)
            r = stats.report()
            if int(rec.hits.sum()) != stats.hits:
                print(f"  WARNING: per-band hit total {int(rec.hits.sum())} != episode hits "
                      f"{stats.hits} for {name}")
            ints.append(pct)
            rews.append(r["avg_reward_per_step"])
            times.append(elapsed)
            sws.append(stats.switches)
            rows.append(dict(k=k_channels, file=file_key, algorithm=name, seed=seed, status="ok",
                             interception_pct=pct, avg_reward_per_step=r["avg_reward_per_step"],
                             avg_intercept_delay=r["avg_intercept_delay"], switches=stats.switches,
                             wasted_scans=stats.wasted_scans, elapsed_s=elapsed,
                             oracle_pct=oracle_pct, n_steps=n_steps, error=""))
            for b in range(N_BANDS):
                band_rows.append(dict(k=k_channels, file=file_key, algorithm=name, seed=seed, band=b,
                                      on_steps=int(on_per_band[b]), hits=int(rec.hits[b]),
                                      capture_pct=(100.0 * rec.hits[b] / on_per_band[b])
                                      if on_per_band[b] else ""))
            if name not in last_sched:
                last_sched[name] = sched
            if name == DEINTERLEAVE_SCHEDULER and deint_scanned is None:
                deint_scanned = rec.scanned
        if ints:
            m = statistics.mean(ints)
            gap = f"{oracle_pct - m:10.1f} pp" if oracle_pct is not None else "n/a"
            print(f"  {name:20s} | {fmt_pct(ints):>17s} | {gap:>13s} | "
                  f"{statistics.mean(rews):11.3f} | {int(statistics.mean(sws)):8d} | "
                  f"{statistics.mean(times):8.1f}")
            per_algo[name] = ints
        else:
            print(f"  {name:20s} | FAILED -- {errors[0] if errors else 'no result'}")

    # ---- per-band capture (seed 0 / first seed) ----------------------------
    live_bands = [b for b in range(N_BANDS) if on_per_band[b] > 0]
    if band_rows and live_bands:
        print("\n  Per-band capture % (first seed; blank = band never ON). "
              "Overall % is dominated by the busiest band -- read this table too.")
        print("  " + f"{'Algorithm':20s}" + "".join(f"{'b' + str(b):>8s}" for b in range(N_BANDS)))
        print("  " + f"{'(ON steps)':20s}" + "".join(f"{int(on_per_band[b]):>8d}" for b in range(N_BANDS)))
        first_seed = SEEDS[0]
        for name in ALGORITHMS:
            sel = {r["band"]: r["capture_pct"] for r in band_rows
                   if r["algorithm"] == name and r["seed"] == first_seed}
            if not sel:
                continue
            cells = "".join(f"{(f'{sel[b]:.1f}' if sel.get(b) not in ('', None) else ''):>8s}"
                            for b in range(N_BANDS))
            print("  " + f"{name:20s}" + cells)

    # ---- PRI diagnostics vs the file's own metadata truth ------------------
    try:
        truth, _notes = source.true_periodic_bands(N_BANDS)
    except Exception:
        truth = {}
    printed_hdr = False
    for name in PRI_FAMILY:
        sched = last_sched.get(name)
        if sched is None or not isinstance(sched, PRIAwareScheduler):
            continue
        lines = []
        for b in range(N_BANDS):
            est = sched.pri_estimate[b]
            if est is None:
                continue
            us = est * DWELL_US
            conf = sched.confidence[b]
            tag = " (stagger)" if getattr(sched, "is_staggered", [False] * N_BANDS)[b] else ""
            tru = truth.get(b)
            err = f"  truth {tru:.2f} us, error {100 * abs(us - tru) / tru:.2f}%" if tru else "  (no metadata truth)"
            scan = ""
            sp = getattr(sched, "scan_period_estimate", None)
            if sp is not None and sp[b] is not None:
                scan = f"  scan period ~{sp[b] * DWELL_US:.0f} us"
            lines.append(f"      band {b}: PRI ~{us:.2f} us ({est:.2f} steps){tag} conf {conf:.2f}{err}{scan}")
        if not printed_hdr:
            print("\n  PRI locks vs metadata truth:")
            printed_hdr = True
        print(f"    {name}: " + ("no band locked" if not lines else ""))
        for ln in lines:
            print(ln)

    extras = {}
    if RUN_DEINTERLEAVE:
        extras = deinterleave_report(pdw, source, deint_scanned, n_steps)

    return rows, band_rows, per_algo, oracle_pct, extras


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    if not H5_FILES:
        raise SystemExit("H5_FILES is empty -- add at least one real .h5 path at the top of run_real_data.py")
    if SWITCH_COST_STEPS > 0:
        print("NOTE: SWITCH_COST_STEPS > 0 has only been validated on toy scenarios, never on real data.\n")

    run_dir = Path(OUTPUT_DIR)
    if not run_dir.is_absolute():
        run_dir = Path(__file__).resolve().parent / run_dir
    run_dir = run_dir / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    report = open(run_dir / "report.txt", "w", encoding="utf-8")
    real_stdout = sys.stdout
    sys.stdout = Tee(real_stdout, report)

    all_rows, all_band_rows = [], []
    results = {}        # file_key -> (per_algo, oracle)
    failed = []
    t_start = time.time()
    try:
        print("=" * 80)
        print("REAL-DATA RUN  (real .h5 files only -- no synthetic data)")
        print("=" * 80)
        print(f"Files ({len(H5_FILES)}): ")
        for f in H5_FILES:
            print(f"  - {f}")
        print(f"Channel counts (k), run iteratively per file: {K_VALUES}")
        print(f"Algorithms: {', '.join(n for n, on in ALGORITHMS.items() if on)}"
              f"{'  + ORACLE' if RUN_ORACLE else ''}")
        print(f"Output: {run_dir}")

        for i, file_key in enumerate(H5_FILES, start=1):
            print("\n" + "#" * 80)
            print(f"FILE {i}/{len(H5_FILES)}: {file_key}")
            print("#" * 80)
            t_file = time.time()
            try:
                path = resolve_path(file_key)
                for ki, k in enumerate(K_VALUES):
                    print("\n" + "-" * 80)
                    print(f"  >>> {Path(file_key).parent.name}/{Path(file_key).stem}   k = {k}   "
                          f"({ki + 1}/{len(K_VALUES)})")
                    print("-" * 80)
                    t_k = time.time()
                    rows, band_rows, per_algo, oracle_pct, _extras = run_one_file(
                        file_key, path, WINDOWS.get(file_key), k, first_pass=(ki == 0))
                    all_rows += rows
                    all_band_rows += band_rows
                    results[(file_key, k)] = (per_algo, oracle_pct)
                    print(f"\n  -- k={k} finished in {(time.time() - t_k) / 60:.1f} min")
                print(f"\n  -- file finished in {(time.time() - t_file) / 60:.1f} min")
            except KeyboardInterrupt:
                print("\nInterrupted by user -- stopping; results so far are saved.")
                failed.append((file_key, "interrupted"))
                break
            except Exception as exc:
                traceback.print_exc()
                print(f"\n  FAILED: {type(exc).__name__}: {exc}")
                print("  (this file is skipped -- no synthetic fallback is ever used)")
                failed.append((file_key, f"{type(exc).__name__}: {exc}"))
                all_rows.append(dict(k=0, file=file_key, algorithm="(file)", seed="", status="FAILED",
                                     error=f"{type(exc).__name__}: {exc}"))

        # ---- cross-file summary, one table per k ------------------------------
        if results:
            names = (["ORACLE"] if RUN_ORACLE else []) + [n for n, on in ALGORITHMS.items() if on]
            file_keys = [f for f in H5_FILES if any((f, k) in results for k in K_VALUES)]
            labels = [(Path(f).parent.name[:4] + "/" + Path(f).stem)[:16] for f in file_keys]

            def cell(name, f, k):
                if (f, k) not in results:
                    return None
                per_algo, oracle_pct = results[(f, k)]
                return oracle_pct if name == "ORACLE" else (
                    statistics.mean(per_algo[name]) if name in per_algo else None)

            mean_tab = {}    # (name, k) -> mean over files, or None
            for k in K_VALUES:
                print("\n\n" + "=" * 80)
                print(f"SUMMARY k={k} -- overall interception % per file")
                print("=" * 80)
                print(f"{'Algorithm':20s}" + "".join(f"{lab:>17s}" for lab in labels) + f"{'MEAN':>10s}")
                for name in names:
                    cells = [cell(name, f, k) for f in file_keys]
                    vals = [v for v in cells if v is not None]
                    m = statistics.mean(vals) if len(vals) == len(file_keys) else None
                    mean_tab[(name, k)] = m
                    print(f"{name:20s}" + "".join(f"{('n/a' if v is None else f'{v:.1f}%'):>17s}" for v in cells)
                          + f"{('n/a' if m is None else f'{m:.1f}%'):>10s}")

            print("\n\n" + "=" * 80)
            print("SUMMARY across k -- MEAN interception % over files, and gain vs RoundRobin at the same k")
            print("=" * 80)
            print(f"{'Algorithm':20s}" + "".join(f"{'k=' + str(k):>10s}" for k in K_VALUES)
                  + "".join(f"{'xRR k=' + str(k):>11s}" for k in K_VALUES))
            for name in names:
                cols = [mean_tab.get((name, k)) for k in K_VALUES]
                gains = []
                for k, m in zip(K_VALUES, cols):
                    rr = mean_tab.get(("RoundRobin", k))
                    gains.append("n/a" if (m is None or not rr) else f"{m / rr:.1f}x")
                print(f"{name:20s}" + "".join(f"{('n/a' if m is None else f'{m:.1f}%'):>10s}" for m in cols)
                      + "".join(f"{g:>11s}" for g in gains))
            print("\n(MEAN needs a result on every file. Scan-mode and stare-mode files measure different "
                  "things -- see each banner. Compare across k via the xRR columns and the oracle gap, "
                  "not raw %.)")

        print("\n" + "=" * 80)
        print(f"DONE in {(time.time() - t_start) / 60:.1f} min -- "
              f"{len({f for f, _ in results})} file(s) succeeded, {len(failed)} failed")
        for k, why in failed:
            print(f"  [FAILED] {k}: {why}")
        print(f"Saved: {run_dir}")
        print("=" * 80)
    finally:
        sys.stdout = real_stdout
        report.close()
        write_csv(run_dir / "summary.csv", all_rows,
                  ["k", "file", "algorithm", "seed", "status", "interception_pct", "oracle_pct",
                   "avg_reward_per_step", "avg_intercept_delay", "switches", "wasted_scans",
                   "elapsed_s", "n_steps", "error"])
        write_csv(run_dir / "per_band.csv", all_band_rows,
                  ["k", "file", "algorithm", "seed", "band", "on_steps", "hits", "capture_pct"])

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
