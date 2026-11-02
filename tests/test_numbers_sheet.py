"""The numbers sheet is generated and every entry can be traced. No API call."""
import json
import re

import pytest

from lotte_audit import paths

SHEET = paths.RESULTS / "numbers_sheet.json"


@pytest.fixture(scope="module")
def sheet():
    if not SHEET.exists():
        pytest.skip("numbers sheet not built yet")
    return json.loads(SHEET.read_text(encoding="utf-8"))


def by_key(sheet):
    return {r["key"]: r for r in sheet["rows"]}


def test_the_person_approved_run_has_its_own_entries_and_its_spend_adds_up(sheet):
    rows = {r["key"]: r["value"] for r in sheet["rows"]}
    ledger = [json.loads(x) for x in (paths.RESULTS / "stage4" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    row = next(r for r in ledger if r.get("run_id") == "human2")
    before = json.loads((paths.RESULTS / "stage4" / "run_summary.json").read_text(encoding="utf-8"))["stage_spent_usd"]
    assert rows["stage4.human2.approval.channel"] == "terminal" and rows["stage4.human2.manifest_sha256"] == row["manifest_sha256"]
    assert rows["spend.stage4.through_human2"] == row["cost"]["stage_total_usd"]
    assert rows["spend.stage4.human2.run"] == pytest.approx(row["cost"]["stage_total_usd"] - before, abs=1e-6)
    assert rows["spend.stage4.human2.panel"] + rows["spend.stage4.human2.explore"] == pytest.approx(rows["spend.stage4.human2.run"], abs=2e-6)
    assert rows["spend.all_stages_through_human2"] == pytest.approx(rows["spend.all_stages_including_attacks"] + rows["spend.stage4.human2.run"], abs=1e-6)
    assert rows["stage4.human2.calls.new_answers"] + rows["stage4.human2.calls.answers_from_cache"] == rows["stage4.human2.plan.answers"]
    assert rows["stage4.human2.real_results_is_empty"] is True and rows["stage4.human2.human_decision_is_empty"] is True


def test_every_entry_has_all_fields_and_a_tracked_source(sheet):
    assert sheet["entries"] == len(sheet["rows"]) > 500
    assert len({r["key"] for r in sheet["rows"]}) == len(sheet["rows"])
    for r in sheet["rows"]:
        assert set(r) == {"key", "value", "unit", "source", "stage", "caveat"}, r["key"]
        assert r["value"] is not None and r["unit"] and r["stage"] and r["caveat"]
        assert (paths.ROOT / r["source"]).exists() or r["source"] == "results/numbers_sheet.json", r["key"]


def test_values_equal_their_source_files(sheet):
    rows = by_key(sheet)
    main = json.loads((paths.RESULTS / "main" / "main_score.json").read_text(encoding="utf-8"))
    cal = main["calibration"]["200|row"]
    e4 = cal["estimators"]["gpt-6.1-terra|C2|E4"]["average"]
    assert rows["stage2.n200.row.terra_C2.E4.average.minus_E2.mean_diff"]["value"] == e4["mean_diff"]
    assert rows["stage2.n200.row.terra_C2.E4.average.minus_E2.ci95"]["value"] == e4["ci95"]
    r1 = cal["difference_to_R1"]["gpt-6.1-terra|C2|E6"]["average"]
    assert rows["stage2.n200.row.terra_C2.E6.average.minus_R1.mean_diff"]["value"] == r1["mean_diff"]
    assert rows["stage2.noise_floor.average"]["value"] == main["reference"]["noise_floor_average_pp"]
    rank = json.loads((paths.RESULTS / "stage3" / "option_ranking.json").read_text(encoding="utf-8"))
    panel = rank["sets"]["merged_coffee_15"]["groups"]["overall"]["estimators"]["panel_C2"]
    assert rows["ranking.merged_coffee_15.panel_C2.spearman.value"]["value"] == panel["spearman"]["value"]
    assert rows["ranking.merged_coffee_15.panel_C2.pair_accuracy.value"]["value"] == panel["pair_accuracy"]["value"]
    assert rows["stage2.panel_share_of_test_psfwt"]["value"] == 58.56


def test_the_named_groups_are_all_there(sheet):
    keys = {r["key"] for r in sheet["rows"]}
    for needed in (
        "gate.terra.C2.average_cell_mae",
        "stage2.n200.row.E2.average.cell_mae",
        "stage2.n200.row.terra_C2.E3.average.cell_mae",
        "stage2.n200.row.R1.average.cell_mae",
        "stage2.n200.row.terra_C2.E5.average.minus_R1.ci95",
        "stage2.person.ever.terra_C2.auc_minus_floor",
        "stage2.stability.ever.mean_abs_diff_pp",
        "ranking.merged_coffee_15.panel_C2_minus_krei_2024.pair_accuracy.ci95",
        "demo.terra.noise_upper",
        "cost.gate_prompt.terra.C2.per_respondent_usd",
        "cost.gate_prompt.terra.C2.per_300_panel_usd",
        "cost.concept_prompt.luna.six_cards.per_300_panel_usd",
        "spend.gate",
        "spend.stage2",
        "spend.stage3",
        "spend.agent_stage",
        "spend.wf7_attacks",
        "spend.fix_stage",
        "tests.passed",
        "scenarios.fix_stage.runs",
        "attacks.replay.live.total",
        "attacks.wf7.probe.kept_minus_clean_t2b_pp",
        "spend.stage4",
        "stage4.allocation.R1.panel_excluded.cell_mae.panel_neyman_minus_proportional.average.ci95",
        "stage4.allocation.R1.panel_excluded.national_error.panel_minus_reference.average.mean_diff",
        "stage4.flags.terra_minus_luna.spearman_ci95",
        "stage4.flags.repeat_sd.overlap_top9.observed",
        "stage4.duel.acceptance.passed",
        "stage4.duel.row.terra_C2.pooled.panel_excluded.false_keep_rate",
        "stage4.duel.row.control_s1.0.pooled.panel_excluded.keep_rate",
        "stage4.duel.seed.draw_seed_99.acceptance_passed",
        "stage4.detectable.between_mde_pp",
        "stage4.detectable.needed.gap_5pp.between_total",
        "stage4.demo7.action.A",
        "stage4.ingest.decision",
        "stage4.explore.A.objections.kept",
        "stage4.posthoc.row.terra_C1.keep_rate",
        "stage4.posthoc.row.terra_C1.beats_rate",
        "stage4.posthoc.row.floor_no_llm.keep_rate",
        "stage4.posthoc.row.floor_no_llm.beats_rate",
        "stage4.posthoc.unit_intact.row.terra_C2.keep_rate_mean",
        "stage4.posthoc.unit_intact.cluster.surrogate_terra_slot.keep_rate_mean",
        "stage4.posthoc.same_sample.draw0.terra_C2.pooled_keep_share",
        "stage4.posthoc.same_sample.all_draws.terra_C2.share_draws_decision_changes",
        "stage4.policy.default",
        "stage4.pair_accuracy.1_to_3pp.pairs_right",
        "stage4.demo8.action.A",
        "stage4.demo8.threshold.2pp.drop_proposed",
        "stage4.demo8.ingest.report_status",
        "stage4.demo8.ingest.panel_condition",
        "stage4.explore8.A.objections.kept",
        "stage4.explore_filter.passed",
    ):
        assert needed in keys, needed


def test_stage_spend_adds_up(sheet):
    rows = by_key(sheet)
    parts = ("spend.gate", "spend.stage2", "spend.stage3", "spend.agent_stage", "spend.wf7_attacks", "spend.fix_stage", "spend.stage4")
    assert rows["spend.all_stages_including_attacks"]["value"] == pytest.approx(sum(rows[k]["value"] for k in parts), abs=1e-5)


def test_sheet_holds_no_row_level_values(sheet):
    text = SHEET.read_text(encoding="utf-8")
    key_path = paths.ROOT / "runs" / "stage3" / "key.csv"
    if key_path.exists():
        codes = {line.split(",")[1] for line in key_path.read_text(encoding="utf-8").splitlines()[1:]}
        assert not set(re.findall(r"\b[A-Z0-9]{8}\b", text)) & codes
    assert ".secrets" not in text and "Users" not in text


def test_a_caveat_goes_with_the_numbers_that_need_one(sheet):
    rows = by_key(sheet)
    assert "E2" in rows["stage2.n200.row.terra_C2.E4.average.minus_E2.mean_diff"]["caveat"]
    assert "R1" in rows["stage2.n200.row.terra_C2.E4.average.minus_R1.mean_diff"]["caveat"]
    assert "\uc2dc\ub4dc" in rows["verdict.gender_flag.count.stage2_seed"]["caveat"]
    assert "\uac00\uc0c1" in rows["demo.terra.noise_upper"]["caveat"]
    assert "\uc81c\ud488 \ub77c\ubca8" in rows["verdict.v3.acceptance_passed"]["caveat"]
    assert "\uc2e4\uc81c \uc124\ubb38\uc744 \ub9cc\ub09c \uc801\uc774 \uc5c6\uc2b5\ub2c8\ub2e4" in rows["stage4.ingest.decision"]["caveat"]
    assert "\ucf58\uc149\ud2b8" in rows["stage4.duel.acceptance.passed"]["caveat"]


def test_stage4_values_equal_their_source_files(sheet):
    rows = by_key(sheet)
    alloc = json.loads((paths.RESULTS / "stage4" / "allocation.json").read_text(encoding="utf-8"))
    r = alloc["reading"]["panel_minus_proportional_r1_average"]
    assert rows["stage4.allocation.R1.panel_excluded.cell_mae.panel_neyman_minus_proportional.average.mean_diff"]["value"] == r["mean_diff"]
    duel = json.loads((paths.RESULTS / "stage4" / "duel_validity.json").read_text(encoding="utf-8"))
    assert rows["stage4.duel.row.terra_C2.pooled.panel_excluded.keep_rate"]["value"] == duel["row"]["terra_C2"]["pooled"]["panel_excluded"]["keep_rate"]
    assert rows["stage4.duel.acceptance.label"]["value"] == duel["acceptance"]["label"]


def test_post_hoc_values_equal_their_source_file_and_carry_the_caveat(sheet):
    rows = by_key(sheet)
    doc = json.loads((paths.RESULTS / "stage4" / "duel_post_hoc.json").read_text(encoding="utf-8"))
    assert rows["stage4.posthoc.row.terra_C1.keep_rate"]["value"] == doc["row"]["terra_C1"]["pooled"]["panel_excluded"]["keep_rate"]
    assert rows["stage4.posthoc.row.floor_no_llm.beats_rate"]["value"] == doc["row"]["floor_no_llm"]["pooled"]["panel_excluded"]["beats_rate"]
    assert rows["stage4.posthoc.unit_intact.row.terra_C2.keep_rate_mean"]["value"] == doc["unit_intact"]["row"]["keep_rate"]["terra_C2"]["mean"]
    assert rows["stage4.posthoc.same_sample.draw0.terra_C2.pooled_keep_share"]["value"] == doc["same_sample"]["draw0"]["terra_C2"]["pooled_keep_share"]
    assert rows["stage4.posthoc.same_sample.all_draws.terra_C2.share_draws_decision_changes"]["value"] == doc["same_sample"]["all_draws"]["terra_C2"]["share_draws_decision_changes"]
    assert "\uc0ac\ud6c4" in rows["stage4.posthoc.row.terra_C1.keep_rate"]["caveat"]


def test_the_frozen_label_goes_out_only_with_its_caveat(sheet):
    rows = by_key(sheet)
    assert rows["stage4.duel.acceptance.label"]["value"] == "decision_rule"
    assert "\uac74\uac15\uac80\uc9c4" in rows["stage4.duel.acceptance.label"]["caveat"]
    assert "\uac74\uac15\uac80\uc9c4" in rows["stage4.duel.acceptance.passed"]["caveat"]
