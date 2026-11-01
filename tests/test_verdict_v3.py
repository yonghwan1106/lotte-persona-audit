"""Rule v3 on hand made inputs. No data, no API."""
import json

from lotte_audit import paths, verdict_v2, verdict_v3

WIN = {"mean_diff": -2.0, "ci95": [-4.0, -0.1]}
LOSE = {"mean_diff": 1.0, "ci95": [-1.0, 3.0]}
CLUSTER_NEG = {"mean_diff": -1.0, "ci95": [-5.0, 2.0]}
CLUSTER_POS = {"mean_diff": 0.2, "ci95": [-5.0, 2.0]}
GOOD = dict(panel_slope=-9.0, real_slope_ci=[-15.0, -10.0], cell_r=0.9, underdispersion=1.0, gap_minus_real_ci=[-1.0, 1.0])


def verdict(row, cluster, **over):
    args = {**GOOD, **over}
    return verdict_v3.item_verdict({"E4": row}, {"E4": cluster}, args["panel_slope"], args["real_slope_ci"], args["cell_r"], args["underdispersion"], args["gap_minus_real_ci"])


def test_row_interval_and_cluster_mean_give_the_first_label():
    out = verdict(WIN, CLUSTER_NEG)
    assert out["verdict"] == verdict_v3.CALIBRATED and out["estimators_beating_r1"] == ["E4"]


def test_v2_would_refuse_what_v3_takes():
    assert verdict_v2.beats_r1(WIN, CLUSTER_NEG) is False
    assert verdict_v3.beats_r1(WIN, CLUSTER_NEG) is True


def test_cluster_mean_in_the_other_direction_refuses():
    assert verdict(WIN, CLUSTER_POS)["verdict"] == verdict_v3.DIRECTION


def test_row_interval_touching_zero_refuses():
    assert verdict({"mean_diff": -2.0, "ci95": [-4.0, 0.0]}, CLUSTER_NEG)["verdict"] == verdict_v3.DIRECTION


def test_real_slope_interval_with_zero_gives_undecidable_not_real_only():
    for ci in ([-2.6, 0.51], [0.0, 3.0], [-3.0, 0.0], None, [None, None]):
        assert verdict(LOSE, CLUSTER_POS, real_slope_ci=ci)["verdict"] == verdict_v3.UNDECIDABLE


def test_a_winner_comes_before_the_slope_question():
    assert verdict(WIN, CLUSTER_NEG, real_slope_ci=[-2.6, 0.51])["verdict"] == verdict_v3.CALIBRATED


def test_direction_and_real_only_branches():
    assert verdict(LOSE, CLUSTER_POS)["verdict"] == verdict_v3.DIRECTION
    assert verdict(LOSE, CLUSTER_POS, cell_r=0.5)["verdict"] == verdict_v3.REAL_ONLY
    assert verdict(LOSE, CLUSTER_POS, underdispersion=3.0)["verdict"] == verdict_v3.REAL_ONLY
    assert verdict(LOSE, CLUSTER_POS, panel_slope=2.0)["verdict"] == verdict_v3.REAL_ONLY


def test_gender_flag_is_separate_from_the_label():
    out = verdict(LOSE, CLUSTER_POS, gap_minus_real_ci=[-14.0, -1.0])
    assert out["gender_gap_use_banned"] is True and out["verdict"] == verdict_v3.DIRECTION
    assert verdict(LOSE, CLUSTER_POS, gap_minus_real_ci=None)["gender_gap_use_banned"] is True
    assert verdict(LOSE, CLUSTER_POS)["gender_gap_use_banned"] is False


def row(item, slot, label):
    model, cond = slot.split("|")
    return {"item": item, "model": model, "condition": cond, "v3": {"verdict": label}}


def rows(per_slot):
    out = []
    for slot in verdict_v3.ACCEPTANCE["slots"]:
        for i, item in enumerate(("ever", "weekly", "carb")):
            out.append(row(item, slot, verdict_v3.CALIBRATED if i < per_slot else verdict_v3.DIRECTION))
    return out


def test_acceptance_bar_real_answers():
    assert verdict_v3.acceptance(rows(2), rows(0))["passed"] is True
    assert verdict_v3.acceptance(rows(3), rows(0))["passed"] is True
    assert verdict_v3.acceptance(rows(1), rows(0))["passed"] is False


def test_acceptance_needs_every_slot():
    r = rows(2)
    for x in r:
        if x["model"] == "gpt-6-luna" and x["condition"] == "C1":
            x["v3"]["verdict"] = verdict_v3.DIRECTION
    out = verdict_v3.acceptance(r, rows(0))
    assert out["passed"] is False and out["real_answers_pass"] is False


def test_acceptance_bar_stand_in_panel():
    one = rows(0)
    one[0]["v3"]["verdict"] = verdict_v3.CALIBRATED
    assert verdict_v3.acceptance(rows(2), one)["passed"] is True
    two = rows(0)
    two[0]["v3"]["verdict"] = verdict_v3.CALIBRATED
    two[5]["v3"]["verdict"] = verdict_v3.CALIBRATED
    out = verdict_v3.acceptance(rows(2), two)
    assert out["passed"] is False and out["surrogate_pass"] is False


def test_stored_v2_inputs_go_through_v3_and_v1_v2_files_are_not_rewritten():
    stored = json.loads((paths.RESULTS / "stage3" / "verdict_v2.json").read_text(encoding="utf-8"))
    out = verdict_v3.apply_rows(stored["answers"]["rows"])
    assert len(out) == 12 and all("v3" in r and "v1" in r and "v2" in r for r in out)
    frozen = json.loads((paths.MANIFESTS / "frozen_stage3.json").read_text(encoding="utf-8"))["files"]
    assert "src/lotte_audit/verdict_v3.py" not in frozen


def test_v3_says_it_was_written_after_the_answers():
    assert verdict_v3.PREREGISTERED is False
    assert "AFTER THE ANSWERS" in verdict_v3.__doc__
