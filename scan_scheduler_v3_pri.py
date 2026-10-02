"""
scan_scheduler_v3_pri.py
==========================
Adds an explicit Pulse Repetition Interval (PRI) predictor on top of the
BeliefUCBScheduler from scan_scheduler_v2.py.

Why: a first-order Markov model only knows "this band was recently
active, so it's probably still active" -- it has no notion of a
repeating cycle, so it's a poor fit for fixed-PRI radars and periodic
beacons (exactly the emitter types the real Turing Synthetic Radar
Dataset's fixed-frequency emitters are: near-constant-PRI). This
scheduler tracks the actual gaps between confirmed hits on a band,
estimates the period and its jitter, and predicts the PHASE of the next
expected occurrence -- catching periodic emitters right when they're
due, not just "recently seen so probably still there."

For bursty/agile bands (no stable period), the gap variance stays high,
confidence drops to ~0, and the scheduler falls back to the plain
belief+UCB score -- so this is a strict upgrade, not a trade-off.

Run:  python3 scan_scheduler_v3_pri.py
"""

import math
import random
import statistics
from collections import Counter
from functools import reduce
from typing import List, Optional

from scan_scheduler_v2 import (
    Scheduler, RunStats, run_episode, RoundRobinScheduler, RandomScheduler,
    BeliefUCBScheduler,
)
from scan_scheduler_prototype import (
    Emitter, MarkovEmitter, AgileEmitter, Environment, make_scenario
)


class SparsePeriodicEmitter(Emitter):
    """
    A single, brief pulse every `pri` steps on a fixed band -- much closer
    to a real fixed-PRI radar (short pulse width, long dead time between
    pulses) than the multi-step "beacon" in the base scenario. This is
    exactly the case a first-order Markov model struggles with: the band
    is OFF almost all the time, so "recently on -> probably still on"
    gives almost no signal between pulses, whereas a PRI estimate tells
    you precisely when the next one is due.
    """
    def __init__(self, name, band, pri):
        super().__init__(name)
        self.band = band
        self.pri = pri

    def step(self, t):
        self.on = (t % self.pri == 0)
        return self.band, self.on


def make_sparse_scenario(n_bands=36):
    """Same comm + agile mix as make_scenario, but the periodic source is
    a sparse single-pulse-per-cycle radar (period 12) on one fixed band."""
    def factory():
        emitters = [
            MarkovEmitter("comm-1", band=1, p_on_given_off=0.05, p_on_given_on=0.9),
            MarkovEmitter("comm-2", band=4, p_on_given_off=0.10, p_on_given_on=0.7),
            SparsePeriodicEmitter("fixed-pri-radar", band=5, pri=12),
            AgileEmitter("agile-threat", bands=[0, 3, 6, 7], dwell=2, duty=0.5),
        ]
        return Environment(n_bands=n_bands, emitters=emitters)
    return factory


class PRIAwareScheduler(BeliefUCBScheduler):
    """
    Per band, keeps the last `history_len` confirmed-hit step indices,
    estimates PRI = median(gaps) and jitter = stdev(gaps), and derives a
    periodicity confidence (1 - coefficient_of_variation, clipped to
    [0,1], zeroed below a CoV cutoff so bursty/agile bands never earn
    confidence). The scan score blends the Markov belief with a Gaussian
    "phase bump" centred on the nearest predicted occurrence
    ((t - last_hit) mod PRI), weighted by that confidence, plus the same
    UCB exploration bonus as the parent class.

    IMPORTANT caveat this class had to learn the hard way (found via
    diagnose_beacon_regression.py): the phase bump's width (jitter) is
    fit from residual timing error, which is near-zero for a truly
    periodic emitter -- but that only means the ONSET time is precise,
    not that the emitter is a single-instant event. A multi-step burst
    (e.g. a beacon that stays ON for 4 consecutive steps every cycle)
    still has a near-zero *onset* jitter, which used to collapse the
    bump to a single-point spike and made the scheduler abandon the
    burst after its first step -- actively WORSE than plain Markov
    belief, which stays elevated for the whole burst via learned
    P(on|on). `max_run_ever` (persistent burst-width estimate) widens
    the jitter floor so the bump plateaus across the observed burst
    length instead of collapsing to a point, without affecting emitters
    that really are single-instant (max_run_ever stays 1 for those).
    """
    def __init__(self, n_bands, ucb_c: float = 0.5, history_len: int = 30,
                 min_confidence: float = 0.75, periodicity_weight: float = 1.5,
                 warmup_steps: int = 0, priority: Optional[List[float]] = None,
                 confidence_scale: float = 0.25, switch_lead_steps: int = 0,
                 min_cycles: int = 4, max_blend_confidence: float = 1.0,
                 warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1):
        super().__init__(n_bands, ucb_c=ucb_c, warmup_steps=warmup_steps, priority=priority,
                          warmup_dwell_steps=warmup_dwell_steps,
                          warmup_dwell_jitter=warmup_dwell_jitter)
        self.history_len = history_len
        self.min_confidence = min_confidence
        self.periodicity_weight = periodicity_weight
        # Denominator scale in the confidence formula
        # (confidence = 1 - rmse / (confidence_scale * refined_pri)). Larger
        # = more forgiving (reaches high confidence with a looser relative
        # fit); smaller = requires a tighter fit before trusting a
        # candidate. Tunable because a fixed 0.25 turned out to be eager
        # enough to occasionally lock onto a spurious candidate on a
        # non-periodic band (found via settle_fix_interaction.py: a -0.3pp
        # beacon-scenario cost from the harmonic-selection fix's added
        # eagerness) -- see tune_confidence_threshold.py for the sweep
        # that selected this value.
        self.confidence_scale = confidence_scale
        # Minimum number of DISTINCT observed cycles of the candidate
        # period before a lock is allowed.
        #
        # Found on real TSRD data (Validation/config_169.h5, band 1),
        # never on the synthetic stand-in. The stand-in's emitters pulse
        # uniformly, so `history_len` (30) hits = ~30 observed cycles.
        # A real emitter's pulses arrive in dense BURSTS -- both the
        # transmitter and the recording receiver are scanning, so the
        # band is only live during their beam overlap. There, 30 hits =
        # two tight clusters of 15, i.e. only TWO independent looks at
        # the period. _refine_pri then fits a straight line through what
        # are effectively two points, which any period equal to the
        # cluster separation fits perfectly.
        #
        # The confidence formula cannot catch this on its own because it
        # is scale-RELATIVE: confidence = 1 - rmse / (confidence_scale *
        # period), so a larger period makes the same absolute residual
        # look better. The observed failure was a reported period of
        # 6354 scan-steps (6.35 s) at confidence 0.98 on a band whose
        # true period is 700 us -- a period longer than most of the
        # recording, asserted with near-maximum confidence.
        #
        # The existing 8-hit threshold does not help: it counts hits,
        # not cycles. This counts cycles.
        self.min_cycles = min_cycles
        # Cap on the CONFIDENCE VALUE USED FOR BLENDING (never on the
        # lock decision itself -- confidence still needs to clear
        # min_confidence to lock at all; this only limits how much
        # weight a locked band's belief term loses). At confidence=1.0
        # the blend formula below gives belief ZERO weight, so the
        # scheduler trusts the periodicity model completely.
        #
        # Found necessary on real TSRD data (config_169.h5, band 1,
        # the AEGIS staggered emitter isolated to a window where it is
        # the ONLY live band): the periodicity model is exactly right
        # (confidence 1.00, period matches the file's declared PRIs to
        # the microsecond) but its Gaussian bumps are NARROW --
        # jitter_estimate floors at 0.5 steps for a genuinely single-
        # instant occurrence -- so between the 5 predicted spikes each
        # cycle, periodicity_score is near zero, and with belief's
        # weight zeroed out by full confidence, nothing tells the
        # scheduler it's fine to just KEEP dwelling on this band during
        # its own silence, since every alternative band is equally or
        # more silent (dead). Interception collapsed to 44.3% against
        # BeliefUCB's simpler "recently on -> still on" momentum
        # hitting 93.7% on the identical window -- not a detection
        # failure (confirmed: the PRI itself is exactly right), a
        # scoring-policy one: a perfectly-predictable-but-narrow signal
        # can score WORSE than a sloppier always-camp heuristic when
        # there is nothing better to switch to. (This is precisely the
        # gap a proper Whittle-index policy -- still on this project's
        # open list -- would close correctly; capping blend confidence
        # is a cheap partial mitigation, not that.)
        #
        # This is a real Pareto trade-off, not a free fix, so the
        # default (1.0) changes NOTHING and every existing result stays
        # exact: measured directly, a cap tight enough to meaningfully
        # help the above case (<=0.8) already costs the sparse-radar
        # headline (100.0%/79.4% -> 96.6%/64.3% at 0.8), and even 0.9 --
        # which preserves that headline exactly -- gives zero
        # improvement on the band-1 case (still 44.3%). There is no
        # value that helps one without costing the other; pick this per
        # deployment based on whether isolated, low-duty periodic
        # emitters or busy multi-emitter environments matter more.
        self.max_blend_confidence = max_blend_confidence
        # How many steps early to start favoring a periodic band, so that
        # if the receiver needs real settling time after a switch
        # (switch_cost_steps in run_episode), it finishes settling right
        # as the predicted pulse arrives instead of missing it entirely.
        # Found necessary by switch_cost_comparison.py: with this at 0,
        # the scheduler predicts the pulse's exact arrival time and jumps
        # to the band exactly then -- which means it's ALWAYS a fresh
        # switch (confirmed: 267 of 285 sparse-radar band-5 visits were
        # fresh switches), so it's still settling precisely when the
        # pulse hits. Set this equal to your deployment's actual
        # switch_cost_steps to fix that. Default 0 preserves every
        # existing result exactly (no lead = arrive exactly on time,
        # the original -- and for switch_cost_steps=0 in the simulator,
        # correct -- behavior).
        self.switch_lead_steps = switch_lead_steps
        self.hit_times: List[List[int]] = [[] for _ in range(n_bands)]
        self.pri_estimate: List[Optional[float]] = [None] * n_bands
        self.jitter_estimate: List[float] = [1.0] * n_bands
        self.confidence: List[float] = [0.0] * n_bands
        # Persistent (never-shrinking) estimate of how many consecutive
        # scan-steps this band's occurrences tend to stay ON for -- e.g.
        # 1 for a single-pulse radar, ~4 for a multi-step periodic burst.
        # This must be tracked separately from the transient hit_times
        # window: once periodicity locks on with a too-narrow jitter, the
        # scheduler starts abandoning bursts early (see class docstring
        # addendum below), which shortens newly-observed runs and can
        # erase the evidence of the true burst width from the sliding
        # window before the plateau fix below ever gets to use it.
        self.max_run_ever: List[int] = [1] * n_bands
        # Staggered-PRI fallback state (see _try_stagger_model /
        # _update_pri_model). Only populated for a band when the
        # single-period (uniform) model above has failed to lock AND a
        # repeating multi-value gap pattern was found instead -- e.g. a
        # radar cycling PRI1, PRI2, ..., PRIL, PRI1, ... (TSRD's own
        # PRIConfig pri_mode='Staggered', a standard ECCM technique).
        # `pri_estimate`/`confidence`/`jitter_estimate` are still the
        # fields everything else in this class (and every diagnostic
        # script) reads -- is_staggered just tells _periodicity_score
        # HOW to interpret them (many unevenly-spaced predicted points
        # per period, not one).
        self.is_staggered: List[bool] = [False] * n_bands
        self.stagger_pattern: List[Optional[List[float]]] = [None] * n_bands
        self.stagger_phase: List[Optional[int]] = [None] * n_bands
        # A SEPARATE, longer-retention hit history used only by the
        # stagger fallback -- history_len (30) is plenty for the
        # uniform model (one global least-squares fit over the whole
        # window, immune to needing an unbroken run), but a stagger fit
        # needs to separately discriminate L position-buckets, which
        # needs strictly more repeats. Measured directly on real data
        # (config_169.h5 band 1, true L=5): at 30 hits the position-
        # bucketed search picks the WRONG L (4, on a spuriously
        # near-constant small sample) with plausible-looking low
        # residual; L=5 (the correct answer, rmse=0.0 once given
        # enough data) only becomes reliably available/competitive from
        # ~50 hits onward, consistently correct from there through the
        # full window (1594 hits) tested. 300 gives comfortable margin
        # above that empirical floor without keeping unbounded history.
        self.stagger_history_len = 300
        self.stagger_min_hits = 50
        self.stagger_hit_times: List[List[int]] = [[] for _ in range(n_bands)]

    @staticmethod
    def _score_candidate(diffs, candidate, tol):
        close = sum(1 for d in diffs if abs(d - max(1, round(d / candidate)) * candidate) <= tol)
        return close / len(diffs)

    @staticmethod
    def _refine_pri(times, seed_candidate):
        """
        Fit an arithmetic progression t_i = a + b*n_i by least squares,
        where n_i = round((t_i - t_0) / seed_candidate) is each hit's
        inferred cycle index. Returns (refined_pri, rmse).

        This matters whenever the true period isn't an exact integer
        number of scan steps (e.g. a 650us PRI sampled at a 20us dwell
        is 32.5 steps) -- consecutive gaps then alternate between
        adjacent integers (32, 33, 32, 34, ...) and that rounding error
        compounds over many cycles, so a single fixed-integer-with-fixed-
        tolerance model degrades badly over a long history even though
        the emitter is perfectly periodic. Fitting the whole history at
        once recovers the fractional period precisely.
        """
        if len(times) < 4:
            return None, None
        t0 = times[0]
        ns = [round((t - t0) / seed_candidate) for t in times]
        if len(set(ns)) < 2:
            return None, None
        # Plain float division, not statistics.mean(): confirmed by
        # profiling ScanAwarePRIScheduler's multi-candidate sweep (which
        # calls this 33,836 times over just 2000 steps) that
        # statistics.mean()'s internal exact-Fraction arithmetic alone
        # accounted for 60% of total scheduler runtime here -- needless
        # precision for a least-squares score where every other term
        # (b, a, rmse) is already plain-float. Semantically identical
        # result for these inputs (list of ints/floats), just without
        # the Fraction overhead.
        n_mean = sum(ns) / len(ns)
        t_mean = sum(times) / len(times)
        den = sum((n - n_mean) ** 2 for n in ns)
        if den == 0:
            return None, None
        b = sum((n - n_mean) * (t - t_mean) for n, t in zip(ns, times)) / den
        a = t_mean - b * n_mean
        residuals = [t - (a + b * n) for n, t in zip(ns, times)]
        rmse = (sum(r * r for r in residuals) / len(residuals)) ** 0.5
        return b, rmse

    def _update_pri_model(self, band):
        """Try the single-period (uniform) model first; if it doesn't
        lock, fall back to a staggered-PRI model. See
        _try_stagger_model's docstring for why these need to be two
        separate models rather than one generalized fit: the uniform
        model's t_i = a + b*n_i has exactly one free "gap" parameter
        (b), which cannot represent an emitter whose consecutive gaps
        genuinely differ pulse to pulse by construction.

        Found necessary on real TSRD data (config_169.h5's band 1, an
        AEGIS SPY-1D with pri_mode='Staggered', 5 PRIs of 100-180us):
        the uniform model never locked at any min_cycles setting --
        against any single candidate period, dense clusters of 5
        different pulse-to-pulse gaps either collapse onto one cycle
        index (destroying the fit) or scatter across many, both giving
        huge residuals. This was never exercised by the synthetic
        stand-in, where every periodic emitter has one fixed PRI.

        is_staggered is reset to False on every call so a band that
        WAS staggered but has since re-locked onto a genuine single
        period (or lost lock entirely) doesn't keep stale stagger state
        that _periodicity_score would otherwise still read.
        """
        self.is_staggered[band] = False
        self._update_pri_model_uniform(band)
        if self.confidence[band] >= self.min_confidence:
            return  # uniform model locked -- done, no need to try stagger

        result = self._try_stagger_model(self.stagger_hit_times[band])
        if result is None or result["phase"] is None:
            # result["phase"] is None means the clean repeating run we
            # found doesn't reach the end of the hit history -- i.e.
            # something (a missed scan, a burst boundary) happened
            # between it and the most recent hit, so we can't say which
            # position in the pattern predicts the NEXT gap. Detecting
            # "this band has staggered structure" without being able to
            # predict its next occurrence isn't useful to the
            # scheduler, so this is treated the same as no lock rather
            # than reported with a guessed phase.
            return
        pattern, period = result["pattern"], result["period"]
        L = len(pattern)
        # Scale-relative confidence, same form as the uniform model's,
        # but against the average INDIVIDUAL gap (period / L) rather
        # than the full period -- rmse here is a residual on individual
        # gap values, not on a full-cycle position, so comparing it
        # against the full period would make confidence trivially high
        # regardless of fit quality (period is L times larger than the
        # scale rmse is actually measured on).
        confidence = min(1.0, max(0.0, 1.0 - result["rmse"] /
                                  (self.confidence_scale * (period / L))))
        if confidence < self.min_confidence:
            return
        self.is_staggered[band] = True
        self.stagger_pattern[band] = pattern
        self.stagger_phase[band] = result["phase"]
        self.pri_estimate[band] = period
        self.jitter_estimate[band] = max(0.5, result["rmse"], self.max_run_ever[band] / 2.0)
        self.confidence[band] = confidence

    def _try_stagger_model(self, times):
        """
        Attempt to explain `times` as a STAGGERED-PRI emitter: a small,
        fixed-length sequence of L distinct pulse-to-pulse gaps that
        repeats (gap[i] depends on i mod L, not on one fixed period) --
        as opposed to the uniform model's single fixed gap. This is a
        standard radar ECCM technique (varying PRI defeats a receiver
        that's only looking for one fixed period) and is exactly what
        TSRD's own PRIConfig(pri_mode='Staggered') generates.

        Only called from _update_pri_model AFTER the uniform model has
        already failed to lock -- a strict fallback, so it cannot cost
        anything on emitters the uniform model already handles (a
        single-PRI emitter's gaps are constant, i.e. a degenerate L=1
        "pattern" the uniform model already fits better and more
        cheaply).

        Method (SDIF-family: cluster consecutive gaps by position in a
        candidate cycle length, not by absolute value):
          1. Take RAW CONSECUTIVE gaps (not all pairwise diffs, unlike
             the uniform model -- a stagger pattern is only visible in
             the actual pulse-to-pulse sequence; pairwise diffs between
             non-adjacent hits are sums of several different individual
             gaps and don't share a common structure to cluster on).
          2. Find the longest contiguous run of "plausible intra-
             pattern" gaps (below 4x the smaller half's median) --
             excludes cross-burst silences and missed-scan artifacts,
             which are typically much larger than any individual
             stagger step.
          3. For each candidate cycle length L = 2..9: split that run
             into L position-buckets (gap[p], gap[p+L], gap[p+2L], ...)
             and require at least `min_cycles` full repeats in every
             bucket. The canonical value at position p is that
             bucket's mean; the candidate period is their sum. Residual
             = each observed gap vs. its bucket's canonical value.
          4. Pick the L with the lowest RELATIVE residual (rmse /
             period) among candidates with enough support.
          5. Determine phase: which pattern position predicts the very
             NEXT gap after times[-1]. Only defined if the winning
             clean run reaches all the way to the end of the observed
             gaps -- otherwise there's an unaccounted-for gap (a missed
             pulse, a burst boundary) between the verified pattern and
             "now", and the phase would be a guess, not a fit.

        Returns None, or a dict with keys pattern (list[float], length
        L), period (float), rmse (float), phase (int or None).
        """
        if len(times) < max(4 * self.min_cycles, self.stagger_min_hits):
            return None
        sorted_times = sorted(times)
        gaps = [sorted_times[i + 1] - sorted_times[i] for i in range(len(sorted_times) - 1)]
        if len(gaps) < 2 * self.min_cycles:
            return None

        small_half = sorted(gaps)[: max(1, len(gaps) // 2)]
        scale = statistics.median(small_half)
        if scale <= 0:
            return None

        # Floor on the SMALLEST canonical pattern value, derived from
        # the longest run of literally-adjacent (gap==1) hits in this
        # window -- the SAME degenerate-fit guard the uniform model
        # already has (its min_candidate = max(8, 2*max_run)), which I
        # initially failed to carry over here.
        #
        # Found the hard way, on the SYNTHETIC beacon scenario (not
        # real data): a densely-scanned Markov band (comm-1,
        # p_on_given_on=0.9) that the scheduler dwells on for many
        # consecutive steps produces a long run of gap==1 values, which
        # trivially "fits" pattern=[1,1] (period=2) with rmse=0.0,
        # confidence=1.000 -- a textbook false positive, not detecting
        # real 2-value stagger structure, just describing "this band
        # tends to stay on." Confirmed directly: this cost -6.6pp to
        # -19.5pp on the beacon scenario across every min_cycles value
        # tried, and was NOT fixed by min_cycles (which counts cycles,
        # not gap magnitude -- a dense sticky band has plenty of
        # "cycles" of a fake period=2).
        #
        # A blind reuse of the uniform model's exact min_candidate
        # formula (hardcoded floor of 8) is WRONG here: it would also
        # reject config_169.h5's real stagger pattern (individual PRIs
        # of 5-9 scan-steps, legitimately below 8). The right floor is
        # relative to how DENSE this specific band's scanning has been,
        # same principle as the uniform model, different scale: real
        # stagger positions are never adjacent scan-steps (min PRI on
        # config_169's band 1 is 5 steps > 1, so its own max_run stays
        # at 1, giving a floor of only 2) while a sticky Markov band's
        # max_run climbs into the tens, correctly excluding it.
        stagger_max_run, run_len = 1, 1
        sorted_times = sorted(times)
        for a, b in zip(sorted_times[:-1], sorted_times[1:]):
            run_len = run_len + 1 if b - a == 1 else 1
            stagger_max_run = max(stagger_max_run, run_len)
        min_pattern_value = max(2, 2 * stagger_max_run)

        # Longest contiguous run of gaps <= scale * stagger_gap_ceiling,
        # tracked by [start, end) INDEX into `gaps` so we can tell
        # afterwards whether it reaches the very end (needed for phase,
        # see docstring).
        #
        # stagger_gap_ceiling=2.0 (not the much looser 4x used
        # elsewhere in this file for excluding cross-burst gaps) was
        # chosen from real data: on config_169.h5's band 1 (AEGIS
        # SPY-1D, 5-value stagger, PRIs 100-180us = 5-9 scan-steps at
        # dwell=20us), the true per-position gaps and the genuine
        # missed-pulse gaps are NOT well separated at 4x scale (~28
        # steps) -- real missed-pulse gaps start around 11 steps, only
        # ~1.5x the largest canonical value (9), so a 4x ceiling lets
        # ~15% of gaps through as spurious "clean" data, which corrupts
        # the position-bucket means enough that L detection picks the
        # wrong cycle length. At 2x scale (~14 steps here), measured
        # directly on this file: 92.5% of gaps are genuine single-
        # position values and the ceiling correctly excludes nearly all
        # of the rest.
        stagger_gap_ceiling = 2.0
        best_start, best_end, cur_start = 0, 0, 0
        for i, g in enumerate(gaps):
            if g > scale * stagger_gap_ceiling:
                cur_start = i + 1
            if i - cur_start + 1 > best_end - best_start:
                best_start, best_end = cur_start, i + 1
        run = gaps[best_start:best_end]
        if len(run) < 2 * self.min_cycles:
            return None

        best = None  # (L, pattern, rmse, rel)
        for L in range(2, 10):
            if len(run) < L * self.min_cycles:
                continue
            positions = [run[p::L] for p in range(L)]
            if any(len(p) < self.min_cycles for p in positions):
                continue
            # Plain float division here too -- see _refine_pri's comment;
            # same needless statistics.mean() Fraction overhead, lower
            # call volume in this path but the same fix.
            pattern = [sum(p) / len(p) for p in positions]
            if min(pattern) < min_pattern_value:
                continue
            period = sum(pattern)
            if period <= 0:
                continue
            residuals = [v - pattern[i % L] for i, v in enumerate(run)]
            rmse = (sum(r * r for r in residuals) / len(residuals)) ** 0.5
            rel = rmse / period
            if best is None or rel < best[3]:
                best = (L, pattern, rmse, rel)

        if best is None:
            return None
        L, pattern, rmse, _rel = best
        period = sum(pattern)

        # Phase resolution is deliberately a SEPARATE step from pattern
        # discovery above, against ALL of `times` rather than just the
        # clean run.
        #
        # First version of this tied phase directly to whether the
        # clean run reached the end of `gaps` -- correct when it did,
        # but on real data (config_169.h5 band 1) it essentially never
        # did: with min_cycles=4 requiring long runs, the LONGEST clean
        # run in a window is frequently an INTERIOR segment (there's
        # almost always a slightly-larger real gap -- a genuine
        # occasional missed pulse, confirmed directly: ~7.5% of this
        # emitter's true consecutive gaps are irregular -- somewhere
        # after the best segment but before times[-1]), so phase came
        # back None on every window size tried (30 up to 500 hits)
        # even though the pattern itself was found exactly right
        # (rmse=0.0, matching the file's declared PRIs precisely).
        #
        # _resolve_stagger_phase instead fits a REPEATING NON-UNIFORM
        # GRID (built from the now-known pattern) against every
        # observed time via nearest-grid-point residual, not requiring
        # unbroken contiguity -- a handful of missed pulses just cost
        # a few grid points' worth of residual, they don't break phase
        # tracking for everything downstream the way an index-based
        # walk would.
        phase, phase_rmse = self._resolve_stagger_phase(sorted_times, pattern)

        return {"pattern": pattern, "period": period, "rmse": max(rmse, phase_rmse),
                "phase": phase}

    @staticmethod
    def _resolve_stagger_phase(times, pattern):
        """Given an already-validated stagger `pattern`, find which
        pattern position predicts the gap from times[-1] to the NEXT
        hit, by fitting a repeating non-uniform grid (the pattern's
        cumulative offsets, tiled) against every observed time and
        picking whichever of the L possible starting phases gives the
        lowest nearest-grid-point residual. See _try_stagger_model's
        docstring for why this needs to be separate from pattern
        discovery. Returns (phase, rmse).
        """
        L = len(pattern)
        period = sum(pattern)
        t0 = times[0]
        span = max(1.0, times[-1] - t0)
        n_cycles = int(span / period) + 2

        best_phase, best_err = 0, None
        for p0 in range(L):
            grid = []
            acc = 0.0
            idx = p0
            for _ in range(n_cycles * L):
                grid.append(t0 + acc)
                acc += pattern[idx % L]
                idx += 1
            sq_err, gi = 0.0, 0
            for t in times:
                while gi + 1 < len(grid) and abs(grid[gi + 1] - t) <= abs(grid[gi] - t):
                    gi += 1
                sq_err += (grid[gi] - t) ** 2
            err = (sq_err / len(times)) ** 0.5
            if best_err is None or err < best_err:
                best_phase, best_err = p0, err

        # Walk the winning grid forward from t0 to find which cycle
        # position times[-1] itself landed nearest to, then the pattern
        # index one further is what predicts the NEXT gap.
        acc, idx, last_idx = 0.0, best_phase, best_phase
        while t0 + acc <= times[-1] + pattern[idx % L] / 2.0:
            last_idx = idx
            acc += pattern[idx % L]
            idx += 1
        return (last_idx + 1) % L, best_err

    def _update_pri_model_uniform(self, band):
        times = self.hit_times[band]
        if len(times) < 8:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return
        # PRI histogramming (a standard ESM technique): take ALL pairwise
        # time differences between recent hits (using raw hits, not just
        # burst onsets, gives more data points and avoids misclassifying
        # a mid-burst re-scan as a "new" onset). A fixed absolute
        # tolerance (not one that scales with the candidate) is used when
        # checking whether a diff is an integer multiple of a candidate
        # period -- a tolerance that scales with the candidate lets tiny
        # candidates trivially "explain" almost anything by chance.
        diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]

        # Guard against a subtle false positive: once the scheduler locks
        # onto a band it likes, it may scan several consecutive steps in a
        # row. A dense run of consecutive integers trivially contains
        # "multiples" of almost any small candidate just by combinatorics
        # (e.g. the run 100..110 contains diffs of 2, 3, 4... up to 10),
        # which can look like false periodicity for an emitter that's
        # just persistently on, not actually cyclic. Ignore any candidate
        # period small enough to be explained by the densest run of
        # back-to-back hits observed.
        max_run = 1
        run = 1
        sorted_times = sorted(times)
        for a, b in zip(sorted_times[:-1], sorted_times[1:]):
            run = run + 1 if b - a == 1 else 1
            max_run = max(max_run, run)
        self.max_run_ever[band] = max(self.max_run_ever[band], max_run)
        min_candidate = max(8, 2 * max_run)

        candidate_pool = [d for d in diffs if d >= min_candidate]
        if not candidate_pool:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return

        # Candidate periods to test, from two complementary methods:
        #  1) GCD of all diffs -- exact and immediate when diffs are
        #     (near) noise-free integer multiples of the true period,
        #     which a pure mode/frequency count can miss badly if the
        #     most common diff happens to be a large multiple (e.g. 168
        #     instead of 12) rather than the period itself.
        #  2) The pairwise mode and its small-integer divisors -- more
        #     robust when there's timing jitter, where an exact GCD
        #     would collapse to 1.
        candidates = set()
        g = reduce(math.gcd, diffs)
        if g >= min_candidate:
            candidates.add(g)
        mode_candidate, _freq = Counter(candidate_pool).most_common(1)[0]
        candidates.add(mode_candidate)
        for k in (2, 3, 4, 5, 6, 7, 8):
            sub = round(mode_candidate / k)
            if sub >= min_candidate:
                candidates.add(sub)

        # Also test each candidate's immediate integer neighbors
        # (+-1). Found via a real failing case (a PDW seed where the
        # true period was 32.5 steps, but the pairwise-diff mode came
        # out as 33): an off-by-one seed candidate isn't just "slightly
        # wrong" -- the n_i = round((t-t0)/candidate) index used by
        # _refine_pri can pick up a ROUNDING COLLISION (two genuinely
        # different hits mapping to the same cycle index) once the
        # seed's error accumulates across enough cycles, which inflates
        # that candidate's residual far more than a 1-step error would
        # suggest (confirmed directly: candidate 33 gave rel error
        # 0.229, candidate 34 gave 0.255, but the untried candidate 32
        # gave 0.029 -- neither the mode, gcd, nor any submultiple of
        # the mode ever generated 32 as a candidate at all). Testing
        # neighbors costs little (the refine+RMSE step is what actually
        # discriminates) and directly covers this failure mode.
        for c in list(candidates):
            for neighbor in (c - 1, c + 1):
                if neighbor >= min_candidate:
                    candidates.add(neighbor)

        # Refine EVERY candidate via least-squares and pick whichever
        # yields the best RELATIVE fit (rmse / refined_pri) -- not
        # whichever scores best on the coarse tol=1 exact-multiple test.
        # That coarse test is only a rough screen: when the true period
        # isn't an integer (real jitter, or a fractional PRI-vs-dwell
        # ratio) and GCD-of-diffs collapses to 1, a harmonic of the true
        # period can score BETTER on the coarse test for a given noise
        # draw than the true fundamental does (found via
        # diagnose_beacon_regression-style inspection on a PDW seed that
        # locked onto ~65 instead of ~32.5 this way). The refined fit's
        # own residual is a much more sensitive, appropriate discriminator
        # for a fractional period than a binary in/out-of-tolerance test.
        best_base, best_rmse, best_rel = None, None, None
        for c in candidates:
            refined, rmse = self._refine_pri(sorted_times, c)
            if refined is None or rmse is None or refined < min_candidate * 0.5:
                continue
            rel = rmse / refined
            if best_rel is None or rel < best_rel:
                best_base, best_rmse, best_rel = refined, rmse, rel

        if best_base is None:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return
        refined_pri, rmse = best_base, best_rmse

        if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return

        # Cycle-count guard (see self.min_cycles in __init__): how many
        # DISTINCT cycles of the winning period did we actually observe?
        # Dense bursts can supply many hits across very few cycles, and
        # a fit through 2 cycle-clusters is a fit through 2 points.
        n_cycles = len({round((t - sorted_times[0]) / refined_pri) for t in sorted_times})
        if n_cycles < self.min_cycles:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0
            return

        confidence = min(1.0, max(0.0, 1.0 - rmse / (self.confidence_scale * refined_pri)))
        if confidence >= self.min_confidence:
            self.pri_estimate[band] = refined_pri
            # Floor jitter at half the largest observed consecutive-hit
            # run, not just the fit residual -- a burst that stays ON
            # for `max_run_ever` steps needs the phase bump to plateau
            # across roughly that width, or the scheduler abandons the
            # burst after its first step (see class docstring).
            self.jitter_estimate[band] = max(0.5, rmse, self.max_run_ever[band] / 2.0)
            self.confidence[band] = confidence
        else:
            self.pri_estimate[band] = None
            self.confidence[band] = 0.0

    def _stagger_distance(self, band, t, last):
        """Circular distance from t to the nearest predicted pulse under
        a staggered-PRI model. Unlike the uniform model -- one predicted
        point per period, so a plain mod suffices -- a stagger pattern
        has L unevenly-spaced predicted points per period, so the
        nearest one is found by minimum over all L candidates (checked
        both within this cycle and one cycle back, to handle wraparound
        correctly for a point near the cycle boundary)."""
        pattern = self.stagger_pattern[band]
        L = len(pattern)
        phase0 = self.stagger_phase[band]
        period = sum(pattern)
        offsets = []
        acc = 0.0
        for i in range(L):
            acc += pattern[(phase0 + i) % L]
            offsets.append(acc)  # offsets[-1] == period (one full cycle from `last`)
        elapsed = (t - last) % period
        candidates = offsets + [o - period for o in offsets]
        return min(abs(elapsed - o) for o in candidates)

    def _periodicity_score(self, band, t):
        pri = self.pri_estimate[band]
        if pri is None or self.confidence[band] <= 0 or not self.hit_times[band]:
            return 0.0
        last = self.hit_times[band][-1]
        if self.is_staggered[band] and self.stagger_pattern[band] and self.stagger_phase[band] is not None:
            dist = self._stagger_distance(band, t, last)
        else:
            phase = (t - last) % pri
            dist = min(phase, pri - phase)
        # Plateau the score across a window of width switch_lead_steps on
        # EITHER side of the predicted instant, rather than the original
        # single-point peak. A first attempt just shifted the whole score
        # curve forward by switch_lead_steps (checking phase against
        # t+lead) -- that only moves WHERE the peak sits, it doesn't
        # widen it, so by the time t reaches the real arrival the score
        # is already past its (now-early) peak and declining, and gets
        # outscored by a loud always-on band exactly when it matters
        # (confirmed directly: with lead=1, the scheduler switched to
        # band 5 one step early as intended, got blocked settling, then
        # abandoned band 5 for band 1 on the very next step -- the real
        # arrival instant -- losing the pulse anyway). Flooring the
        # distance at (dist - switch_lead_steps) instead makes the score
        # sit at its maximum for the whole [predicted-lead, predicted]
        # window, so switching in early and then STAYING through the
        # real arrival is what actually gets rewarded.
        dist = max(0.0, dist - self.switch_lead_steps)
        sigma = self.jitter_estimate[band]
        return math.exp(-(dist ** 2) / (2 * sigma ** 2))

    def choose_bands(self, k):
        self.t += 1
        if self.t <= self.warmup_steps:
            for b in range(self.n_bands):
                self._propagate(b)
            return self._warmup_bands(k)
        for b in range(self.n_bands):
            self._propagate(b)
        scores = []
        for b in range(self.n_bands):
            ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
            conf = min(self.confidence[b], self.max_blend_confidence)
            periodic = self._periodicity_score(b, self.t)
            blended = (1 - conf) * self.belief[b] + conf * self.periodicity_weight * periodic
            scores.append(self.priority[b] * blended + ucb_bonus)
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
        return order[:k]

    def update(self, band, observed_on):
        super().update(band, observed_on)
        if observed_on:
            times = self.hit_times[band]
            times.append(self.t)
            if len(times) > self.history_len:
                del times[0]
            stagger_times = self.stagger_hit_times[band]
            stagger_times.append(self.t)
            if len(stagger_times) > self.stagger_history_len:
                del stagger_times[0]
            self._update_pri_model(band)


def run_comparison():
    n_bands = 36
    n_steps = 4000
    scenario = make_scenario(n_bands)

    print(f"Scenario: {n_bands} bands, {n_steps} steps, 4 concurrent emitters "
          f"(2 Markov comms, 1 periodic beacon [bands 2,5,6 -- true period 12 steps], "
          f"1 frequency-agile threat)\n")

    for k in (1, 2):
        random.seed(7)
        print(f"--- k_channels = {k} ---")
        schedulers = {
            "RoundRobin (open-loop baseline)": RoundRobinScheduler(n_bands),
            "BeliefUCB (Markov-only, learned)": BeliefUCBScheduler(n_bands, ucb_c=0.5),
            "PRIAware (Markov + periodicity, learned)": PRIAwareScheduler(n_bands, ucb_c=0.5),
        }
        header = (f"{'Scheduler':42s} | {'Interception %':>15s} | "
                  f"{'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}")
        print(header)
        print("-" * len(header))
        for name, sched in schedulers.items():
            stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
            r = stats.report()
            print(f"{name:42s} | {r['interception_ratio']*100:14.1f}% | "
                  f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")
        print()

    # Diagnostic: did it actually learn the true beacon period?
    random.seed(7)
    pri_sched = PRIAwareScheduler(n_bands, ucb_c=0.5)
    run_episode(scenario, pri_sched, n_steps, n_bands, k_channels=1)
    print("PRI diagnostic (true beacon period = 12 steps, on bands 2/5/6):")
    for b in (2, 5, 6):
        pri, conf = pri_sched.pri_estimate[b], pri_sched.confidence[b]
        if pri is not None:
            print(f"  band {b} (beacon):        estimated PRI = {pri:5.1f}  confidence = {conf:.2f}")
        else:
            print(f"  band {b} (beacon):        not enough hits observed yet")
    for b in (1, 4, 0, 3, 7):
        pri, conf = pri_sched.pri_estimate[b], pri_sched.confidence[b]
        if pri is not None:
            print(f"  band {b} (comm/agile):    estimated PRI = {pri:5.1f}  confidence = {conf:.2f}  (should stay low)")
        else:
            print(f"  band {b} (comm/agile):    not enough hits observed yet")


def run_sparse_comparison():
    n_bands = 36
    n_steps = 4000
    warmup = 800   # brief open-loop sweep so the sparse radar gets enough
                   # early samples for the PRI estimator to lock on (see
                   # module docstring / write-up: this is a real
                   # exploration/exploitation trade-off, not free)
    scenario = make_sparse_scenario(n_bands)

    print(f"Sparse scenario: {n_bands} bands, {n_steps} steps ({warmup}-step warmup) -- a "
          f"single-pulse-per-cycle fixed-PRI radar (band 5, true period 12 steps, ON for "
          f"just 1 step per cycle) alongside 2 Markov comms + 1 agile threat\n")

    for k in (1, 2):
        random.seed(11)
        print(f"--- k_channels = {k} ---")
        schedulers = {
            "RoundRobin (open-loop baseline)": RoundRobinScheduler(n_bands),
            "BeliefUCB (Markov-only, learned)": BeliefUCBScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
            "PRIAware (Markov + periodicity, learned)": PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
        }
        header = (f"{'Scheduler':42s} | {'Interception %':>15s} | "
                  f"{'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}")
        print(header)
        print("-" * len(header))
        for name, sched in schedulers.items():
            stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
            r = stats.report()
            print(f"{name:42s} | {r['interception_ratio']*100:14.1f}% | "
                  f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")
        print()

    print("The blended interception % above can be misleading here -- it's dominated by\n"
          "the loud, near-always-on comm-1 channel. What actually matters for an EW system\n"
          "is PER-EMITTER capture, especially of the one threat that's genuinely hard to\n"
          "predict without a periodicity model:\n")

    def per_emitter_capture(sched_cls, warmup):
        random.seed(11)
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
        return radar_pulses, radar_caught, comm1_on, comm1_caught, sched

    for name, cls in [("BeliefUCB", BeliefUCBScheduler), ("PRIAware", PRIAwareScheduler)]:
        rp, rc, cp, cc, sched = per_emitter_capture(cls, warmup)
        pri = getattr(sched, "pri_estimate", [None] * n_bands)[5]
        conf = getattr(sched, "confidence", [0.0] * n_bands)[5]
        print(f"  {name:10s}: fixed-PRI radar caught {rc:4d}/{rp} ({100*rc/rp:5.1f}%)   "
              f"comm-1 caught {cc:4d}/{cp} ({100*cc/cp:5.1f}%)   "
              f"[band5 estimated PRI={pri}, confidence={conf:.2f}]")


if __name__ == "__main__":
    run_comparison()
    print("=" * 100)
    run_sparse_comparison()
