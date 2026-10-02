"""Drop-in optimized Whittle-index solver.

API and numerical algorithm are kept compatible with the original module.
The main optimization is a Numba-compiled implementation of the existing
warm-started subsidy sweep.  No policy-iteration shortcut, approximation,
or closed-form replacement is used.
"""

import numpy as np

try:
    from numba import njit
    _NUMBA_AVAILABLE = True
except Exception:
    _NUMBA_AVAILABLE = False


def build_belief_chain(p01: float, p11: float, n_truncate: int = 60, tol: float = 1e-7):
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

    branch_a = build_branch(p01)
    branch_b = build_branch(p11)
    raw = branch_a + branch_b + [fixed_point]
    rounded = np.round(np.array(raw), 9)
    omegas = np.unique(rounded)

    def nearest_idx(w):
        return int(np.argmin(np.abs(omegas - w)))

    # Exact nearest-neighbour mapping, but without an O(n) scan for every state.
    targets = omegas * p11 + (1.0 - omegas) * p01
    pos = np.searchsorted(omegas, targets, side="left")
    pos = np.clip(pos, 0, len(omegas) - 1)
    left = np.maximum(pos - 1, 0)
    choose_left = np.abs(targets - omegas[left]) <= np.abs(omegas[pos] - targets)
    succ_passive = np.where(choose_left, left, pos).astype(np.int64)

    idx_p01 = nearest_idx(p01)
    idx_p11 = nearest_idx(p11)
    return omegas, succ_passive, idx_p01, idx_p11


def _default_m_grid(m_hi: float, n_grid: int):
    return np.concatenate([np.geomspace(1e-6, 1e-2, 60),
                           np.linspace(1e-2, m_hi, n_grid)[1:]])


if _NUMBA_AVAILABLE:
    @njit(cache=True, fastmath=False)
    def _sweep_numba(omegas, succ_passive, idx_p01, idx_p11, m_grid,
                     vi_tol, vi_max_iter, early_exit, check_first_passive):
        n = len(omegas)
        ref = n - 1
        whittle = np.empty(n, dtype=np.float64)
        for i in range(n):
            whittle[i] = np.nan
        still_active = np.ones(n, dtype=np.bool_)
        V = np.zeros(n, dtype=np.float64)

        first = True
        for gm in range(len(m_grid)):
            m = m_grid[gm]

            # These arrays deliberately mirror the original implementation:
            # q_* are from the V at the START of the iteration, and the action
            # after the loop is based on the q_* from the final iteration.
            q_active = np.empty(n, dtype=np.float64)
            q_passive = np.empty(n, dtype=np.float64)
            V_new = np.empty(n, dtype=np.float64)

            for _ in range(vi_max_iter):
                v11 = V[idx_p11]
                v01 = V[idx_p01]
                maxdiff = 0.0

                for i in range(n):
                    w = omegas[i]
                    qa = w + w * v11 + (1.0 - w) * v01
                    qp = m + V[succ_passive[i]]
                    q_active[i] = qa
                    q_passive[i] = qp
                    vn = (qa if qa >= qp else qp) - V[ref]
                    V_new[i] = vn
                    d = abs(vn - V[i])
                    if d > maxdiff:
                        maxdiff = d

                # Match the original: assign V before breaking.
                for i in range(n):
                    V[i] = V_new[i]
                if maxdiff < vi_tol:
                    break

            if first and check_first_passive:
                for i in range(n):
                    if not (q_active[i] >= q_passive[i]):
                        return whittle, False
            first = False

            any_active = False
            for i in range(n):
                action_active = q_active[i] >= q_passive[i]
                if still_active[i] and not action_active:
                    whittle[i] = m
                    still_active[i] = False
                if still_active[i]:
                    any_active = True

            if early_exit and not any_active:
                break

        return whittle, True
else:
    _sweep_numba = None


def _sweep_numpy(omegas, succ_passive, idx_p01, idx_p11, m_grid, vi_tol,
                 vi_max_iter, early_exit=True, check_first_passive=False,
                 patience=0):
    """Original numerical sweep, retained as a fallback and for patience>0."""
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
            break
    return whittle, True


def _sweep(omegas, succ_passive, idx_p01, idx_p11, m_grid, vi_tol, vi_max_iter,
           early_exit=True, check_first_passive=False, patience=0):
    # Default path: compiled version of the SAME Bellman sweep.
    # patience>0 is intentionally kept on the original path because that mode
    # is already approximate by design and is not the performance-critical
    # default.
    if _NUMBA_AVAILABLE and patience == 0:
        return _sweep_numba(omegas, succ_passive, idx_p01, idx_p11, m_grid,
                            vi_tol, vi_max_iter, early_exit,
                            check_first_passive)
    return _sweep_numpy(omegas, succ_passive, idx_p01, idx_p11, m_grid,
                        vi_tol, vi_max_iter, early_exit,
                        check_first_passive, patience)


def solve_whittle_indices(p01: float, p11: float, n_truncate: int = 60,
                           m_lo: float = -0.5, m_hi: float = 1.5, n_grid: int = 120,
                           vi_tol: float = 1e-6, vi_max_iter: int = 500, m_grid=None,
                           fast: bool = True, patience: int = 0):
    """Drop-in replacement for the original solve_whittle_indices()."""
    omegas, succ_passive, idx_p01, idx_p11 = build_belief_chain(p01, p11, n_truncate)

    if m_grid is None:
        m_grid = _default_m_grid(m_hi, n_grid)
    m_grid = np.asarray(m_grid, dtype=float)

    whittle = None
    if fast:
        i0 = int(np.searchsorted(m_grid, 0.5 * float(omegas.min())))
        i0 = max(0, min(i0, len(m_grid) - 1))
        whittle, ok = _sweep(
            omegas, succ_passive, idx_p01, idx_p11, m_grid[i0:],
            vi_tol, vi_max_iter, early_exit=True,
            check_first_passive=(i0 > 0), patience=patience)
        if not ok:
            whittle = None

    if whittle is None:
        whittle, _ = _sweep(
            omegas, succ_passive, idx_p01, idx_p11, m_grid,
            vi_tol, vi_max_iter, early_exit=fast,
            patience=patience if fast else 0)

    whittle[np.isnan(whittle)] = float(m_grid[-1])
    return dict(zip(omegas.tolist(), whittle.tolist())), omegas, whittle


if __name__ == "__main__":
    print("=== Self-test: optimized whittle_index.py ===")
    for p01, p11 in [(0.1, 0.8), (0.3, 0.6), (0.05, 0.95), (0.6, 0.3)]:
        table, omegas, whittle = solve_whittle_indices(p01, p11)
        w_at_p11 = table[min(table, key=lambda w: abs(w - p11))]
        print(f"p01={p01}, p11={p11}:")
        print(f"  ANCHOR CHECK  W(p11) computed={w_at_p11:.4f}  vs known closed-form W(p11)=p11={p11:.4f}"
              f"  {'OK' if abs(w_at_p11 - p11) < 0.03 else 'MISMATCH -- investigate'}")
        order = np.argsort(omegas)
        monotone = np.all(np.diff(whittle[order]) >= -1e-9)
        print(f"  monotone non-decreasing in belief: {monotone}")
        print(f"  index range: [{whittle.min():.3f}, {whittle.max():.3f}] over {len(omegas)} reachable belief states\n")
