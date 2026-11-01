"""The frozen trust map rule of the main stage. Deterministic, no randomness, no data access.

config/prereg_main.json states the rule in words and manifests/frozen_main.json holds this file's hash.
The verdict is for one item, one model and one condition. It reads aggregates only.

  comparison at n=200, per calibrated estimator: {"mean_diff": float, "ci95": [lo, hi]}
  a negative difference means the estimator's cell MAE is below E2's in the same draw.
"""

CALIBRATED = "\ubcf4\uc815 \ud6c4 \ucc38\uace0"
DIRECTION = "\ubc29\ud5a5\ub9cc"
REAL_ONLY = "\uc2e4\uce21 \uc804\uc6a9"
CALIBRATED_ESTIMATORS = ("E4", "E5", "E6")
CELL_R_MIN = 0.7
UNDERDISPERSION_RANGE = (0.5, 2.0)


def beats_e2(row, cluster):
    """Row draw interval wholly below zero and cluster draw mean below zero, for one estimator."""
    if row is None or cluster is None:
        return False
    lo_hi = row.get("ci95")
    if lo_hi is None or lo_hi[1] is None or cluster.get("mean_diff") is None:
        return False
    return bool(lo_hi[1] < 0 and cluster["mean_diff"] < 0)


def direction_checks(panel_slope, real_slope_ci, cell_r, underdispersion):
    """The three checks of the direction branch, each as a bool."""
    lo, hi = real_slope_ci if real_slope_ci is not None else (None, None)
    slope_ok = False
    if panel_slope is not None and lo is not None and hi is not None:
        slope_ok = bool((lo > 0 and hi > 0 and panel_slope > 0) or (lo < 0 and hi < 0 and panel_slope < 0))
    r_ok = cell_r is not None and bool(cell_r >= CELL_R_MIN)
    ud_ok = underdispersion is not None and bool(UNDERDISPERSION_RANGE[0] <= underdispersion <= UNDERDISPERSION_RANGE[1])
    return {"age_slope_ok": slope_ok, "cell_r_ok": r_ok, "underdispersion_ok": ud_ok}


def item_verdict(row_comparisons, cluster_comparisons, panel_slope, real_slope_ci, cell_r, underdispersion):
    """Apply the rule. Returns the label, the evidence, and the fixed ban on raw numbers."""
    winners = [e for e in CALIBRATED_ESTIMATORS if beats_e2(row_comparisons.get(e), cluster_comparisons.get(e))]
    checks = direction_checks(panel_slope, real_slope_ci, cell_r, underdispersion)
    if winners:
        label = CALIBRATED
    elif all(checks.values()):
        label = DIRECTION
    else:
        label = REAL_ONLY
    return {
        "verdict": label,
        "winning_estimators": winners,
        "direction_checks": checks,
        "level_trusted": bool(winners),
        "raw_panel_number_as_market_number": False,
    }
