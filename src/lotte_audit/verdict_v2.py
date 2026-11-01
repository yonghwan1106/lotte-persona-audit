"""Trust map rule v2. Deterministic, no randomness, no data access. verdict.py (v1) stays as it was and is shown beside it.

NOT PRE-REGISTERED WITH RESPECT TO THE STAGE 2 ANSWERS. v2 was written after those answers were seen, because
v1 labelled all 12 combinations the same and a non-LLM stand-in panel took 11 of 12. Treat a v2 label on the
stage 2 answers as a stricter reading of data already seen, not as a confirmatory test.

The verdict is for one item, one model and one condition. It reads aggregates only.

  comparison at n=200, per calibrated estimator: {"mean_diff": float, "ci95": [lo, hi]}
  against R1: estimator cell MAE minus R1 cell MAE in the same draw, on the truth that excludes panel respondents.
  a negative difference means the estimator is better than R1.
"""
from . import verdict as v1

CALIBRATED = v1.CALIBRATED
DIRECTION = v1.DIRECTION
REAL_ONLY = v1.REAL_ONLY
CALIBRATED_ESTIMATORS = v1.CALIBRATED_ESTIMATORS
GENDER_GAP_BAN = "\uc131\ubcc4 \ucc28\uc774 \uc0ac\uc6a9 \uae08\uc9c0"
RULE_VERSION = 2
PREREGISTERED_FOR_STAGE2_ANSWERS = False


def _wholly_below_zero(comparison):
    if comparison is None:
        return False
    ci = comparison.get("ci95")
    return ci is not None and ci[1] is not None and bool(ci[1] < 0)


def beats_r1(row, cluster):
    """The interval is wholly below zero under both draw kinds, for one estimator."""
    return _wholly_below_zero(row) and _wholly_below_zero(cluster)


def gender_gap_banned(gap_minus_real_ci):
    """True when the panel minus real gender gap interval excludes zero. No interval means no clearance, so it is banned."""
    if gap_minus_real_ci is None or gap_minus_real_ci[0] is None or gap_minus_real_ci[1] is None:
        return True
    lo, hi = gap_minus_real_ci
    return bool(lo > 0 or hi < 0)


def item_verdict(row_vs_r1, cluster_vs_r1, row_vs_e2, cluster_vs_e2, panel_slope, real_slope_ci, cell_r, underdispersion, gap_minus_real_ci):
    """Apply v2. The label comes from R1 and the direction checks; the gender flag is separate and never changes the label."""
    winners = [e for e in CALIBRATED_ESTIMATORS if beats_r1(row_vs_r1.get(e), cluster_vs_r1.get(e))]
    checks = v1.direction_checks(panel_slope, real_slope_ci, cell_r, underdispersion)
    if winners:
        label = CALIBRATED
    elif all(checks.values()):
        label = DIRECTION
    else:
        label = REAL_ONLY
    wins_e2 = [e for e in CALIBRATED_ESTIMATORS if v1.beats_e2(row_vs_e2.get(e), cluster_vs_e2.get(e))]
    banned = gender_gap_banned(gap_minus_real_ci)
    return {
        "rule_version": RULE_VERSION,
        "verdict": label,
        "estimators_beating_r1": winners,
        "direction_checks": checks,
        "beats_e2": bool(wins_e2),
        "estimators_beating_e2": wins_e2,
        "gender_gap_use_banned": banned,
        "flags": [GENDER_GAP_BAN] if banned else [],
        "raw_panel_number_as_market_number": False,
    }


def v1_view(result):
    """A v1 output with its misleading level_trusted field shown as beats_e2. verdict.py itself is not touched."""
    out = {k: v for k, v in result.items() if k != "level_trusted"}
    out["beats_e2"] = result["level_trusted"]
    return out
