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
        self._last_recompute = [-recompute_every] * n_bands  # force an immediate first compute

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

    def choose_bands(self, k):
        self.t += 1
        if self.t <= self.warmup_steps:
            for b in range(self.n_bands):
                self._propagate(b)
            return self._warmup_bands(k)
        for b in range(self.n_bands):
            self._propagate(b)
            self._maybe_recompute(b)
        scores = [
            self.priority[b] * self._lookup(b, self.belief[b])
            + self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
            for b in range(self.n_bands)
        ]
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
        return order[:k]


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
