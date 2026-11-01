"""Weighted metrics shared by baselines and scoring. All cell metrics are in percentage points."""
import numpy as np
from sklearn.metrics import roc_auc_score


def weighted_auc(y, p, w):
    """Weighted AUC. None when y has only one class."""
    y = np.asarray(y)
    if y.min() == y.max():
        return None
    return float(roc_auc_score(y, np.asarray(p, dtype=float), sample_weight=np.asarray(w, dtype=float)))


def cell_means(values, weights, cells, universe=None):
    """Weighted mean per cell as {cell: value}. Cells absent from the data are left out."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    cells = np.asarray(cells)
    universe = np.unique(cells) if universe is None else universe
    out = {}
    for u in universe:
        m = cells == u
        if m.any():
            out[int(u)] = float(np.average(values[m], weights=weights[m]))
    return out


def cell_mae(estimate, truth):
    """Mean absolute error in pp over the truth cells present in the estimate."""
    keys = [k for k in truth if k in estimate]
    if not keys:
        raise ValueError("no overlapping cells")
    return float(100 * np.mean([abs(estimate[k] - truth[k]) for k in keys]))


def constant_mae(constant, truth):
    return float(100 * np.mean([abs(constant - v) for v in truth.values()]))


def underdispersion(estimate, truth):
    """SD of panel cell means over SD of real cell means, same cells."""
    keys = [k for k in truth if k in estimate]
    real_sd = np.std([truth[k] for k in keys], ddof=1)
    if real_sd == 0:
        return None
    return float(np.std([estimate[k] for k in keys], ddof=1) / real_sd)


def cell_pearson(estimate, truth):
    keys = [k for k in truth if k in estimate]
    a = np.array([estimate[k] for k in keys])
    b = np.array([truth[k] for k in keys])
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _age_means(values, weights, ages):
    bands = sorted(set(np.asarray(ages).astype(int).tolist()))
    return bands, [float(np.average(values[ages == b], weights=weights[ages == b])) for b in bands]


def age_slope(values, weights, ages):
    """OLS slope of the weighted age-band mean on band order, pp per band (band step about 10 years)."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    ages = np.asarray(ages).astype(int)
    bands, means = _age_means(values, weights, ages)
    if len(bands) < 2:
        return None
    return float(100 * np.polyfit(np.arange(len(bands)), means, 1)[0])


def gender_gap(values, weights, sexes):
    """Female minus male weighted mean, pp. SQ1 codes: 1 male, 2 female."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    sexes = np.asarray(sexes).astype(int)
    if not ((sexes == 1).any() and (sexes == 2).any()):
        return None
    return float(100 * (np.average(values[sexes == 2], weights=weights[sexes == 2]) - np.average(values[sexes == 1], weights=weights[sexes == 1])))


def within_group_auc(y, p, groups, w):
    """Weighted AUC computed inside each group and pooled by positive-negative weight mass.

    Inside one survey unit, unit-level effects cancel, so this shows individual-level signal only.
    Returns (auc or None, number of usable groups).
    """
    y = np.asarray(y)
    p = np.asarray(p, dtype=float)
    groups = np.asarray(groups)
    w = np.asarray(w, dtype=float)
    num = den = 0.0
    used = 0
    for g in np.unique(groups):
        k = groups == g
        pos = y[k] == 1
        if pos.all() or not pos.any():
            continue
        mass = w[k][pos].sum() * w[k][~pos].sum()
        num += roc_auc_score(y[k], p[k], sample_weight=w[k]) * mass
        den += mass
        used += 1
    return (float(num / den) if den else None), used


def worth_n(panel_mae, constant, curve):
    """Convert a panel cell MAE to 'worth N real respondents'.

    curve is {n: better of raw and shrinkage MAE}. Returns a dict with label and an N when there is one.
    Prints as 'no value' when the panel cannot beat the constant baseline.
    """
    if panel_mae >= constant:
        return {"label": "no value", "n": None}
    ns = sorted(curve)
    best = np.minimum.accumulate([curve[n] for n in ns])
    if panel_mae > best[0]:
        return {"label": f"<{ns[0]}", "n": None}
    if panel_mae <= best[-1]:
        return {"label": f">={ns[-1]}", "n": None}
    for i in range(len(ns) - 1):
        hi, lo = best[i], best[i + 1]
        if lo <= panel_mae <= hi:
            if hi == lo:
                est = ns[i + 1]
            else:
                frac = (hi - panel_mae) / (hi - lo)
                est = np.exp(np.log(ns[i]) + frac * (np.log(ns[i + 1]) - np.log(ns[i])))
            return {"label": f"about {int(round(est))}", "n": int(round(est))}
    return {"label": "no value", "n": None}
