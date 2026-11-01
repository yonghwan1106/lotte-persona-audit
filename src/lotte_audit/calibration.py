"""Estimators and draws of the main stage's calibration study. No answers are read here.

Cells are small integers 0..m-1 so the 200 repeats stay fast. All estimates are probabilities and
cell_mae returns percentage points, the same scale as metrics.cell_mae.
"""
import numpy as np

CLIP_LO, CLIP_HI = 0.001, 0.999
K = 30
OFFSET_BOUND = 12.0
RIDGE = 1e-6
MAX_ITER = 50


def clip(p):
    return np.clip(np.asarray(p, dtype=float), CLIP_LO, CLIP_HI)


def logit(p):
    p = clip(p)
    return np.log(p) - np.log1p(-p)


def expit(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def cell_mean(values, weights, cells, m):
    """Weighted mean per cell. NaN where the cell has no rows."""
    den = np.bincount(cells, weights=weights, minlength=m)
    num = np.bincount(cells, weights=weights * values, minlength=m)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def cell_mae(estimate, truth):
    return float(100 * np.mean(np.abs(np.asarray(estimate) - np.asarray(truth))))


def direct_and_shrunk(y, w, cells, m, k=K):
    """E1 and E2. Same formula as baselines.real_sample_curve, with empty cells on the national mean."""
    national = float(np.average(y, weights=w))
    direct = np.where(np.bincount(cells, minlength=m) > 0, cell_mean(y, w, cells, m), national)
    counts = np.bincount(cells, minlength=m)
    return direct, (counts * direct + k * national) / (counts + k)


def fit_offset(p, y, w, bound=OFFSET_BOUND):
    """Offset d with the weighted sum of expit(logit(p)+d) equal to the weighted sum of y, by bisection."""
    lp = logit(p)
    target = float(np.sum(w * y))
    lo, hi = -bound, bound
    if np.sum(w * expit(lp + lo)) >= target:
        return lo
    if np.sum(w * expit(lp + hi)) <= target:
        return hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if np.sum(w * expit(lp + mid)) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _newton(x, y, w, start):
    """Weighted logistic maximum likelihood with a tiny ridge. Returns coefficients, or None if it did not converge."""
    beta = np.array(start, dtype=float)

    def loglik(b):
        eta = x @ b
        return float(np.sum(w * (y * eta - np.logaddexp(0.0, eta))) - 0.5 * RIDGE * b @ b)

    current = loglik(beta)
    for _ in range(MAX_ITER):
        mu = expit(x @ beta)
        grad = x.T @ (w * (y - mu)) - RIDGE * beta
        hess = (x * (w * mu * (1 - mu))[:, None]).T @ x + RIDGE * np.eye(x.shape[1])
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            return None
        scale = 1.0
        new = beta + scale * step
        next_ll = loglik(new)
        while next_ll < current - 1e-12 and scale > 1e-4:
            scale *= 0.5
            new = beta + scale * step
            next_ll = loglik(new)
        done = abs(next_ll - current) < 1e-9
        beta, current = new, next_ll
        if done:
            return beta
    return None


def fit_recalibration(p, y, w):
    """(a, b, status) of weighted logistic on logit(p). Falls back to the offset fit with b=1 when needed."""
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    w = w * len(w) / w.sum()
    lp = logit(p)
    if not (np.sum(w * y) > 0 and np.sum(w * (1 - y)) > 0):
        return fit_offset(p, y, w), 1.0, "fallback_one_class"
    beta = _newton(np.column_stack([np.ones(len(lp)), lp]), y, w, [fit_offset(p, y, w), 1.0])
    if beta is None:
        return fit_offset(p, y, w), 1.0, "fallback_no_convergence"
    return float(beta[0]), float(beta[1]), "ok"


def age_sex_model_cells(y, w, cells, cell_age, cell_sex):
    """R1: no panel at all. Weighted logistic on age band order and sex fitted on the n real respondents.

    Returns a modelled mean per cell. When the n hold one class or the fit fails, every cell gets the sample mean.
    """
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    w = w * len(w) / w.sum()
    national = float(np.average(y, weights=w))
    if not (np.sum(w * y) > 0 and np.sum(w * (1 - y)) > 0):
        return np.full(len(cell_age), national)
    x = np.column_stack([np.ones(len(y)), cell_age[cells], cell_sex[cells]])
    beta = _newton(x, y, w, [float(logit(national)), 0.0, 0.0])
    if beta is None:
        return np.full(len(cell_age), national)
    return expit(np.column_stack([np.ones(len(cell_age)), cell_age, cell_sex]) @ beta)


def panel_cells(p_test, w_test, cells_test, m):
    """E3: panel cell means on the test panel with its analysis weights."""
    return cell_mean(clip(p_test), w_test, cells_test, m)


def offset_estimate(d, p_test, w_test, cells_test, m):
    """E4 from a fitted offset."""
    return cell_mean(expit(logit(p_test) + d), w_test, cells_test, m)


def recalibrated_estimate(a, b, p_test, w_test, cells_test, m):
    """E5 and E7 from fitted coefficients."""
    return cell_mean(expit(a + b * logit(p_test)), w_test, cells_test, m)


def difference_estimate(p_cal, y, w, cells_cal, p_test, w_test, cells_test, m, k=K):
    """E6: panel cell mean plus the real residual per cell, shrunk toward the global residual, clipped."""
    resid = np.asarray(y, dtype=float) - clip(p_cal)
    global_resid = float(np.average(resid, weights=w))
    counts = np.bincount(cells_cal, minlength=m)
    direct = np.where(counts > 0, cell_mean(resid, w, cells_cal, m), global_resid)
    shrunk = (counts * direct + k * global_resid) / (counts + k)
    return np.clip(panel_cells(p_test, w_test, cells_test, m) + shrunk, 0.0, 1.0)


def draw_rows(rng, mass, n):
    """n row positions with probability proportional to mass, without replacement."""
    return rng.choice(len(mass), size=n, replace=False, p=mass / mass.sum())


def draw_unit_order(rng, unit_mass):
    """A successive sample of all units: the exponential keys give probability proportional to mass at each step."""
    return np.argsort(rng.exponential(size=len(unit_mass)) / unit_mass)


def draw_units(rng, unit_mass, unit_sizes, n):
    """Whole unit positions in draw order until at least n rows are in. A unit is never cut."""
    order = draw_unit_order(rng, unit_mass)
    stop = int(np.searchsorted(np.cumsum(unit_sizes[order]), n)) + 1
    return order[:stop]


def row_inclusion(mass, n, draws, seed):
    rng = np.random.default_rng(seed)
    hits = np.zeros(len(mass))
    for _ in range(draws):
        hits[draw_rows(rng, mass, n)] += 1
    return np.maximum(hits, 1) / draws


def unit_inclusion(unit_mass, unit_sizes, n, draws, seed):
    rng = np.random.default_rng(seed)
    hits = np.zeros(len(unit_mass))
    for _ in range(draws):
        hits[draw_units(rng, unit_mass, unit_sizes, n)] += 1
    return np.maximum(hits, 1) / draws


def unit_table(units):
    """(unique units, list of row positions per unit)."""
    uniq, inv = np.unique(units, return_inverse=True)
    return uniq, [np.flatnonzero(inv == i) for i in range(len(uniq))]


def make_draws(weights, units, n, kind, repeats, seed, pi_draws, pi_seed):
    """Repeated samples from the pool as (row positions, repaired weights). Pool weights are never used twice."""
    weights = np.asarray(weights, dtype=float)
    rng = np.random.default_rng(seed)
    out = []
    if kind == "row":
        pi = row_inclusion(weights, n, pi_draws, pi_seed)
        for _ in range(repeats):
            idx = draw_rows(rng, weights, n)
            out.append((idx, weights[idx] / pi[idx]))
        return out
    if kind != "cluster":
        raise ValueError(f"unknown draw kind {kind}")
    _, groups = unit_table(units)
    mass = np.array([weights[g].sum() for g in groups])
    sizes = np.array([len(g) for g in groups])
    pi = unit_inclusion(mass, sizes, n, pi_draws, pi_seed)
    for _ in range(repeats):
        chosen = draw_units(rng, mass, sizes, n)
        idx = np.concatenate([groups[u] for u in chosen])
        wts = np.concatenate([weights[groups[u]] / pi[u] for u in chosen])
        out.append((idx, wts))
    return out


def difference_summary(values, reference):
    """Mean difference to the reference over paired draws, with the percentile 95 percent interval."""
    d = np.asarray(values, dtype=float) - np.asarray(reference, dtype=float)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"mean_diff": round(float(d.mean()), 3), "ci95": [round(float(lo), 3), round(float(hi), 3)], "share_below_zero": round(float((d < 0).mean()), 3)}
