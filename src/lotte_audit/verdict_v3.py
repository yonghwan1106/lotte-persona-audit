"""Trust map rule v3. Deterministic, no randomness, no data access. verdict.py (v1) and verdict_v2.py stay as they were.

WRITTEN OPENLY AFTER THE ANSWERS WERE SEEN. Stage 2 answers, the v2 table, the stand-in panel results and an outside check with a
panel holding the real answers were all known when this was written. It is not a pre-registered test of anything. Its purpose is a
first branch that can fire at all, because under v2 no panel can reach it: not even a panel holding each respondent's real answer.

Rule, for one item, one model and one condition, on the truth from test respondents outside the panel:

  CALIBRATED   a calibrated estimator beats R1: its row draw interval of cell MAE minus R1 lies wholly below zero, and its cluster
               draw mean difference is below zero too.
  UNDECIDABLE  no estimator does, and the real age slope interval includes zero. The direction branch has nothing to compare a sign
               with, so it says so instead of sending the item to real only.
  DIRECTION    no estimator does, the real slope interval excludes zero, and the three direction checks of v1 hold.
  REAL_ONLY    otherwise.

The gender gap flag is separate and never changes the label. It sits near the edge of its interval and moves with the bootstrap seed,
so a count of flagged rows is reported with its seed sensitivity and is not a fixed number.

ACCEPTANCE decides whether the labels may be read as a working rule. It is checked on controls before the rule is applied to LLM answers.
A failed acceptance means the labels must not be used as product labels, and the rule is not tuned again.
"""
from . import verdict as v1, verdict_v2

CALIBRATED = v1.CALIBRATED
DIRECTION = v1.DIRECTION
REAL_ONLY = v1.REAL_ONLY
UNDECIDABLE = "\ud310\uc815 \ubd88\uac00"
ESTIMATORS = v1.CALIBRATED_ESTIMATORS
GENDER_GAP_BAN = verdict_v2.GENDER_GAP_BAN
RULE_VERSION = 3
PREREGISTERED = False
ACCEPTANCE = {
    "real_answers_min_items_per_slot": 2,
    "slots": ("gpt-6.1-terra|C2", "gpt-6.1-terra|C1", "gpt-6-luna|C2", "gpt-6-luna|C1"),
    "items_per_slot": 3,
    "surrogate_max_of_12": 1,
}


def beats_r1(row, cluster):
    """Row interval wholly below zero and cluster mean below zero, for one estimator."""
    if not row or not cluster:
        return False
    ci = row.get("ci95")
    mean = cluster.get("mean_diff")
    if ci is None or ci[1] is None or mean is None:
        return False
    return bool(ci[1] < 0 and mean < 0)


def slope_interval_includes_zero(real_slope_ci):
    """No interval counts as including zero: without one no sign can be compared."""
    if real_slope_ci is None or real_slope_ci[0] is None or real_slope_ci[1] is None:
        return True
    lo, hi = real_slope_ci
    return bool(lo <= 0 <= hi)


def item_verdict(row_vs_r1, cluster_vs_r1, panel_slope, real_slope_ci, cell_r, underdispersion, gap_minus_real_ci):
    winners = [e for e in ESTIMATORS if beats_r1(row_vs_r1.get(e), cluster_vs_r1.get(e))]
    checks = v1.direction_checks(panel_slope, real_slope_ci, cell_r, underdispersion)
    if winners:
        label = CALIBRATED
    elif slope_interval_includes_zero(real_slope_ci):
        label = UNDECIDABLE
    elif all(checks.values()):
        label = DIRECTION
    else:
        label = REAL_ONLY
    banned = verdict_v2.gender_gap_banned(gap_minus_real_ci)
    return {
        "rule_version": RULE_VERSION,
        "verdict": label,
        "estimators_beating_r1": winners,
        "direction_checks": checks,
        "real_slope_interval_includes_zero": slope_interval_includes_zero(real_slope_ci),
        "gender_gap_use_banned": banned,
        "flags": [GENDER_GAP_BAN] if banned else [],
        "raw_panel_number_as_market_number": False,
    }


def from_v2_inputs(inputs):
    """The same inputs v2 read, stored per row by verdict_study.trust_maps."""
    return item_verdict(inputs["vs_r1_row"], inputs["vs_r1_cluster"], inputs["panel_age_slope"], inputs["real_age_slope_ci95"], inputs["cell_pearson_r"], inputs["underdispersion_ratio"], inputs["gap_minus_real_ci95"])


def apply_rows(rows):
    """v3 beside v1 and v2 for rows of verdict_study.study_answers."""
    return [{**r, "v3": from_v2_inputs(r["v2_inputs"])} for r in rows]


def count_labels(rows):
    out = {}
    for r in rows:
        out[r["v3"]["verdict"]] = out.get(r["v3"]["verdict"], 0) + 1
    return out


def acceptance(real_rows, surrogate_rows):
    """Both controls against the fixed bar. Rows must already hold v3."""
    per_slot = {}
    for slot in ACCEPTANCE["slots"]:
        model, cond = slot.split("|")
        mine = [r for r in real_rows if r["model"] == model and r["condition"] == cond]
        per_slot[slot] = {"items": len(mine), "calibrated": [r["item"] for r in mine if r["v3"]["verdict"] == CALIBRATED]}
    real_ok = all(len(v["calibrated"]) >= ACCEPTANCE["real_answers_min_items_per_slot"] and v["items"] == ACCEPTANCE["items_per_slot"] for v in per_slot.values())
    surrogate_hits = [f"{r['model']}|{r['condition']}|{r['item']}" for r in surrogate_rows if r["v3"]["verdict"] == CALIBRATED]
    surrogate_ok = len(surrogate_rows) == 12 and len(surrogate_hits) <= ACCEPTANCE["surrogate_max_of_12"]
    return {
        "bar": {k: v for k, v in ACCEPTANCE.items()},
        "real_answers_per_slot": per_slot,
        "real_answers_pass": real_ok,
        "surrogate_rows_calibrated": surrogate_hits,
        "surrogate_pass": surrogate_ok,
        "passed": bool(real_ok and surrogate_ok),
    }
