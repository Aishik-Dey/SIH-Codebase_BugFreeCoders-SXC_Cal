"""
scan_aware_scheduler.py
=========================
Extends PRIAwareScheduler to handle SpatiallyScanningEmitter targets,
where a single band shows TWO independent periodicities nested inside
each other: a fast intra-burst PRI (pulses while the beam is on us) and
a slow inter-burst scan_period (when the beam comes back around). The
base PRIAwareScheduler models one periodicity per band; feeding it a
scanning emitter's hit stream directly would make it try to fit a
single period to a bimodal gap distribution, and -- since it selects
whichever candidate gets the tightest least-squares fit -- it would
most likely lock onto the tight, well-fit intra-burst PRI and stay
structurally blind to the much larger scan_period, meaning it could
only ever "stumble into" a beam pass, never predict one.

This scheduler tracks the two periodicities as separate estimates with
separate confidences:
  - scan_confidence / scan_period_estimate  -- when does the NEXT BURST
    start (from burst-onset times)
  - pri_confidence / pri_estimate           -- once inside a predicted
    burst window, when's the next PULSE within it (from gaps between
    hits inside the same burst)

Both burst segmentation AND scan_period fitting went through real,
found-not-assumed failure modes worth stating plainly:

  1. Burst segmentation originally split on the largest ratio jump
     between sorted consecutive-hit gaps ("gap in the gaps"), which
     looked scale-agnostic but broke down under sparse, self-selected
     scanning (the receiver doesn't catch every pulse of every beam
     pass): consecutive detected onsets jitter enough that the ratio
     heuristic sometimes merged two real bursts into one. Fixed by
     seeding a robust intra-burst PRI estimate FIRST
     (_robust_intra_burst_pri_seed), then splitting on a FIXED multiple
     of that seed instead of guessing the split point from noisy local
     gap statistics. The old ratio-jump method is kept only as a
     cold-start fallback for when there isn't yet enough data to seed
     a PRI at all.

  2. scan_period fitting originally used naive adjacent-onset-gap
     median/stdev, gated by a raw coefficient-of-variation threshold.
     That fails for exactly the reason the base class's PRI model
     already had to solve: whenever the scheduler misses an ENTIRE
     rotation (never scans the band during that beam pass), the
     resulting onset-to-onset gap is a MULTIPLE of the true
     scan_period, not the period itself -- inflating apparent variance
     even though the underlying signal is perfectly periodic. Fixed by
     reusing the exact same GCD/mode/submultiple candidate search +
     least-squares refinement the base class uses for PRI
     (_search_best_period, shared by both tiers), which is precisely
     the technique built to handle missed-cycle multiples.

Downstream gating (min_bursts, burst-size consistency, and the
refined-fit confidence threshold) is the actual safety net against
false periodicity locks on genuinely non-periodic bands -- found
directly during testing: with looser gates, an AgileEmitter band (no
real periodicity at all) reached scan_confidence=0.93 from spurious
least-squares overfitting on too few burst onsets.

The combined periodicity score is burst_score * pri_score: burst_score
alone gates broad interest in a band (no point favoring it at all
outside a predicted burst window), and pri_score sharpens WITHIN that
window once enough intra-burst pulses have been seen to fit a PRI --
before that, pri_score defaults to 1.0 so early bursts aren't
suppressed just because fine-grained PRI hasn't locked yet.

Run:  python3 scan_aware_scheduler.py
"""

import math
import statistics
from collections import Counter
from functools import reduce
from typing import List, Optional

from scan_scheduler_v3_pri import PRIAwareScheduler


class ScanAwarePRIScheduler(PRIAwareScheduler):
    def __init__(self, n_bands, ucb_c: float = 0.5, history_len: int = 60,
                 min_confidence: float = 0.75, periodicity_weight: float = 1.0,
                 warmup_steps: int = 0, priority: Optional[List[float]] = None,
                 confidence_scale: float = 0.25, switch_lead_steps: int = 0,
                 warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1,
                 min_gap_ratio: float = 3.0, min_burst_hits: int = 2,
                 min_bursts: int = 5, min_burst_size_consistency: float = 0.5,
                 min_scan_to_pri_ratio: float = 3.0, period_agreement_tol: float = 0.05,
                 beam_dwell_sigma_divisor: float = 3.0):
        super().__init__(n_bands, ucb_c=ucb_c, history_len=history_len,
                          min_confidence=min_confidence, periodicity_weight=periodicity_weight,
                          warmup_steps=warmup_steps, priority=priority,
                          confidence_scale=confidence_scale, switch_lead_steps=switch_lead_steps,
                          warmup_dwell_steps=warmup_dwell_steps,
                          warmup_dwell_jitter=warmup_dwell_jitter)
        # Cold-start-only fallback split (see module docstring point 1).
        self.min_gap_ratio = min_gap_ratio
        self.min_burst_hits = min_burst_hits
        # A least-squares fit trivially finds a near-perfect line
        # through almost any handful of points -- this must be high
        # enough that a spurious segmentation of non-periodic noise
        # doesn't get enough "onsets" to overfit confidently (found
        # directly: min_bursts=3 let an AgileEmitter band reach
        # scan_confidence=0.93). Mirrors the base class's len(times)<8
        # gate before it even attempts a PRI fit.
        self.min_bursts = min_bursts
        # A real rotating scanner illuminates for roughly the same
        # number of pulses each pass; bursty/agile noise split by the
        # segmentation heuristic tends to produce wildly uneven "burst"
        # sizes -- reject those before ever attempting a period fit.
        # (Fraction of bursts required within +-1 of the median size;
        # see _evaluate_burst_split for why raw CoV is the wrong
        # statistic here.)
        self.min_burst_size_consistency = min_burst_size_consistency
        # A genuine OUTER period must be substantially larger than the
        # inner PRI seed it was segmented against -- otherwise the
        # "outer" search has just degenerated into rediscovering the
        # same small-scale structure twice. Found directly: once the
        # scheduler over-commits scan time to a band, occasional
        # sidelobe-leak hits caught DURING the dead window (now that
        # it's scanning continuously, not just during true bursts)
        # pollute the pairwise-diff pool with extra small-scale
        # samples, dragging scan_period_estimate back down to equal
        # pri_estimate (confirmed: scan_period locked to 3.0, the same
        # as the true inner PRI, with scan_confidence=1.00 and 90% of
        # all scan time then dumped onto that one band). This ratio
        # check is a cheap, principled guard against that self-
        # reinforcing runaway, without needing to filter sidelobe
        # leaks explicitly.
        self.min_scan_to_pri_ratio = min_scan_to_pri_ratio

        self.burst_starts: List[List[int]] = [[] for _ in range(n_bands)]
        self.scan_period_estimate: List[Optional[float]] = [None] * n_bands
        self.scan_jitter_estimate: List[float] = [1.0] * n_bands
        self.scan_confidence: List[float] = [0.0] * n_bands
        self.pri_confidence: List[float] = [0.0] * n_bands
        # Persistent (never-shrinking) estimate of burst width in steps,
        # same rationale as PRIAwareScheduler.max_run_ever: widens the
        # burst_score plateau so the scheduler doesn't abandon a burst
        # partway through once locked on.
        self.beam_dwell_estimate: List[int] = [1] * n_bands
        # Lock-stability gate for scan_period_estimate (see
        # _update_scan_model): a single _evaluate_burst_split fit is
        # NOT enough to trust, however good its own RMSE looks --
        # found directly (seeds 1 and 5 of the mixed scenario): a
        # corrupted pri_seed at cold start produced a one-off spurious
        # fit (scan_period=89.7 against a true 40) that got published
        # immediately, and then self-reinforced, because the beam_dwell
        # sane_cap in _update_intra_burst_state is itself scaled off
        # scan_period_estimate -- a bad first lock loosens the cap that
        # was supposed to catch further bad spans. Requiring the NEXT
        # independent fit (one call later, over the then-larger hit
        # history) to land within period_agreement_tol of this one
        # before publishing either is a cheap, principled way to reject
        # one-off overfits without needing a hardcoded "sanity" period
        # the scheduler has no ground truth to derive.
        self.period_agreement_tol = period_agreement_tol
        self._pending_period: List[Optional[float]] = [None] * n_bands
        self._pending_pri_seed: List[Optional[float]] = [None] * n_bands
        self._trusted_pri_seed: List[Optional[float]] = [None] * n_bands
        # beam_dwell_estimate is a never-shrinking MAX over noisy
        # per-pass spans, so it systematically drifts toward the upper
        # tail of the true dwell's natural variation, not its center --
        # confirmed directly across seeds (stabilizing at 13, 10, 7
        # against a true beam_dwell_steps=6). Dividing by more than 2
        # compensates for that known upward bias when turning it into a
        # gaussian sigma, tightening the high-interest window back
        # toward the actual illumination time instead of padding it.
        self.beam_dwell_sigma_divisor = beam_dwell_sigma_divisor

    @staticmethod
    def _search_best_period(times, refine_pri_fn, min_candidate=1):
        """Shared robust period search: GCD + mode + small-integer
        submultiples + immediate neighbors of the pairwise-diff pool,
        each refined via least squares, best RELATIVE fit wins. Used
        for both the intra-burst PRI seed and the inter-burst
        scan_period, so both get the same protection against "a missed
        cycle produces a gap that's a multiple of the true period, not
        the period itself" -- which naive adjacent-gap median/stdev
        does not handle."""
        if len(times) < 4:
            return None, None
        diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]
        diffs = [d for d in diffs if d >= min_candidate]
        if not diffs:
            return None, None
        g = reduce(math.gcd, diffs)
        mode_candidate, _freq = Counter(diffs).most_common(1)[0]
        candidates = {c for c in (g, mode_candidate) if c >= min_candidate}
        for k in (2, 3, 4, 5, 6, 7, 8):
            sub = round(mode_candidate / k)
            if sub >= min_candidate:
                candidates.add(sub)
        for c in list(candidates):
            for neighbor in (c - 1, c + 1):
                if neighbor >= min_candidate:
                    candidates.add(neighbor)
        best_period, best_rmse, best_rel = None, None, None
        for c in candidates:
            refined, rmse = refine_pri_fn(times, c)
            if refined is None or rmse is None or refined < min_candidate * 0.5:
                continue
            rel = rmse / refined
            if best_rel is None or rel < best_rel:
                best_period, best_rmse, best_rel = refined, rmse, rel
        return best_period, best_rmse

    def _robust_intra_burst_pri_seed(self, times):
        """Rough estimate of the intra-burst spacing scale, used ONLY to
        set a burst-segmentation threshold -- not the final per-burst
        PRI (that's fit separately, per burst, once segmentation is
        clean). A cluster of n nearby hits contributes O(n^2) pairwise
        diffs at the intra-burst scale, while there are only
        O(#bursts) diffs anywhere near the inter-burst scale, so the
        dominant small-scale structure in _search_best_period's result
        is overwhelmingly intra-burst even with zero segmentation done
        yet -- this is what avoids the chicken-and-egg problem of
        needing clean bursts to find PRI and needing PRI to find clean
        bursts."""
        period, _rmse = self._search_best_period(times, self._refine_pri, min_candidate=1)
        return period

    @staticmethod
    def _segment_bursts_ratio(times, min_gap_ratio):
        """Cold-start fallback: split on the largest ratio jump between
        sorted consecutive-hit gap values. Only used before enough data
        exists to seed a PRI (see _segment_bursts_fixed for the
        normal path)."""
        if len(times) < 2:
            return [list(times)] if times else []
        gaps = sorted(set(b - a for a, b in zip(times[:-1], times[1:]) if b > a))
        split_value = None
        if len(gaps) >= 2:
            best_ratio = min_gap_ratio
            for g1, g2 in zip(gaps[:-1], gaps[1:]):
                ratio = g2 / g1
                if ratio >= best_ratio:
                    best_ratio, split_value = ratio, (g1 + g2) / 2.0
        if split_value is None:
            return [list(times)]
        return ScanAwarePRIScheduler._segment_bursts_fixed(times, split_value)

    @staticmethod
    def _segment_bursts_fixed(times, split_value):
        bursts = [[times[0]]]
        for prev, cur in zip(times[:-1], times[1:]):
            if cur - prev > split_value:
                bursts.append([cur])
            else:
                bursts[-1].append(cur)
        return bursts

    def _update_scan_model(self, band):
        times = self.hit_times[band]

        raw_seed = self._robust_intra_burst_pri_seed(times)
        # Stability-gate the SEED itself, one level upstream of the
        # scan_period lock-stability gate below. Found directly (seed 7
        # of the mixed scenario): pri_seed can be wrong (39, a harmonic
        # of the OUTER period, not the true inner PRI of 3) and stay
        # *consistently* wrong call after call -- not a one-off outlier
        # but a systematic bias. Since it's consistent, it drives the
        # SAME wrong multiplier sweep on consecutive calls and produces
        # two consecutive outer-period fits (~482) that agree with each
        # other, which is exactly what the scan_period_estimate
        # stability gate below was trusting as "real". Requiring the
        # seed to reproduce itself across two independent calls before
        # it's allowed to drive segmentation at all catches the
        # corruption at its origin instead of downstream, where two
        # gates can each individually look satisfied while both are
        # being fed the same bad input.
        pending_seed = self._pending_pri_seed[band]
        if raw_seed is not None and raw_seed >= 1:
            if (pending_seed is not None and pending_seed >= 1
                    and abs(raw_seed - pending_seed) <= self.period_agreement_tol * pending_seed):
                self._trusted_pri_seed[band] = raw_seed
            # else: leave the existing trusted seed (possibly None)
            # alone -- don't jump to a single disagreeing new estimate.
            self._pending_pri_seed[band] = raw_seed
        pri_seed = self._trusted_pri_seed[band]

        if pri_seed is None or pri_seed < 1:
            # Too little data to seed a PRI yet -- cold-start fallback.
            bursts = self._segment_bursts_ratio(times, self.min_gap_ratio)
            best = self._evaluate_burst_split(band, bursts, pri_seed)
        else:
            # A single fixed split multiplier is fragile when beam_dwell
            # is only a few multiples of PRI (missing just 1-2 intra-
            # burst pulses can push a real gap past a tight threshold,
            # wrongly splitting one true burst into two -- confirmed
            # directly: 2.5x split pri=3 into bursts whose onset gaps
            # were STILL all clean multiples of 3, degenerating the
            # outer fit right back to 3). Try a spread of multipliers
            # and let whichever produces the best-fitting, non-
            # degenerate outer period win -- same "search candidates,
            # keep the best fit" approach used everywhere else here.
            best = None
            # Multipliers capped at 6.0: wider ones (9.0, 13.0, tried in
            # earlier iterations of this fix) produce split thresholds
            # that can approach or exceed the true inter-pass gap for
            # realistic period/dwell ratios, which merges consecutive
            # beam passes into one "burst" by construction -- found
            # directly (seed 16): mult=13.0 against pri_seed=3 gave a
            # split of 39 against a true period of 40, guaranteeing
            # merges. A period-aware exclusion bound was tried instead
            # of trimming the list, but it created a worse failure: once
            # scan_period_estimate freezes on any value (even one
            # already rejected back to scan_confidence=0.0), the bound
            # derived from that frozen value can end up excluding every
            # multiplier including the smallest, permanently starving
            # the sweep (found directly, seed 0: 90 scans total in an
            # 8000-step episode, then silence). Missing 1-2 intra-burst
            # pulses -- the reason a spread of multipliers exists at
            # all -- only needs a modest margin above 2x PRI; 6.0x
            # already covers missing several consecutive pulses without
            # ever approaching a realistic period.
            for mult in (2.0, 2.5, 3.0, 4.0, 6.0):
                bursts = self._segment_bursts_fixed(times, pri_seed * mult)
                result = self._evaluate_burst_split(band, bursts, pri_seed)
                if result is not None and (best is None or result[-1] < best[-1]):
                    best = result

        if best is None:
            self.scan_confidence[band] = 0.0
            # self.confidence[band] (read by the inherited choose_bands)
            # must be kept in sync with scan_confidence here too, not
            # just on the success path below -- found directly (seed 11
            # of the mixed scenario): without this line, a stale
            # self.confidence left over from an earlier successful
            # round (e.g. 1.0 from a since-rejected false lock) stays
            # frozen forever once _update_scan_model starts taking this
            # early-return branch every time. choose_bands' blended
            # score is (1-conf)*belief + conf*periodicity_weight*
            # periodic; with conf stuck at 1.0 and periodic correctly
            # at 0.0 (periodicity_score does read the fresh
            # scan_confidence), BOTH terms of blended collapse to zero
            # -- not just underweighted, entirely zeroed -- so the band
            # only ever scores from its raw UCB exploration bonus. That
            # silently starves scan_count for the rest of the episode
            # (confirmed: 63 scans total across 8000 steps) with no
            # visible sign in scan_confidence, which correctly read 0.0
            # the whole time -- the bug was in a value nothing else
            # was checking.
            self.confidence[band] = 0.0
            self.burst_starts[band] = []
            # For intra-burst PRI/beam-dwell tracking while scan_period
            # is still unresolved, use the TIGHTEST seeded split (or
            # skip entirely if no seed exists yet) -- NOT the raw
            # ratio-jump fallback, which can return one mega-burst
            # spanning nearly the whole hit history when there's no
            # clear separation yet. beam_dwell_estimate is a never-
            # shrinking max, so a single such mega-burst would corrupt
            # it permanently (confirmed directly: a degenerate span
            # inflated it to ~200 against a true beam_dwell of 6,
            # which then made every future periodicity score
            # uselessly wide regardless of whether scan_period ever
            # locked correctly afterward).
            if pri_seed is not None and pri_seed >= 1:
                self._update_intra_burst_state(band, self._segment_bursts_fixed(times, pri_seed * 2.0))
            return

        bursts, onsets, refined, rmse, _rel = best
        # Update intra-burst PRI/beam-dwell BEFORE (possibly) publishing
        # the new candidate period below: the sane_cap inside this call
        # must be scaled off the last TRUSTED scan_period_estimate, not
        # off a brand-new, not-yet-confirmed candidate.
        self._update_intra_burst_state(band, bursts)
        self.burst_starts[band] = onsets

        pending = self._pending_period[band]
        agrees_with_pending = (pending is not None and pending > 0
                                and abs(refined - pending) <= self.period_agreement_tol * pending)
        if agrees_with_pending:
            # Two independent fits (this call and the last one, over a
            # hit history that grew in between) landing within
            # tolerance of each other is real signal that this is a
            # genuine period, not a one-off overfit -- publish it as
            # the trusted estimate used both for periodicity scoring
            # and for the beam_dwell sane_cap.
            confidence = min(1.0, max(0.0, 1.0 - rmse / (self.confidence_scale * refined)))
            self.scan_period_estimate[band] = refined
            self.scan_jitter_estimate[band] = max(0.5, rmse)
            self.scan_confidence[band] = confidence
        elif self.scan_period_estimate[band] is None:
            # Nothing trusted yet and this candidate doesn't match the
            # last one either -- hold at zero confidence rather than
            # publishing an unconfirmed single fit (this is exactly
            # what let a spurious 89.7-step lock through previously).
            self.scan_confidence[band] = 0.0
        # else: a fit already exists and this new candidate disagrees
        # with the last one -- keep trusting the existing lock rather
        # than jumping to a single disagreeing new fit.
        self._pending_period[band] = refined

        # Overall confidence gates the belief-vs-periodic blend in the
        # inherited choose_bands(): without a scan_period lock there's
        # no usable periodic prediction at all, regardless of how good
        # the intra-burst PRI fit looks in isolation (you'd need to
        # already be scanning during a burst to have observed it).
        self.confidence[band] = self.scan_confidence[band]

    def _update_intra_burst_state(self, band, bursts):
        """intra-burst PRI + persistent beam-dwell width, factored out
        so both the successful-lock path and the no-lock fallback path
        can update it consistently.

        Both quantities below are computed only from TYPICAL-sized
        bursts, not the raw split. Found directly: a merged burst
        (e.g. size 11 against a true ~2-pulse beam pass) doesn't just
        corrupt beam_dwell_estimate via its span -- it also dumps a
        pile of its own internal gaps into the intra_gaps pool used to
        fit pri_estimate. Those internal gaps sit near the OUTER scan
        period (since the "burst" is actually several merged beam
        passes), which drags pri_estimate up from the true ~3 toward
        the scan period itself (confirmed: pri_estimate climbing to
        36-39 against scan_period~40). Once pri_estimate is corrupted
        that way, every downstream consumer (min_scan_to_pri_ratio's
        degeneracy guard, the sane_cap below) is now working off a
        wrong number too -- so the typical-size filter has to be
        applied before either estimate is touched, not just tacked on
        to the beam_dwell computation."""
        sizes = [len(b) for b in bursts if b]
        median_size = statistics.median(sizes) if sizes else 0
        tolerance = max(1, 0.5 * median_size)
        typical_bursts = [b for b in bursts if b and abs(len(b) - median_size) <= tolerance]

        intra_gaps = []
        for burst in typical_bursts:
            if len(burst) >= self.min_burst_hits:
                intra_gaps.extend(b - a for a, b in zip(burst[:-1], burst[1:]))
        if len(intra_gaps) >= 3:
            self.pri_estimate[band] = statistics.median(intra_gaps)
            spread = statistics.pstdev(intra_gaps) if len(intra_gaps) > 1 else 0.5
            self.jitter_estimate[band] = max(0.5, spread)
            cov = spread / max(1e-6, self.pri_estimate[band])
            self.pri_confidence[band] = max(0.0, min(1.0, 1.0 - cov))
        else:
            self.pri_confidence[band] = 0.0

        if typical_bursts:
            last_typical = typical_bursts[-1]
            span = last_typical[-1] - last_typical[0]
            # Defensive sanity cap: beam_dwell_estimate is a never-
            # shrinking max, so one bad segmentation could otherwise
            # corrupt it permanently. A genuine beam dwell can't be
            # anywhere near a full scan_period (SpatiallyScanningEmitter
            # itself enforces beam_dwell <= scan_period at construction,
            # and physically it's the SMALL fraction of a rotation the
            # beam is on you) -- so bound it relative to whichever
            # period signal is available, not just a loose PRI multiple.
            pri = self.pri_estimate[band]
            period = self.scan_period_estimate[band]
            sane_cap = 30 * pri if pri else float("inf")
            if period:
                sane_cap = min(sane_cap, 0.5 * period)
            if span + 1 <= sane_cap:
                self.beam_dwell_estimate[band] = max(self.beam_dwell_estimate[band], span + 1)

    def _evaluate_burst_split(self, band, bursts, pri_seed):
        """Checks one candidate burst segmentation against the size-
        consistency and degeneracy gates, and if it passes, returns
        (bursts, onsets, refined_period, rmse, relative_fit) -- or None
        if this split doesn't produce a trustworthy outer period."""
        onsets = [b[0] for b in bursts if len(b) >= 1]
        if len(onsets) < self.min_bursts:
            return None
        sizes = [len(b) for b in bursts if len(b) >= 1]
        # Raw coefficient-of-variation on burst sizes is oversensitive
        # at small absolute scale: with mean size ~1-2 (this band is
        # barely being scanned twice per pass), a single burst of size
        # 3 or 7 swings CoV wildly even though it's still plausibly the
        # same target occasionally catching one extra/fewer pulse.
        # Check instead what fraction of bursts sit within +-1 of the
        # median size -- tolerant of natural small-N variability, still
        # rejects genuinely erratic (non-periodic) segmentations.
        median_size = statistics.median(sizes) if sizes else 0
        near_median_frac = (sum(1 for s in sizes if abs(s - median_size) <= 1) / len(sizes)
                             if sizes else 0.0)
        if near_median_frac < self.min_burst_size_consistency:
            return None
        refined, rmse = self._search_best_period(
            onsets, self._refine_pri,
            # Excluding degenerate candidates from the search itself,
            # not just rejecting them after the fact: since the inner
            # PRI gates every transmission opportunity (beam-window
            # catches AND sidelobe leaks alike), candidate=pri_seed is
            # an exact algebraic divisor of every onset time and will
            # ALWAYS win a best-relative-fit contest against the true
            # outer period, structurally -- not from noise. Asking
            # _search_best_period to only consider candidates already
            # >= pri_seed * min_scan_to_pri_ratio forces it to report
            # the best candidate that COULD be the outer period,
            # instead of finding pri_seed, discarding it as degenerate,
            # and giving up with nothing.
            min_candidate=int(pri_seed * self.min_scan_to_pri_ratio) if pri_seed else 1)
        if refined is None or rmse is None or refined <= 0:
            return None
        return bursts, onsets, refined, rmse, rmse / refined

    def _periodicity_score(self, band, t):
        scan_conf = self.scan_confidence[band]
        period = self.scan_period_estimate[band]
        if scan_conf <= 0 or period is None or not self.burst_starts[band]:
            return 0.0
        last_burst = self.burst_starts[band][-1]
        phase = (t - last_burst) % period
        dist = min(phase, period - phase)
        dist = max(0.0, dist - self.switch_lead_steps)
        sigma = max(0.5, self.scan_jitter_estimate[band],
                    self.beam_dwell_estimate[band] / self.beam_dwell_sigma_divisor)
        burst_score = math.exp(-(dist ** 2) / (2 * sigma ** 2))

        pri_conf = self.pri_confidence[band]
        pri = self.pri_estimate[band]
        if pri_conf > 0 and pri and self.hit_times[band]:
            last_hit = self.hit_times[band][-1]
            phase2 = (t - last_hit) % pri
            dist2 = min(phase2, pri - phase2)
            sigma2 = max(0.5, self.jitter_estimate[band])
            pri_score = math.exp(-(dist2 ** 2) / (2 * sigma2 ** 2))
        else:
            # No fine-grained intra-burst timing yet -- don't suppress
            # interest across the whole predicted burst window just
            # because we haven't resolved PRI within it yet.
            pri_score = 1.0

        return burst_score * pri_score

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
            conf = self.confidence[b]
            periodic = self._periodicity_score(b, self.t)
            blended = (1 - conf) * self.belief[b] + conf * self.periodicity_weight * periodic
            # Extra exploration pull for a high-priority band that
            # hasn't locked yet. The base class's UCB bonus is NOT
            # weighted by priority -- only the "known value" (blended)
            # term is -- so a rare, low-occupancy but important target
            # competes for scan time on equal exploration footing with
            # every other band, even though bootstrapping a scan_period
            # lock specifically needs several CONSECUTIVE close-
            # together hits (to see intra-burst gaps at all), not just
            # occasional isolated ones. Found directly (seeds 9, 16,
            # 20, 21, 22, 24 of the mixed scenario, uncovered only
            # after fixing the confidence-desync bug above -- that bug
            # had been masking this separate, broader issue): even with
            # confidence correctly falling back to pure belief pre-
            # lock, belief alone for a naturally-sparse band stayed too
            # low against louder comms bands to ever earn enough
            # consecutive visits, leaving scan_period_estimate at None
            # (never even a first candidate) for the whole episode.
            # Scaling the bonus by priority ONLY pre-lock (conf<=0)
            # targets exactly the bootstrap phase; once locked, the
            # periodicity term already takes over and this has no
            # further effect.
            if conf <= 0:
                ucb_bonus *= self.priority[b]
            scores.append(self.priority[b] * blended + ucb_bonus)
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
        return order[:k]

    def update(self, band, observed_on):
        # Deliberately skip PRIAwareScheduler.update (it would call the
        # single-periodicity _update_pri_model this class overrides the
        # meaning of); go straight to the belief/UCB update it wraps.
        super(PRIAwareScheduler, self).update(band, observed_on)
        if observed_on:
            times = self.hit_times[band]
            times.append(self.t)
            if len(times) > self.history_len:
                del times[0]
            self._update_scan_model(band)


if __name__ == "__main__":
    import random as _random
    from scan_scheduler_v2 import run_episode, RoundRobinScheduler
    from scan_scheduler_prototype import Environment
    from scan_scheduler_v3_pri import SparsePeriodicEmitter
    from spatial_scan_emitter import SpatiallyScanningEmitter

    n_bands, n_steps = 8, 6000

    def scenario():
        inner = SparsePeriodicEmitter("fixed-pri-radar", band=5, pri=3)
        scanning = SpatiallyScanningEmitter(inner, scan_period_steps=40,
                                             beam_dwell_steps=6, sidelobe_leak_prob=0.02)
        return Environment(n_bands=n_bands, emitters=[scanning])

    print("Isolated scenario: one spatially-scanning fixed-PRI radar (band 5), "
          f"scan_period=40, beam_dwell=6, inner PRI=3, sidelobe_leak=2%, {n_steps} steps\n")

    for name, sched in [
        ("RoundRobin (open-loop baseline)", RoundRobinScheduler(n_bands)),
        ("PRIAware (single-periodicity, blind to nesting)", PRIAwareScheduler(n_bands, ucb_c=0.5)),
        ("ScanAwarePRIScheduler (this class)", ScanAwarePRIScheduler(n_bands, ucb_c=0.5)),
    ]:
        _random.seed(7)
        stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=1)
        r = stats.report()
        print(f"{name:52s} | interception={r['interception_ratio']*100:5.1f}% | "
              f"avg_reward/step={r['avg_reward_per_step']:.3f}")
