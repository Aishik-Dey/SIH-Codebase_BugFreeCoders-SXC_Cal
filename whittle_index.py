"""
whittle_index.py
==================
Computes Whittle indices for the 2-state Markov ("Gilbert-Elliott")
restless-bandit channel model this whole project's belief tracking
already uses (BeliefUCBScheduler's belief[b], learned via
_p_on_given_on/_p_on_given_off, IS exactly the belief state omega in
this model; _propagate IS exactly the T(omega) update below). This is
the biggest remaining theoretical item from the original gap analysis:
a genuinely optimal (for this restless-bandit relaxation) alternative
to the myopic belief+UCB/Hedge heuristic every other scheduler in this
project uses.

MODEL (matches Liu & Zhao 2010, "Indexability of Restless Bandit
Problems and Optimality of Whittle Index for Dynamic Multichannel
Access", IEEE Trans. Info. Theory -- confirmed via direct paper search,
not assumed from memory): a band is a 2-state Markov chain (on/off).
Scanning it (ACTIVATE) reveals its true current state (reward = 1 if
on, 0 if off) and, going forward, the belief resets to p11 = P(on |
just observed on) or p01 = P(on | just observed off). NOT scanning
(PASSIVE) reveals nothing; belief evolves via T(omega) = omega*p11 +
(1-omega)*p01.

WHY NUMERICAL, NOT THE PAPER'S CLOSED FORM, STATED HONESTLY: Liu & Zhao
prove a closed-form Whittle index exists and give it, but the exact
expression is piecewise (splits on p11 vs p01, and further by regions
of the belief space) and is genuinely easy to mistranscribe from a
paper I can't fully verify character-by-character here. Computing the
Whittle index NUMERICALLY -- by directly solving the average-reward
subsidized single-arm MDP that Whittle's index is DEFINED by, via
relative value iteration -- sidesteps that transcription risk entirely
by construction: it can't be "the wrong formula" because it isn't a
formula, it's the direct definition, solved. This is also a
standard, legitimate technique in this literature (see e.g. "Efficient
Algorithms for Finite Horizon and Streaming Restless Bandits" and
"Uncertainty-of-Information Scheduling" -- both compute Whittle indices
this way rather than via closed form, explicitly for problems where a
clean closed form is unavailable or error-prone). Validated below
against the ONE piece of the closed form confirmed directly from
multiple independent sources: W(p11) = p11 (the Whittle index of the
belief state immediately after observing the channel ON).

ALGORITHM: the belief space, restricted to states actually reachable
from p01/p11 under repeated passive evolution, is a COUNTABLE chain
(not the full continuum) -- exactly as established in the cited
literature ("the belief state space of a single-bandit is a countably
infinite set"). Build this chain by iterating T from p01 and from p11
until both converge (geometrically) to the shared fixed point, merge
into one terminal state there. For a swept grid of candidate subsidies
m (ascending), solve the average-reward relative-value-iteration
Bellman equation for the two-action MDP over this chain, warm-started
from the previous (slightly lower) m's solution -- since V varies
continuously in m, this converges in a handful of iterations per grid
point rather than from scratch, making a fine sweep computationally
cheap. Indexability (proven in the cited paper, not re-derived here)
guarantees each state's optimal action flips from ACTIVATE to PASSIVE
exactly once as m increases; that crossover m IS the state's Whittle
index.

Run:  python3 whittle_index.py   (self-test: anchor + monotonicity)
"""

import numpy as np


def build_belief_chain(p01: float, p11: float, n_truncate: int = 60, tol: float = 1e-7):
    """Returns (omegas, succ_passive, idx_p01, idx_p11) where omegas is
    a sorted array of distinct reachable belief values, succ_passive[i]
    is the index (into omegas) of T(omegas[i]), and idx_p01/idx_p11 are
    the indices of p01 and p11 themselves (the two ACTIVATE-branch
    restart points, constant across every state)."""
    def T(w):
        return w * p11 + (1 - w) * p01

    fixed_point = p01 / (1 - p11 + p01) if abs(1 - p11 + p01) > 1e-12 else 0.5

    def build_branch(start):
        vals = [start]
        w = start
        for _ in range(n_truncate):
            w = T(w)
            if abs(w - fixed_point) < tol:
                break
            vals.append(w)
        return vals

    branch_a = build_branch(p01)  # "just observed OFF" branch
    branch_b = build_branch(p11)  # "just observed ON" branch

    raw = branch_a + branch_b + [fixed_point]
    # Merge near-duplicates (branches can converge to values that are
    # numerically indistinguishable well before hitting the fixed point
    # exactly), then sort -- np.unique with a rounding key is enough
    # here since chain values are well-separated except near the tail.
    rounded = np.round(np.array(raw), 9)
    omegas = np.unique(rounded)

    def nearest_idx(w):
        return int(np.argmin(np.abs(omegas - w)))

    succ_passive = np.array([nearest_idx(T(w)) for w in omegas], dtype=np.int64)
    idx_p01 = nearest_idx(p01)
    idx_p11 = nearest_idx(p11)
    return omegas, succ_passive, idx_p01, idx_p11


def _default_m_grid(m_hi: float, n_grid: int):
    return np.concatenate([np.geomspace(1e-6, 1e-2, 60),
                           np.linspace(1e-2, m_hi, n_grid)[1:]])


def _sweep(omegas, succ_passive, idx_p01, idx_p11, m_grid, vi_tol, vi_max_iter,
           early_exit=True, check_first_passive=False, patience=0):
    """Warm-started ascending-m sweep. Returns (whittle, ok). ok is False only
    when check_first_passive is set and some state was already passive at the
    first grid point (i.e. a flip happened below the trimmed start)."""
    n = len(omegas)
    ref = n - 1
    whittle = np.full(n, np.nan)
    still_active = np.ones(n, dtype=bool)
    V = np.zeros(n)
    first = True
    for m in m_grid:
        same = 0
        prev = None
        for _ in range(vi_max_iter):
            q_active = omegas + omegas * V[idx_p11] + (1 - omegas) * V[idx_p01]
            q_passive = m + V[succ_passive]
            V_new = np.maximum(q_active, q_passive) - V[ref]
            if np.max(np.abs(V_new - V)) < vi_tol:
                V = V_new
                break
            V = V_new
            if patience:
                # Only the ACTION per state matters for the index, and for
                # sparse bands (small p01) V converges slowly (often hitting
                # the iteration cap) while the policy settles within a few
                # iterations. Stop once it has been unchanged `patience` times.
                act = q_active >= q_passive
                if prev is not None and np.array_equal(act, prev):
                    same += 1
                    if same >= patience:
                        break
                else:
                    same = 0
                prev = act
        action_active = q_active >= q_passive
        if first and check_first_passive and not action_active.all():
            return whittle, False
        first = False
        newly_passive = still_active & ~action_active
        whittle[newly_passive] = m
        still_active &= action_active
        if early_exit and not still_active.any():
            break  # every state has flipped; remaining (larger) m cannot change anything
    return whittle, True


def solve_whittle_indices(p01: float, p11: float, n_truncate: int = 60,
                           m_lo: float = -0.5, m_hi: float = 1.5, n_grid: int = 120,
                           vi_tol: float = 1e-6, vi_max_iter: int = 500, m_grid=None,
                           fast: bool = True, patience: int = 0):
    """Returns (dict {belief: whittle}, omegas, whittle) via the warm-started
    ascending-m sweep described in the module docstring.

    fast=True (default) gives the same result as fast=False, a little quicker
    (verified by randomized equality tests, see whittle_equiv_test.py):
      * early exit once every state has flipped to passive, and
      * start the sweep near the smallest reachable belief instead of at
        m_lo. Safe by indexability (the passive set only grows with m): if no
        state is passive at the trimmed start, none was passive below it. If
        that check ever fails the solver silently redoes the full sweep.
    fast=False is the original full sweep (kept for verification).

    patience>0 additionally stops each VI solve once the policy is unchanged for
    that many iterations. It is ~2-3x faster but NOT exact (13-32 of 293 random
    cases differ, worst by 0.25 in index), so it is off by default."""
    omegas, succ_passive, idx_p01, idx_p11 = build_belief_chain(p01, p11, n_truncate)
    # Subsidy grid. The old uniform linspace(-0.5, 1.5, 120) has a step of
    # ~0.0168, COARSER than the belief range of a sparse band (p01 ~ 1e-3 or
    # lower), so every low-belief state was quantised to the same first grid
    # point above 0 (0.0042) and all sparse bands tied. A log-spaced low end
    # resolves indices down to 1e-6; the linear tail keeps the old resolution.
    if m_grid is None:
        m_grid = _default_m_grid(m_hi, n_grid)
    m_grid = np.asarray(m_grid, dtype=float)

    whittle = None
    if fast:
        i0 = int(np.searchsorted(m_grid, 0.5 * float(omegas.min())))
        i0 = max(0, min(i0, len(m_grid) - 1))
        whittle, ok = _sweep(omegas, succ_passive, idx_p01, idx_p11, m_grid[i0:],
                             vi_tol, vi_max_iter, early_exit=True,
                             check_first_passive=(i0 > 0), patience=patience)
        if not ok:
            whittle = None
    if whittle is None:
        whittle, _ = _sweep(omegas, succ_passive, idx_p01, idx_p11, m_grid,
                            vi_tol, vi_max_iter, early_exit=fast, patience=patience if fast else 0)

    # Any state never flipped within the grid gets the upper bound as a safe
    # fallback rather than NaN propagating into scoring.
    whittle[np.isnan(whittle)] = float(m_grid[-1])
    return dict(zip(omegas.tolist(), whittle.tolist())), omegas, whittle


if __name__ == "__main__":
    print("=== Self-test: whittle_index.py ===")
    for p01, p11 in [(0.1, 0.8), (0.3, 0.6), (0.05, 0.95), (0.6, 0.3)]:
        table, omegas, whittle = solve_whittle_indices(p01, p11)
        w_at_p11 = table[min(table, key=lambda w: abs(w - p11))]
        print(f"p01={p01}, p11={p11}:")
        print(f"  ANCHOR CHECK  W(p11) computed={w_at_p11:.4f}  vs known closed-form W(p11)=p11={p11:.4f}"
              f"  {'OK' if abs(w_at_p11 - p11) < 0.03 else 'MISMATCH -- investigate'}")
        order = np.argsort(omegas)
        monotone = np.all(np.diff(whittle[order]) >= -1e-9)
        print(f"  monotone non-decreasing in belief: {monotone}")
        print(f"  index range: [{whittle.min():.3f}, {whittle.max():.3f}] over "
              f"{len(omegas)} reachable belief states\n")
