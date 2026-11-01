"""The duel with no outside truth: calibrated panel E4 against the age and sex logistic R1, inside one real sample.

The rule is fixed in config/prereg_stage4.json, block A3_duel. Pure numbers, no file and no API. All functions take arrays, so stored answers,
controls, ingested answers and synthetic answers take the same path. Nothing per respondent is returned.
"""
import numpy as np
from scipy import stats

from . import calibration as cal

FOLDS = 5
LOSS_CLIP = 1e-6
T_975 = float(stats.t.ppf(0.975, FOLDS - 1))


def folds_by_cell(cells, k, rng):
    """Fold number per row. Inside each cell the rows are shuffled and dealt in turn, and the counter runs on across cells."""
    cells = np.asarray(cells)
    fold = np.zeros(len(cells), dtype=int)
    start = 0
    for c in np.unique(cells):
        where = np.flatnonzero(cells == c)
        rng.shuffle(where)
        fold[where] = (start + np.arange(len(where))) % k
        start = (start + len(where)) % k
    return fold


def log_loss(p, y):
    p = np.clip(np.asarray(p, dtype=float), LOSS_CLIP, 1 - LOSS_CLIP)
    y = np.asarray(y, dtype=float)
    return -(y * np.log(p) + (1 - y) * np.log1p(-p))


def r1_fold_losses(y, w, cells, cell_age, cell_sex, fold, k=FOLDS):
    """Weighted R1 log loss in each held out fold. Kept apart because every panel of a draw shares it."""
    out = np.zeros(k)
    for f in range(k):
        test = fold == f
        train = ~test
        by_cell = cal.age_sex_model_cells(y[train], w[train], cells[train], cell_age, cell_sex)
        out[f] = np.average(log_loss(by_cell[cells[test]], y[test]), weights=w[test])
    return out


def panel_fold_losses(y, w, p, fold, k=FOLDS):
    """Weighted log loss of the offset calibrated panel in each held out fold, the offset fit on the other folds."""
    out = np.zeros(k)
    for f in range(k):
        test = fold == f
        train = ~test
        d = cal.fit_offset(p[train], y[train], w[train])
        out[f] = np.average(log_loss(cal.expit(cal.logit(p[test]) + d), y[test]), weights=w[test])
    return out


def decide(fold_improvements):
    """The fixed rule on the k fold improvements (R1 loss minus panel loss, positive favours the panel)."""
    d = np.asarray(fold_improvements, dtype=float)
    k = len(d)
    mean = float(d.mean())
    half = float(stats.t.ppf(0.975, k - 1) * d.std(ddof=1) / np.sqrt(k))
    lo, hi = mean - half, mean + half
    return {"mean_improvement": mean, "interval": [lo, hi], "keep": bool(lo > 0), "excludes_zero": bool(lo > 0 or hi < 0)}


def duel(answers_by_item, cells, w, cell_age, cell_sex, seed, k=FOLDS):
    """One duel. answers_by_item maps an item to (y, p) over the same respondents. Returns pooled and per item decisions.

    cells are 0..m-1 with cell_age and cell_sex indexed by them. seed is what numpy default_rng takes, so a duel is repeatable.
    """
    cells = np.asarray(cells)
    w = np.asarray(w, dtype=float)
    fold = folds_by_cell(cells, k, np.random.default_rng(seed))
    improvements, per_item = {}, {}
    for item, (y, p) in answers_by_item.items():
        y = np.asarray(y, dtype=float)
        p = np.asarray(p, dtype=float)
        r1 = r1_fold_losses(y, w, cells, cell_age, cell_sex, fold, k)
        panel = panel_fold_losses(y, w, p, fold, k)
        improvements[item] = r1 - panel
        per_item[item] = {**decide(improvements[item]), "r1_loss": float(r1.mean()), "panel_loss": float(panel.mean())}
    pooled = decide(np.mean([improvements[i] for i in improvements], axis=0))
    return {"folds": k, "pooled": pooled, "per_item": per_item}


def rounded(block, digits=5):
    out = dict(block)
    for name in ("mean_improvement", "r1_loss", "panel_loss"):
        if name in out:
            out[name] = round(out[name], digits)
    out["interval"] = [round(x, digits) for x in out["interval"]]
    return out
