"""compare_panel_direct: after the real 200 arrive, the panel must beat a simple regression on those 200 or its values are dropped.

No real concept answers exist yet. The tests feed this function synthetic real answers and say so. Nothing in results/ has been
produced from it. It is one function, not a path: nothing receives real survey answers, nothing builds a panel value per real
respondent, and nothing writes its result into a report. Those steps are not built. Only the tests call this function.

Scoring is cross validation inside the real respondents. Each fold fits on the other folds only, so a respondent never scores their
own fit. Folds keep survey units whole. The bootstrap resamples units and keeps the pairing of estimators.
"""
import numpy as np

from .. import calibration, verdict_v2

SYNTHETIC_LABEL = "SYNTHETIC REAL ANSWERS, TEST ONLY"


def folds_by_unit(units, k, seed):
    """Fold number per row with whole units in a fold."""
    uniq, inv = np.unique(np.asarray(units), return_inverse=True)
    order = np.random.default_rng(seed).permutation(len(uniq))
    fold_of_unit = np.zeros(len(uniq), dtype=int)
    fold_of_unit[order] = np.arange(len(uniq)) % k
    return fold_of_unit[inv]


def _brier(p, y):
    return (np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2


def out_of_fold(y, weights, age_order, sex, panel_p, units, k, seed):
    """Held out predictions of the direct mean, the raw panel, the calibrated panel and R1."""
    n = len(y)
    fold = folds_by_unit(units, k, seed)
    cells = np.unique(np.column_stack([age_order, sex]), axis=0, return_inverse=True)
    table, cell_of = cells[0], cells[1].ravel()
    out = {"direct_mean": np.zeros(n), "panel_raw": calibration.clip(panel_p), "panel_calibrated": np.zeros(n), "r1": np.zeros(n)}
    for f in range(k):
        test = fold == f
        train = ~test
        out["direct_mean"][test] = np.average(y[train], weights=weights[train])
        d = calibration.fit_offset(panel_p[train], y[train], weights[train])
        out["panel_calibrated"][test] = calibration.expit(calibration.logit(panel_p[test]) + d)
        by_cell = calibration.age_sex_model_cells(y[train], weights[train], cell_of[train], table[:, 0].astype(float), table[:, 1].astype(float))
        out["r1"][test] = by_cell[cell_of[test]]
    return out


def compare_panel_direct(y, weights, age_order, sex, panel_p, units, has_invitation_list=True, k=5, draws=2000, seed=20261102):
    """y is a real 0/1 answer per respondent, panel_p the panel's value for the same respondent's cell or persona.

    Returns the side by side losses and whether the panel values must be dropped from this decision.
    The panel stays only when the bootstrap interval of the Brier difference, calibrated panel minus R1, lies wholly below zero.
    It reads a helper of verdict_v2 but it is not the v2 test: verdict_v2.beats_r1 compares cell MAE in repeated row and cluster
    draws, while this compares one person level Brier loss, cross validated inside the real sample, under a survey unit bootstrap.
    """
    y = np.asarray(y, dtype=float)
    weights = np.asarray(weights, dtype=float)
    age_order = np.asarray(age_order, dtype=float)
    sex = np.asarray(sex, dtype=float)
    panel_p = np.asarray(panel_p, dtype=float)
    units = np.asarray(units)
    if not has_invitation_list:
        return {
            "calibration_possible": False,
            "panel_values_dropped": True,
            "report_line": "calibration impossible, direct estimate only",
            "rule": "invitation list and response status are required for calibration",
        }
    preds = out_of_fold(y, weights, age_order, sex, panel_p, units, k, seed)
    losses = {name: _brier(p, y) for name, p in preds.items()}
    uniq, inv = np.unique(units, return_inverse=True)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(uniq), size=(draws, len(uniq)))
    counts = np.vstack([np.bincount(picks[i], minlength=len(uniq)) for i in range(draws)])
    den = counts @ np.bincount(inv, weights=weights, minlength=len(uniq))

    def boot_diff(a, b):
        diff = 100.0 * (losses[a] - losses[b]) * weights
        sums = np.bincount(inv, weights=diff, minlength=len(uniq))
        boots = (counts @ sums) / den
        lo, hi = np.percentile(boots, [2.5, 97.5])
        mean = float(np.sum(diff) / np.sum(weights))
        return {"mean_diff": round(mean, 4), "ci95": [round(float(lo), 4), round(float(hi), 4)]}

    against_r1 = boot_diff("panel_calibrated", "r1")
    panel_stays = verdict_v2._wholly_below_zero(against_r1)
    return {
        "calibration_possible": True,
        "brier_x100": {name: round(float(100.0 * np.average(v, weights=weights)), 4) for name, v in losses.items()},
        "panel_calibrated_minus_r1": against_r1,
        "panel_raw_minus_r1": boot_diff("panel_raw", "r1"),
        "panel_calibrated_minus_direct_mean": boot_diff("panel_calibrated", "direct_mean"),
        "panel_values_dropped": not panel_stays,
        "rule": "panel values stay only if the interval of calibrated panel minus R1 lies wholly below zero",
        "default": "follow the real answers when panel and real answers disagree",
    }
