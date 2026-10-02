"""
pdw_source.py
===============
One place that answers "where did this PDW stream come from, and what is
its ground truth?" -- so every experiment script can accept `--h5`
identically instead of each growing its own half-version of the same
wiring.

Why this module exists at all
-----------------------------
Before this, every PDW-capable script called
`generate_synthetic_pdw_stream(seed=seed)` directly and hard-coded the
stand-in's truth (`TRUE_PERIODIC_BANDS = {1: 1000.0, 4: 650.0, 6:
1500.0}`). Those constants are only true because the stand-in generator
declares them. Pointing those same scripts at a real .h5 without
replacing the truth would have them assert a synthetic emitter's PRI
against a completely different real emitter and report confident
nonsense. So `--h5` support is NOT just "accept a path": the truth has
to come out of the file too.

Three things change when the source is a real .h5 rather than the
stand-in, and all three are surfaced explicitly rather than left for the
reader to infer:

1. SEED SEMANTICS CHANGE.  With the stand-in, `seed` drives both the
   data and the scheduler's own randomness, so N seeds = N different
   environments and the spread across them measures robustness to the
   environment.  A real .h5 is one fixed recording: the seed then only
   perturbs warm-up shuffle order and UCB tie-breaking, so the spread
   measures robustness to scheduler randomness on a single environment.
   Those are different claims.  `PDWSource.seed_semantics` names which
   regime a run was in, and it is stamped into every CSV row.

2. GROUND TRUTH COMES FROM THE FILE.  `true_periodic_bands()` derives
   (band -> true period) from the file's own transmitter metadata, and
   refuses to emit a truth entry for any band it cannot defend (band
   shared by several emitters, frequency-hopping emitter smeared across
   bands, PRI mode with no single well-defined period).  The reasons are
   kept in `truth_notes` and printed, not swallowed.

3. THE RECEIVER IN A SCAN-MODE FILE IS ITSELF A SCANNING RECEIVER.  See
   the long note in `banner()`.  This is the single most important thing
   to understand before quoting an interception ratio measured on one of
   these files.

The TSRD .h5 layout is read directly with h5py rather than through
`turing_deinterleaving_challenge.PulseTrain.load`.  The layout is plain
(`data` (N,5) float32, `labels` (N,1) int8, `metadata/...` attrs), the
package is gated behind a HuggingFace licence, and a hard dependency on
it is exactly what made the old `load_real_pulse_train()` fall back to
synthetic data on ImportError -- i.e. silently answer a real-data
question with fake data.  The package path is kept only as a fallback.
"""

import argparse
import os
import numpy as np

from pdw_loader import generate_synthetic_pdw_stream

PDW_DTYPE = [("toa", "f8"), ("cf", "f8"), ("pw", "f8"),
             ("aoa", "f8"), ("amp", "f8"), ("label", "i4")]

# The stand-in's declared truth, kept here so the synthetic path behaves
# byte-for-byte as before (see validate_pdw_multiseed.py's docstring for
# how these map onto bands at n_bands=8, freq_range (0, 18000)).
SYNTHETIC_TRUE_PERIODIC_BANDS = {1: 1000.0, 4: 650.0, 6: 1500.0}


class PDWSourceError(RuntimeError):
    """Raised when an explicitly-requested real .h5 cannot be loaded.

    Deliberately fatal: a run asked for real data, so quietly handing it
    synthetic data instead would make the result a lie.
    """


# ----------------------------------------------------------------------
# Reading a real TSRD .h5
# ----------------------------------------------------------------------

def read_h5_pulse_train(path):
    """Read a TSRD .h5 directly with h5py.

    Returns (pdw, meta) where `pdw` is a structured array in exactly the
    dtype `generate_synthetic_pdw_stream()` produces -- so
    PDWReplayEnvironment and every scheduler run unmodified -- and `meta`
    is a plain dict of the receiver/transmitter configuration.
    """
    if not os.path.exists(path):
        raise PDWSourceError(f"--h5 path does not exist: {path}")
    try:
        import h5py
    except ImportError as exc:
        raise PDWSourceError(
            "h5py is required to read a TSRD .h5 directly. Install it with:\n"
            "    pip install h5py"
        ) from exc

    with h5py.File(path, "r") as f:
        data = np.asarray(f["data"][:], dtype=np.float64)
        labels = np.asarray(f["labels"][:], dtype=np.int32).ravel()
        names = [x.decode() if isinstance(x, bytes) else str(x)
                 for x in f["metadata/feature_names"][:]]

        meta = {"path": path, "feature_names": names,
                "n_pulses": int(data.shape[0])}
        md = f["metadata"]
        for k, v in md.attrs.items():
            meta[str(k)] = v.item() if hasattr(v, "item") else v

        rx = {}
        if "receiver" in md:
            grp = md["receiver"]
            for k, v in grp.attrs.items():
                rx[str(k)] = v.item() if hasattr(v, "item") else v
            for k in grp:
                rx[k] = np.asarray(grp[k][:])
        meta["receiver"] = rx

        txs = {}
        if "transmitters" in md:
            tgrp = md["transmitters"]
            for name in tgrp:
                # "transmitters_7" -> 7; this index is what `labels` refers to
                try:
                    idx = int(str(name).rsplit("_", 1)[-1])
                except ValueError:
                    continue
                g = tgrp[name]
                tx = {"function": _attr(g, "function", "")}
                fc, pc, sc = g.get("frequency_config"), g.get("pri_config"), g.get("scan_config")
                if fc is not None:
                    tx["freq_mode"] = _attr(fc, "freq_mode", "")
                    tx["freqs_mhz"] = np.asarray(fc["freqs_mhz"][:]) if "freqs_mhz" in fc else np.array([])
                if pc is not None:
                    tx["pri_mode"] = _attr(pc, "pri_mode", "")
                    tx["pris_us"] = np.asarray(pc["pris_us"][:]) if "pris_us" in pc else np.array([])
                if sc is not None:
                    tx["scan_type"] = _attr(sc, "scan_type", "")
                    tx["scan_rate_rpm"] = float(_attr(sc, "scan_rate_rpm", 0.0) or 0.0)
                    tx["beam_width_deg"] = float(_attr(sc, "beam_width_deg", 0.0) or 0.0)
                txs[idx] = tx
        meta["transmitters"] = txs

    pdw = np.empty(data.shape[0], dtype=PDW_DTYPE)
    pdw["toa"] = data[:, 0]
    pdw["cf"] = data[:, 1]
    pdw["pw"] = data[:, 2]
    pdw["aoa"] = data[:, 3]
    pdw["amp"] = data[:, 4]
    pdw["label"] = labels
    pdw = pdw[np.argsort(pdw["toa"], kind="stable")]
    return pdw, meta


def _attr(grp, key, default=None):
    v = grp.attrs.get(key, default)
    if isinstance(v, bytes):
        return v.decode()
    if hasattr(v, "item") and getattr(v, "shape", ()) == ():
        return v.item()
    return v


# ----------------------------------------------------------------------
# Deriving ground truth from a real file's own metadata
# ----------------------------------------------------------------------

def _declared_period_us(tx):
    """The period a transmitter's PRI config actually repeats on.

    Fixed      -> the single PRI.
    Staggered  -> the sum of the stagger group.  A staggered emitter is
                  not aperiodic: its pulse pattern repeats once per full
                  group, so the group sum is the period a periodicity
                  estimator can legitimately be scored against (the
                  individual PRIs are not).
    Anything else (jittered, sliding, D&S) has no single well-defined
    period -> None, and the band is excluded from truth rather than
    scored against a number that does not exist.
    """
    pris = np.asarray(tx.get("pris_us", []), dtype=float)
    mode = str(tx.get("pri_mode", "")).lower()
    if pris.size == 0:
        return None, "no PRI values in metadata"
    if mode == "fixed":
        return float(pris[0]), "Fixed"
    if mode == "staggered":
        return float(pris.sum()), f"Staggered (group of {pris.size}, sum)"
    return None, f"PRI mode '{tx.get('pri_mode')}' has no single period"


def derive_true_periodic_bands(pdw, meta, n_bands, freq_range_mhz,
                               dominance=0.95, min_pulses=8):
    """(band -> true period in us) derived from the file's own metadata.

    A band earns a truth entry only when all of these hold:
      * it actually contains pulses (>= `min_pulses`),
      * one emitter label supplies >= `dominance` of them (otherwise the
        band is a collision: the superposition of two emitters is not
        periodic, and "no lock" there is the correct answer, not a
        failure -- this is the same structural artefact found earlier on
        the stand-in's band 1),
      * that label's own pulses are mostly IN this band (otherwise it is
        a frequency hopper smeared across several bands and this band
        only sees a fraction of its pulses, so its declared PRI is not
        the period observable here),
      * its PRI mode defines a single period (see _declared_period_us).

    Everything rejected is recorded in `notes` with the reason.
    """
    lo, hi = freq_range_mhz
    edges = np.linspace(lo, hi, n_bands + 1)
    band_of = np.clip(np.digitize(pdw["cf"], edges) - 1, 0, n_bands - 1)
    labels = pdw["label"]
    txs = meta.get("transmitters", {})

    truth, notes = {}, {}
    for b in range(n_bands):
        in_band = band_of == b
        n_in = int(in_band.sum())
        if n_in < min_pulses:
            notes[b] = f"only {n_in} pulses in band"
            continue
        uniq, counts = np.unique(labels[in_band], return_counts=True)
        top = int(uniq[np.argmax(counts)])
        share = counts.max() / n_in
        if share < dominance:
            others = ", ".join(str(int(u)) for u in uniq)
            notes[b] = (f"collision: {len(uniq)} emitters share this band "
                        f"(labels {others}); dominant label {top} is only "
                        f"{share*100:.1f}%")
            continue
        label_total = int((labels == top).sum())
        containment = counts.max() / label_total if label_total else 0.0
        if containment < dominance:
            notes[b] = (f"label {top} is frequency-agile: only "
                        f"{containment*100:.1f}% of its pulses land in this band")
            continue
        tx = txs.get(top)
        if tx is None:
            notes[b] = f"no transmitter metadata for label {top}"
            continue
        period, why = _declared_period_us(tx)
        if period is None:
            notes[b] = f"label {top} ({tx.get('function','?')}): {why}"
            continue
        truth[b] = period
        notes[b] = (f"label {top} ({tx.get('function','?')}), {why} "
                    f"-> {period:.2f} us, {n_in} pulses")
    return truth, notes


def empirical_period_check(pdw, meta, truth, n_bands, freq_range_mhz):
    """Sanity-check each metadata-derived period against the file itself.

    Metadata says what was configured; the recording is what survived the
    receiver.  Where the two disagree, that disagreement is the finding,
    so it is reported rather than resolved silently in favour of either.
    """
    lo, hi = freq_range_mhz
    edges = np.linspace(lo, hi, n_bands + 1)
    band_of = np.clip(np.digitize(pdw["cf"], edges) - 1, 0, n_bands - 1)
    out = {}
    for b, period in truth.items():
        t = np.sort(pdw["toa"][band_of == b])
        if t.size < 3:
            continue
        gaps = np.diff(t)
        intra = gaps[gaps <= period * 3]  # ignore inter-burst silences
        out[b] = {
            "declared_us": period,
            "median_gap_us": float(np.median(gaps)),
            "median_intra_gap_us": float(np.median(intra)) if intra.size else float("nan"),
            "n_gaps_within_3x": int(intra.size),
            "n_gaps": int(gaps.size),
        }
    return out


# ----------------------------------------------------------------------
# The source object every script talks to
# ----------------------------------------------------------------------

class PDWSource:
    def __init__(self, h5_path=None, n_bands=8, freq_range_mhz=None,
                 window_s=None):
        """window_s: optional (start_s, duration_s) in ABSOLUTE ToA seconds,
        restricting a real recording to a sub-window.

        Needed because a real TSRD file is tens of seconds long, and a
        dwell fine enough to resolve a microsecond-scale PRI turns that
        into ~10^6 scan steps -- two orders of magnitude longer than any
        episode this codebase has ever run. Coarsening the dwell instead
        makes the PRI sub-step and therefore unresolvable by
        construction, which is why every band came back NO LOCK at
        dwell=1000us. A window keeps the fine dwell and shortens the
        span, so the periods are actually resolvable.

        Steps are numbered from the window start (see t0_us), so a
        window never prepends empty leading steps."""
        self.n_bands = n_bands
        self.path = h5_path
        self.kind = "h5" if h5_path else "synthetic"
        self._cached = None
        self.window_s = window_s
        self.meta = {}

        if h5_path:
            self._cached, self.meta = read_h5_pulse_train(h5_path)
            if window_s:
                start_us = float(window_s[0]) * 1e6
                end_us = start_us + float(window_s[1]) * 1e6
                toa = self._cached["toa"]
                self._cached = self._cached[(toa >= start_us) & (toa < end_us)]
                self._window_us = (start_us, end_us)
                if len(self._cached) == 0:
                    raise PDWSourceError(
                        f"--window {window_s[0]}s +{window_s[1]}s contains no pulses "
                        f"in {h5_path}")
            rx_range = self.meta.get("receiver", {}).get("freq_range_mhz")
            if freq_range_mhz is None and rx_range is not None and len(rx_range) == 2:
                freq_range_mhz = (float(rx_range[0]), float(rx_range[1]))
        self.freq_range_mhz = freq_range_mhz or (0, 18000)

    # -- data ---------------------------------------------------------
    def for_seed(self, seed):
        """The PDW stream for this seed.

        Synthetic: a fresh stream per seed.  Real .h5: the same fixed
        recording every time -- which is exactly why `seed_semantics`
        below exists.
        """
        if self.kind == "h5":
            return self._cached
        return generate_synthetic_pdw_stream(seed=seed)

    @property
    def t0_us(self):
        """ToA origin. A real recording does not start at t=0 (config_169
        starts at 1.13 s), and `toa // dwell` would otherwise prepend tens
        of thousands of guaranteed-empty scan steps before any emitter can
        appear -- free 'correctly predicted silence' for every scheduler
        and a badly distorted interception denominator."""
        if self.kind == "h5" and self._cached is not None and len(self._cached):
            if self.window_s:
                return float(self._window_us[0])
            return float(self._cached["toa"].min())
        return 0.0

    @property
    def seed_semantics(self):
        if self.kind == "h5":
            return ("scheduler-randomness-only (one fixed recording; "
                    "seeds do NOT vary the environment)")
        return "environment+scheduler (each seed is a different environment)"

    @property
    def provenance(self):
        return self.kind if self.kind == "synthetic" else f"h5:{os.path.basename(self.path)}"

    # -- truth --------------------------------------------------------
    def true_periodic_bands(self, n_bands=None):
        n_bands = n_bands or self.n_bands
        if self.kind == "synthetic":
            if n_bands != 8:
                return {}, {b: "synthetic truth is only defined at n_bands=8"
                            for b in range(n_bands)}
            return dict(SYNTHETIC_TRUE_PERIODIC_BANDS), {}
        return derive_true_periodic_bands(self._cached, self.meta, n_bands,
                                          self.freq_range_mhz)

    # -- reporting ----------------------------------------------------
    def banner(self, n_bands=None, dwell_us=None):
        n_bands = n_bands or self.n_bands
        lines = []
        if self.kind == "synthetic":
            lines.append("DATA SOURCE: local schema-faithful synthetic PDW stand-in "
                         "(not the real TSRD).")
            lines.append(f"  seed semantics: {self.seed_semantics}")
            return "\n".join(lines)

        rx = self.meta.get("receiver", {})
        n = self.meta.get("n_pulses", 0)
        toa = self._cached["toa"]
        span_s = (toa.max() - toa.min()) / 1e6 if n else 0.0
        lines.append(f"DATA SOURCE: real TSRD pulse train  {self.path}")
        if self.window_s:
            lines.append(f"  WINDOW: {self.window_s[0]:.4f} s .. "
                         f"{self.window_s[0] + self.window_s[1]:.4f} s of the recording "
                         f"(sub-window of a longer file; steps numbered from window start)")
        lines.append(f"  {n} pulses, ToA span {span_s:.2f} s "
                     f"(collection_time {self.meta.get('collection_time_s', '?')} s), "
                     f"freq range {self.freq_range_mhz[0]:.0f}-{self.freq_range_mhz[1]:.0f} MHz")
        lines.append(f"  seed semantics: {self.seed_semantics}")

        scan_mode = str(rx.get("scan_mode", "")).lower()
        if "scan" in scan_mode:
            sweep = None
            dt = rx.get("dwell_times_s")
            if dt is not None and len(dt):
                sweep = float(np.sum(dt))
            lines.append("")
            lines.append("  *** SCAN-MODE FILE -- READ THIS BEFORE QUOTING AN INTERCEPTION RATIO ***")
            lines.append("  The receiver that produced this recording was ITSELF a fixed-sweep")
            lines.append("  scanning receiver" +
                         (f" ({len(dt)} dwells, {sweep:.2f} s per full sweep)." if sweep else "."))
            lines.append("  So this file is the OUTPUT of an open-loop scanner -- the very baseline")
            lines.append("  this project exists to beat. Every pulse that scanner missed is absent")
            lines.append("  here and is invisible to our scheduler, which means:")
            lines.append("    - the interception denominator is 'what the open-loop scanner already")
            lines.append("      caught', not 'what the emitters actually transmitted';")
            lines.append("    - periodicity found in this stream is partly the ORIGINAL RECEIVER's")
            lines.append("      sweep revisit period, not emitter structure.")
            lines.append("  A stare-mode file is the oracle needed to score scan SCHEDULING honestly.")
            lines.append("  Treat numbers from this file as re-capture efficiency on a pre-filtered")
            lines.append("  stream, not as interception rate against the environment.")

        truth, notes = self.true_periodic_bands(n_bands)
        lines.append("")
        lines.append(f"  Ground truth derived from file metadata (n_bands={n_bands}):")
        for b in range(n_bands):
            if b in truth:
                extra = ""
                if dwell_us:
                    extra = f"  [= {truth[b]/dwell_us:.3f} scan-steps at dwell {dwell_us} us]"
                lines.append(f"    band {b}: TRUTH {truth[b]:.2f} us{extra}  ({notes.get(b,'')})")
            elif b in notes:
                lines.append(f"    band {b}: no truth -- {notes[b]}")
        if not truth:
            lines.append("    (no band qualifies for a defensible truth entry -- "
                         "any PRI-accuracy metric on this file is meaningless)")
        return "\n".join(lines)


# ----------------------------------------------------------------------
# Uniform CLI wiring
# ----------------------------------------------------------------------

def add_pdw_source_args(ap: argparse.ArgumentParser, default_n_bands=8,
                        default_dwell_us=20.0):
    ap.add_argument("--h5", default=None,
                    help="Path to a real TSRD .h5 pulse train. When given, the real "
                         "file is used and its ground truth is derived from its own "
                         "metadata; a load failure is FATAL (no silent fallback to "
                         "the synthetic stand-in). Omit to use the stand-in.")
    ap.add_argument("--n-bands", type=int, default=default_n_bands)
    ap.add_argument("--dwell-us", type=float, default=default_dwell_us)
    add_window_args(ap)
    return ap


def add_window_args(ap):
    ap.add_argument("--window-start-s", type=float, default=None,
                    help="With --h5: restrict the replay to a sub-window of the "
                         "recording, starting at this ABSOLUTE ToA (seconds). Lets you "
                         "keep a PRI-resolving dwell without a 10^6-step episode.")
    ap.add_argument("--window-s", type=float, default=None,
                    help="With --window-start-s: window length in seconds.")
    return ap


def window_from_args(args):
    start = getattr(args, "window_start_s", None)
    dur = getattr(args, "window_s", None)
    if start is None and dur is None:
        return None
    if start is None or dur is None:
        raise SystemExit("FATAL: --window-start-s and --window-s must be given together.")
    return (start, dur)


def resolve_pdw_source(args):
    return PDWSource(h5_path=getattr(args, "h5", None),
                     n_bands=getattr(args, "n_bands", 8),
                     window_s=window_from_args(args))


def suggest_windows(source, n_bands, dwell_us, top=6):
    """Where in a long recording is a band actually live?

    A real emitter is only live during the overlap of its own beam and
    the recording receiver's sweep, so most of the file is silence for
    any given band. This lists the contiguous active stretches per band
    with enough cycles of that band's declared period to be worth
    running, so a window can be chosen from evidence rather than by
    guessing at an offset.
    """
    if source.kind != "h5":
        return []
    pdw = source._cached
    lo, hi = source.freq_range_mhz
    edges = np.linspace(lo, hi, n_bands + 1)
    band_of = np.clip(np.digitize(pdw["cf"], edges) - 1, 0, n_bands - 1)
    truth, _ = source.true_periodic_bands(n_bands)
    out = []
    for b, period_us in truth.items():
        t = np.sort(pdw["toa"][band_of == b])
        if t.size < 8:
            continue
        gaps = np.diff(t)
        # A burst break = a gap far larger than the declared period.
        brk = np.where(gaps > max(period_us * 20, 5000.0))[0]
        starts = np.concatenate(([t[0]], t[brk + 1]))
        ends = np.concatenate((t[brk], [t[-1]]))
        for s_us, e_us in zip(starts, ends):
            n_p = int(((t >= s_us) & (t <= e_us)).sum())
            dur_us = e_us - s_us
            cycles = dur_us / period_us
            out.append({"band": b, "start_s": s_us / 1e6,
                        "duration_s": dur_us / 1e6, "pulses": n_p,
                        "cycles": cycles,
                        "steps_at_dwell": dur_us / dwell_us,
                        "period_steps": period_us / dwell_us})
    out.sort(key=lambda r: -r["cycles"])
    return out[:top]
