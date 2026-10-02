"""
scan_scheduler_whittle.py
============================
WhittleIndexScheduler: the biggest remaining theoretical item from the
original gap analysis. Subclasses BeliefUCBScheduler to reuse its
belief tracking and online p01/p11 (P(on|off)/P(on|on)) learning
exactly as-is -- only choose_bands differs, scoring each band by its
Whittle index (whittle_index.py) instead of the myopic belief+UCB
score every other scheduler in this project uses.

Per-band Whittle-index TABLES are recomputed periodically (every
`recompute_every` steps, default 200), not every step -- p01/p11
estimates only change slowly as more observations accumulate, so
recomputing on every single step would be needless work for no
precision gain. Between recomputes, a band's current belief is looked
up in its last-computed table via linear interpolation between the two
nearest bracketing (sorted, monotonic per whittle_index.py's own
validation) table entries, since the live-tracked belief generally
won't land exactly on one of the table's discrete chain points.

The UCB exploration bonus and priority weighting are kept EXACTLY as
in BeliefUCBScheduler (same formula, same role) so this is a fair,
apples-to-apples comparison against every other scheduler in this
project: only the "how good is this band right now" term changes, not
the exploration or priority mechanics layered on top of it.

Run:  python3 scan_scheduler_whittle.py   (quick single-seed sanity
check against the sparse-radar and beacon references, matching this
project's own established first-pass validation discipline)
"""

import math
import random

import numpy as np
from typing import Dict, List

from scan_scheduler_v2 import BeliefUCBScheduler
from whittle_index import solve_whittle_indices

# Shared, process-wide cache of solved tables keyed by (p01, p11).
# The value-iteration solve is ~94% of this scheduler's runtime, and many bands
# (and many recomputes of the same band) have identical parameters, so solving
# once per distinct (p01, p11) removes most of the work without changing output.
_TABLE_CACHE: dict = {}


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _inv_logit(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class WhittleIndexScheduler(BeliefUCBScheduler):
    def __init__(self, n_bands, ucb_c: float = 0.5, warmup_steps: int = 0,
                 priority=None, warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1,
                 recompute_every: int = 200, table_quant_step: float = 0.0,
                 memoize: bool = True):
        super().__init__(n_bands, ucb_c=ucb_c, warmup_steps=warmup_steps, priority=priority,
                          warmup_dwell_steps=warmup_dwell_steps,
                          warmup_dwell_jitter=warmup_dwell_jitter)
        self.recompute_every = recompute_every
        # memoize=True (default): exact-key table cache, output identical to no
        # cache. table_quant_step>0: approximate logit-scale buckets (opt-in).
        # memoize=False and table_quant_step=0: original solve-every-recompute.
        self.memoize = memoize
        self.table_quant_step = table_quant_step or 0.0
        self._band_key = [None] * n_bands
        self.n_solves = 0          # diagnostic: VI solves actually run by this instance
        # Per-band sorted (omegas, whittle) arrays from the last
        # recompute -- None until the first recompute happens.
        self._tables: List = [None] * n_bands
        # numpy so the per-step "which bands are due" test is one vector compare
        self._last_recompute = np.full(n_bands, -recompute_every, dtype=np.int64)  # force an immediate first compute
        # --- vectorised per-step state (see choose_bands) -----------------------
        # The python lists inherited from BeliefUCBScheduler (belief, off_on, ...)
        # stay authoritative; these numpy mirrors are refreshed in update() (only
        # the scanned band changes) so choose_bands needs no per-band python loop.
        self._np_ready = False
        self._tab_dirty = True

    def _lookup(self, band, belief):
        table = self._tables[band]
        if table is None:
            return belief  # no table yet -- fall back to raw belief (same order as everyone pre-learning)
        omegas, whittle = table
        # np.searchsorted-free linear interpolation via plain Python
        # (small arrays, called once per band per step -- no need for
        # numpy overhead here versus the batch solve in whittle_index.py).
        n = len(omegas)
        if belief <= omegas[0]:
            return whittle[0]
        if belief >= omegas[-1]:
            return whittle[-1]
        lo, hi = 0, n - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if omegas[mid] <= belief:
                lo = mid
            else:
                hi = mid
        span = omegas[hi] - omegas[lo]
        frac = (belief - omegas[lo]) / span if span > 1e-12 else 0.0
        return whittle[lo] + frac * (whittle[hi] - whittle[lo])

    def _maybe_recompute(self, band):
        if self.t - self._last_recompute[band] < self.recompute_every:
            return
        self._last_recompute[band] = self.t
        p01 = self._p_on_given_off(band)
        p11 = self._p_on_given_on(band)
        # Degenerate/near-degenerate transition estimates (can happen
        # early, or for a band that's been almost always on or off)
        # would make build_belief_chain's fixed-point division unstable
        # or produce a near-empty chain -- fall back to raw belief
        # (table=None) rather than risk a bad table silently shipping.
        if not (0.0 < p01 < 1.0 and 0.0 < p11 < 1.0) or abs(p11 - p01) < 1e-6:
            self._tables[band] = None
            return
        if self.table_quant_step:
            # APPROXIMATE mode (opt-in): share tables across nearby parameters.
            # Not recommended: on sparse scenarios interception swung between
            # 9% and 57% across bucket widths because small table changes flip
            # which band the scheduler locks onto.
            step = self.table_quant_step
            key = (round(_logit(p01) / step), round(_logit(p11) / step))
            ckey = (step,) + key
            solve_p01, solve_p11 = _inv_logit(key[0] * step), _inv_logit(key[1] * step)
        elif self.memoize:
            # EXACT mode (default): key on the exact estimates. p01/p11 are
            # ratios of integer counts, so a band that wasn't scanned since the
            # last recompute (or two bands with equal counts) gives bit-identical
            # inputs and therefore a bit-identical table -- same output as
            # solving every time, minus the redundant solves.
            key = (p01, p11)
            ckey = ("exact",) + key
            solve_p01, solve_p11 = p01, p11
        else:
            _, omegas, whittle = solve_whittle_indices(p01, p11)
            self.n_solves += 1
            order = omegas.argsort()
            self._tables[band] = (omegas[order], whittle[order])
            return
        if key == self._band_key[band]:
            return  # this band already holds this table
        self._band_key[band] = key
        table = _TABLE_CACHE.get(ckey)
        if table is None:
            if abs(solve_p11 - solve_p01) < 1e-6:
                table = False  # memoryless: fall back to raw belief
            else:
                _, omegas, whittle = solve_whittle_indices(solve_p01, solve_p11)
                self.n_solves += 1
                order = omegas.argsort()
                table = (omegas[order], whittle[order])
            _TABLE_CACHE[ckey] = table
        self._tables[band] = table or None

    # ------------------------------------------------------------------
    # Vectorised per-step path. Everything below reproduces the scalar
    # formulas operation-for-operation (same IEEE ops in the same order), so
    # picks are bit-identical to the old per-band python loop -- verified by
    # scan_scheduler_whittle_equiv_test.py.
    # ------------------------------------------------------------------
    def _sync_np(self):
        self._p01 = np.array([self.off_on[b] / self.off_tot[b] for b in range(self.n_bands)])
        self._p11 = np.array([self.on_on[b] / self.on_tot[b] for b in range(self.n_bands)])
        self._cnt1 = np.array(self.scan_count, dtype=np.float64) + 1.0
        self._prio = np.array(self.priority, dtype=np.float64)
        self._np_ready = True

    def update(self, band, observed_on):
        super().update(band, observed_on)
        if self._np_ready:
            self._p01[band] = self.off_on[band] / self.off_tot[band]
            self._p11[band] = self.on_on[band] / self.on_tot[band]
            self._cnt1[band] = self.scan_count[band] + 1.0

    def _propagate_all(self):
        bel = np.array(self.belief)
        bel = bel * self._p11 + (1 - bel) * self._p01      # == _propagate, all bands at once
        self.belief[:] = bel.tolist()                       # keep the list object (and its identity)
        return bel

    _PAD = 1e300   # finite padding (never <= a belief): keeps arithmetic on unused lanes free of inf/nan

    def _rebuild_padded(self):
        """Pack the per-band tables into rectangular arrays so the interpolation
        in _lookup_all is a handful of array ops (flat 1-D takes, not 2-D fancy
        indexing, which is ~3x slower for these sizes)."""
        B = self.n_bands
        lens = [0 if t is None else len(t[0]) for t in self._tables]
        L = max(lens + [1]) + 1
        om = np.full((B, L), self._PAD)
        wh = np.zeros((B, L))
        for b, t in enumerate(self._tables):
            if t is not None:
                om[b, :lens[b]] = t[0]
                wh[b, :lens[b]] = t[1]
        self._om = om
        self._om_flat, self._wh_flat = om.ravel(), wh.ravel()
        tlen = np.array(lens, dtype=np.int64)
        rows = np.arange(B)
        self._rowbase = rows * L
        self._tlm2 = np.maximum(tlen - 2, 0)
        self._has_tab = tlen > 0
        last = np.maximum(tlen - 1, 0)
        self._om_first = om[:, 0].copy()
        self._wh_first = wh[:, 0].copy()
        self._om_last = om[rows, last]
        self._wh_last = wh[rows, last]
        self._tab_dirty = False

    def _lookup_all(self, bel):
        """Vector form of _lookup: linear interpolation in each band's table;
        raw belief where a band has no table yet."""
        cnt = (self._om <= bel[:, None]).sum(axis=1)       # #table beliefs <= bel (padding never counted)
        i_lo = self._rowbase + np.minimum(np.maximum(cnt - 1, 0), self._tlm2)
        i_hi = i_lo + 1
        o_lo = self._om_flat.take(i_lo)
        w_lo = self._wh_flat.take(i_lo)
        span = self._om_flat.take(i_hi) - o_lo
        good = span > 1e-12
        frac = np.where(good, (bel - o_lo) / np.where(good, span, 1.0), 0.0)
        val = w_lo + frac * (self._wh_flat.take(i_hi) - w_lo)
        val = np.where(bel >= self._om_last, self._wh_last, val)
        val = np.where(bel <= self._om_first, self._wh_first, val)
        return np.where(self._has_tab, val, bel)

    def choose_bands(self, k):
        self.t += 1
        if not self._np_ready:
            self._sync_np()
        if self.t <= self.warmup_steps:
            self._propagate_all()
            return self._warmup_bands(k)
        bel = self._propagate_all()
        due = np.flatnonzero(self.t - self._last_recompute >= self.recompute_every)
        if due.size:
            for b in due.tolist():
                self._maybe_recompute(b)
            self._tab_dirty = True
        if self._tab_dirty:
            self._rebuild_padded()
        scores = (self._prio * self._lookup_all(bel)
                  + self.ucb_c * np.sqrt(math.log(self.t + 1) / self._cnt1))
        # stable sort on -score == sorted(..., reverse=True): ties keep lower band index first
        return np.argsort(-scores, kind="stable")[:k].tolist()


if __name__ == "__main__":
    from scan_scheduler_v2 import BeliefUCBScheduler as _BUCB, run_episode
    from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
    from scan_scheduler_prototype import make_scenario

    n_bands = 36

    print("=== Sanity: sparse-radar headline (synthetic, seed=11, warmup=800) ===")
    n_steps, warmup = 4000, 800
    scenario = make_sparse_scenario(n_bands)

    def per_emitter_capture(cls, **kw):
        random.seed(11)
        sched = cls(n_bands, ucb_c=0.5, warmup_steps=warmup, **kw)
        env = scenario()
        radar_p = radar_c = comm1_on = comm1_c = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
            if t > warmup:
                if status[5]:
                    radar_p += 1
                    if 5 in bands:
                        radar_c += 1
                if status[1]:
                    comm1_on += 1
                    if 1 in bands:
                        comm1_c += 1
        return radar_c, radar_p, comm1_c, comm1_on

    for name, cls in [("BeliefUCB", _BUCB), ("PRIAware (v3)", PRIAwareScheduler),
                      ("WhittleIndex", WhittleIndexScheduler)]:
        rc, rp, cc, co = per_emitter_capture(cls)
        print(f"  {name:20s}: radar {100*rc/rp:5.1f}%   comm-1 {100*cc/co:5.1f}%")

    print("\n=== Sanity: beacon scenario (synthetic, seed=7), k=1 and k=2 ===")
    scenario2 = make_scenario(n_bands)
    for k in (1, 2):
        print(f"  --- k={k} ---")
        for name, cls in [("BeliefUCB", _BUCB), ("PRIAware (v3)", PRIAwareScheduler),
                          ("WhittleIndex", WhittleIndexScheduler)]:
            random.seed(7)
            sched = cls(n_bands, ucb_c=0.5)
            stats = run_episode(scenario2, sched, n_steps, n_bands, k_channels=k)
            print(f"    {name:20s}: {stats.report()['interception_ratio']*100:5.1f}%")
