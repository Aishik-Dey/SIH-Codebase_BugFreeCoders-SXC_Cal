"""
deinterleave_hdbscan.py
=========================
V-measure/HDBSCAN comparison against TSRD's own leaderboard metric --
the last unstarted item from the original gap analysis with a direct,
concrete motivation already found in this project's own data: the real
config_169.h5 band-1 collision (two emitters landing in the same coarse
8-band channel, confirmed earlier as a structural binning artifact, not
a scheduler bug). Pulse deinterleaving is the tool built for exactly
that problem -- this checks whether unsupervised clustering on the raw
pulse parameters actually recovers what coarse band-binning can't.

TASK: cluster raw PDWs by (CF, PW, AoA) -- the per-pulse parameters
that stay roughly constant for a non-agile emitter -- using HDBSCAN
(sklearn's native implementation, no separate `hdbscan` package
needed), then score against the file's own ground-truth emitter labels
with V-measure (homogeneity/completeness harmonic mean), matching
TSRD's own published scoring metric and baseline algorithm.

TWO parts:
  1. Full-stream V-measure -- the leaderboard-comparable number:
     cluster every pulse in the file, exactly what the TSRD challenge
     itself scores.
  2. Intercepted-subset V-measure -- the genuinely novel, scheduling-
     connected extension nothing in this project has done before: run
     the current best scheduler (HedgeBlendedPRIAwareScheduler) over
     the same file, keep only the pulses it actually caught (same
     band/step binning formula as PDWReplayEnvironment, reproduced
     directly from raw pulse ToA/CF rather than re-deriving through
     the environment object), and cluster THAT subset. This is the
     realistic question: a receiver doesn't deinterleave omniscient
     stare-mode data, it deinterleaves whatever fraction it actually
     intercepted.

Run:  python3 deinterleave_hdbscan.py
"""

import sys
import random
import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import v_measure_score, homogeneity_score, completeness_score

from pdw_source import PDWSource
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler

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


def cluster_and_score(pdw, min_cluster_size=10, min_samples=None, label=""):
    features = np.column_stack([pdw["cf"], pdw["pw"], pdw["aoa"]])
    features = StandardScaler().fit_transform(features)
    true_labels = pdw["label"]

    clusterer = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples)
    pred_labels = clusterer.fit_predict(features)

    n_found = len(set(pred_labels)) - (1 if -1 in pred_labels else 0)
    n_noise = int((pred_labels == -1).sum())
    v = v_measure_score(true_labels, pred_labels)
    h = homogeneity_score(true_labels, pred_labels)
    c = completeness_score(true_labels, pred_labels)
    print(f"  {label:28s} n={len(pdw):5d}  true_emitters={len(set(true_labels))}  "
          f"clusters_found={n_found}  noise_pts={n_noise} ({100*n_noise/len(pdw):.1f}%)  "
          f"V-measure={v:.3f}  (homogeneity={h:.3f}, completeness={c:.3f})")
    return pred_labels, true_labels, v


def confusion_breakdown(true_labels, pred_labels):
    """Which true emitters got merged into the same cluster, or split
    across multiple -- the actual interpretable story behind a
    V-measure number, not just the summary statistic."""
    print("  Per-true-emitter cluster assignment (excluding noise):")
    for t in sorted(set(true_labels)):
        mask = (true_labels == t) & (pred_labels != -1)
        if mask.sum() == 0:
            print(f"    true label {t}: 0 non-noise pulses (all noise or absent)")
            continue
        clusters, counts = np.unique(pred_labels[mask], return_counts=True)
        order = np.argsort(-counts)
        parts = ", ".join(f"cluster {clusters[i]}:{counts[i]}" for i in order)
        print(f"    true label {t} ({mask.sum()} pulses): {parts}")


def agile_vs_fixed_labels(pdw, cf_std_threshold=20.0):
    """Classifies each TRUE label as agile or fixed by its own CF
    spread (std in MHz) -- not a clustering result, a direct read of
    the ground truth. A static (CF,PW,AoA) clustering method has no
    chance of forming one cluster per agile emitter regardless of
    tuning; separating the V-measure by this split is the fair way to
    report what the method can and cannot do, rather than one blended
    number that makes a near-perfect fixed-emitter recovery look
    mediocre because of the agile emitters mixed into the same score
    -- the same 'report per-emitter, not one blended number' lesson
    this project has hit repeatedly elsewhere (sparse-radar headline,
    Gap #1's noise-model demo, Gap #2's radar-band-%)."""
    agile, fixed = set(), set()
    for lbl in sorted(set(pdw["label"])):
        cf_std = pdw["cf"][pdw["label"] == lbl].std()
        (agile if cf_std > cf_std_threshold else fixed).add(int(lbl))
    return agile, fixed


def score_subset(pdw, labels_to_keep, tag):
    mask = np.isin(pdw["label"], list(labels_to_keep))
    if mask.sum() < 10:
        print(f"  {tag}: too few pulses ({mask.sum()}) to score")
        return
    cluster_and_score(pdw[mask], label=tag)


def band_of(cf, freq_range_mhz, n_bands):
    lo, hi = freq_range_mhz
    edges = np.linspace(lo, hi, n_bands + 1)
    return np.clip(np.digitize(cf, edges) - 1, 0, n_bands - 1)


def get_intercepted_mask(pdw, source, k_channels=1):
    """Same band/step binning formula as PDWReplayEnvironment, applied
    directly to the raw pulses (not re-run through the environment
    object) so it can be matched against a fresh, independent run of
    the scheduler's own scan decisions.

    k_channels>1 generalizes the original k=1-only version: a step's
    scanned set is now a per-step BOOLEAN mask over bands (any of the
    k_channels chosen bands counts as scanned that step), not a single
    band index -- needed since choose_bands(k) returns k bands per step
    once k>1."""
    band_idx = band_of(pdw["cf"], source.freq_range_mhz, N_BANDS)
    step_idx = np.maximum(((pdw["toa"] - source.t0_us) // DWELL_US).astype(np.int64), 0)
    n_steps = int(step_idx.max()) + 1

    # Independent re-run of the current best scheduler, warmup=0 -- the
    # same established real-file config used throughout this project
    # (see run_on_turing_dataset.py's default real-data path), now at
    # the given k_channels instead of the original hardcoded k=1.
    from pdw_environment import PDWReplayEnvironment
    env = PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=DWELL_US,
                                freq_range_mhz=source.freq_range_mhz, t0_us=source.t0_us)
    random.seed(1)
    sched = HedgeBlendedPRIAwareScheduler(N_BANDS, ucb_c=0.5, warmup_steps=0)
    scanned_mask = np.zeros((n_steps, N_BANDS), dtype=bool)
    for t in range(env.n_steps):
        status = env.step()
        bands = sched.choose_bands(k_channels)
        for b in bands:
            sched.update(b, status[b])
            scanned_mask[t, b] = True

    valid = step_idx < n_steps
    intercepted = np.zeros(len(pdw), dtype=bool)
    intercepted[valid] = scanned_mask[step_idx[valid], band_idx[valid]]
    return intercepted


if __name__ == "__main__":
    source = PDWSource(h5_path=H5, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(0)

    print("=== Part 1: full-stream V-measure (leaderboard-comparable) ===")
    pred_full, true_full, v_full = cluster_and_score(pdw, label="full stream")
    confusion_breakdown(true_full, pred_full)

    print("\n=== Fair breakdown: static (CF,PW,AoA) clustering vs fixed- vs agile-parameter emitters ===")
    print("  (agile/fixed classified directly from each true label's own CF spread -- "
          "not a clustering result)")
    agile, fixed = agile_vs_fixed_labels(pdw)
    print(f"  agile-by-ground-truth labels: {sorted(agile)}   fixed-by-ground-truth labels: {sorted(fixed)}")
    if fixed:
        score_subset(pdw, fixed, "fixed-parameter emitters only")
    if agile:
        score_subset(pdw, agile, "agile-parameter emitters only")

    print("\n=== Hyperparameter check: is this sensitive to min_cluster_size? ===")
    for mcs in [5, 10, 20, 40]:
        cluster_and_score(pdw, min_cluster_size=mcs, label=f"min_cluster_size={mcs}")

    print("\n=== Part 2: intercepted-subset V-measure at k=1,2,3 (scheduling-connected) ===")
    print("  (k=1 mostly just re-measured label-0's own fragmentation last time -- "
          "label 2 got ZERO surviving pulses, label 4 only 17/29. Checking whether "
          "k=2/k=3 actually let the smaller emitters survive interception.)")
    for k in (1, 2, 3):
        intercepted = get_intercepted_mask(pdw, source, k_channels=k)
        pdw_intercepted = pdw[intercepted]
        print(f"\n  --- k={k}: {intercepted.sum()}/{len(pdw)} pulses intercepted "
              f"({100*intercepted.sum()/len(pdw):.1f}%) ---")
        print("  per-true-label survival:", end=" ")
        survival = []
        for lbl in sorted(set(pdw["label"])):
            n_true = int((pdw["label"] == lbl).sum())
            n_survived = int((pdw_intercepted["label"] == lbl).sum()) if len(pdw_intercepted) else 0
            survival.append(f"label {lbl}: {n_survived}/{n_true}")
        print(", ".join(survival))
        if len(pdw_intercepted) >= 20:
            pred_sub, true_sub, v_sub = cluster_and_score(pdw_intercepted, label=f"intercepted subset (k={k})")
            agile_i, fixed_i = agile_vs_fixed_labels(pdw_intercepted)
            if fixed_i:
                score_subset(pdw_intercepted, fixed_i, f"  intercepted, fixed-only (k={k})")
            if agile_i:
                score_subset(pdw_intercepted, agile_i, f"  intercepted, agile-only (k={k})")
        else:
            print("  Too few intercepted pulses for a meaningful clustering result.")
    print(f"\n  Full-stream V-measure (all pulses, oracle/stare-mode equivalent): {v_full:.3f}")
