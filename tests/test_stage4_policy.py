"""The post hoc product decision: panel values stay out of reports and the duel is a health check. Also the action table, the exploration filter and the post hoc numbers. No API."""
import json

import numpy as np
import pandas as pd
import pytest

from lotte_audit import duel, duel_units, paths
from lotte_audit.agent import action, explore, ingest, report4, toolimpl
from test_stage4_product import (
    ACC,
    CFG,
    GOOD_OBJECTION,
    GOOD_QUESTION,
    LIMITS,
    LUNA,
    RULES,
    SEP,
    STAGE,
    TERRA,
    TEXT,
    StubExplorer,
    block,
    finished,
    g,
    product_ctx,
    run_dir,
    run_ingest,
    to_diagnostics,
    validity,
    write_files,
)

HELD_VALUE = "\ud328\ub110 \uac12 \uc720\uc9c0"
STATUS = STAGE["real"]["status_excluded"]
POST_HOC = paths.RESULTS / "stage4" / "duel_post_hoc.json"
DEMO8 = paths.RESULTS / "stage4" / "demo8"
STAGE4_SAMPLES = paths.RESULTS / "explore"


def with_units(real_path, units=10):
    df = pd.read_csv(real_path)
    df["unit_id"] = [f"U{i % units:03d}" for i in range(len(df))]
    df.to_csv(real_path, index=False)


def agreed_policy(tmp_path, run_length):
    doc = ingest.load_policy()
    doc["consecutive_keeps_required"] = run_length
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def fresh_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"run_id": name, "manifest_sha256": "abc"}), encoding="utf-8")
    (d / "report.md").write_text(f"{ingest.MARK_START}\nold\n{ingest.MARK_END}\n", encoding="utf-8")
    return d


# ---------- the policy ----------


def test_policy_file_defaults_to_excluded_and_says_it_is_post_hoc():
    doc = ingest.load_policy()
    assert doc["default"] == "excluded" and doc["duel_role"] == "health_check" and doc["post_hoc"] is True
    assert doc["consecutive_keeps_required"] is None and doc["fold_kind_counted"] == "unit_intact"
    assert doc["frozen_label"] == "decision_rule" and doc["frozen_label_caveat"]


def test_a_single_keep_never_puts_a_panel_value_in_a_report(tmp_path):
    real, panel = write_files(tmp_path)
    with_units(real)
    d = run_dir(tmp_path)
    doc = run_ingest(tmp_path, real, panel, d, tmp_path / "l.jsonl", "field survey")
    assert doc["duel_outcome"] == "keep"
    assert doc["panel_values_in_report"] is False and doc["panel_values_may_enter"] is False
    assert doc["report_status"] == STATUS
    text = (d / "report.md").read_text(encoding="utf-8")
    assert STATUS in text and HELD_VALUE not in text and STAGE["real"]["reason_keep"] in text
    assert doc["duel_grade"]["label_caveat"] == ingest.load_policy()["frozen_label_caveat"]


def test_every_run_is_a_health_check_in_the_ledger(tmp_path):
    real, panel = write_files(tmp_path)
    ledger = tmp_path / "l.jsonl"
    for name in ("a", "b"):
        run_ingest(tmp_path, real, panel, fresh_dir(tmp_path, name), ledger, "field survey")
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert all(r["real_results"]["health_check"]["recorded"] is True for r in rows)
    assert all(r["real_results"]["panel_values_in_report"] is False for r in rows)


def test_the_agreed_run_counts_unit_intact_keeps_only_and_a_drop_resets_it(tmp_path):
    ledger = tmp_path / "l.jsonl"
    policy = agreed_policy(tmp_path, 2)
    real, panel = write_files(tmp_path)
    # No survey unit column: recorded, never counted.
    doc = run_ingest(tmp_path, real, panel, fresh_dir(tmp_path, "cell"), ledger, "field survey", policy_path=policy)
    assert doc["fold_kind"] == ingest.CELL_STRATIFIED and doc["health_check"]["counts_toward_run"] is False and doc["health_check"]["consecutive_keeps"] == 0
    with_units(real)
    # A stand-in never counts, whatever its folds.
    doc = run_ingest(tmp_path, real, panel, fresh_dir(tmp_path, "standin"), ledger, ingest.STANDIN_LABEL, policy_path=policy)
    assert doc["health_check"]["counts_toward_run"] is False and doc["health_check"]["consecutive_keeps"] == 0
    doc = run_ingest(tmp_path, real, panel, fresh_dir(tmp_path, "one"), ledger, "field survey", policy_path=policy)
    assert doc["fold_kind"] == ingest.UNIT_INTACT and doc["health_check"]["consecutive_keeps"] == 1 and doc["panel_values_may_enter"] is False
    doc = run_ingest(tmp_path, real, panel, fresh_dir(tmp_path, "two"), ledger, "field survey", policy_path=policy)
    assert doc["health_check"]["consecutive_keeps"] == 2 and doc["panel_values_may_enter"] is True
    # Reaching the run allows a person to decide. The code still writes no panel value.
    assert doc["panel_values_in_report"] is False
    # Another panel has its own count.
    doc = run_ingest(tmp_path, real, panel, fresh_dir(tmp_path, "other"), ledger, "field survey", model=LUNA, condition="C1", policy_path=policy)
    assert doc["health_check"]["consecutive_keeps"] == 1
    # A counted drop ends the run.
    weak_real, weak_panel = write_files(tmp_path, signal=0.0)
    with_units(weak_real)
    doc = run_ingest(tmp_path, weak_real, weak_panel, fresh_dir(tmp_path, "drop"), ledger, "field survey", policy_path=policy)
    assert doc["duel_outcome"] == "drop" and doc["health_check"]["consecutive_keeps"] == 0 and doc["panel_values_may_enter"] is False


def test_the_report_states_the_policy_even_with_no_real_answers(tmp_path):
    _, _, text = finished(tmp_path)
    policy = ingest.load_policy()
    assert STATUS in text and HELD_VALUE not in text
    for line in report4.policy_lines(STAGE, policy):
        assert line in text
    assert policy["frozen_label"] in text
    assert STAGE["report"]["questionnaire_gap"] in text


def test_the_questionnaire_gap_names_the_variables_the_panel_needs():
    templates = json.loads((paths.CONFIG / "persona_templates.json").read_text(encoding="utf-8"))
    assert set(templates["c1_vars"]) == {"age", "sex", "region", "dong", "household", "occupation", "education", "marital", "income"}
    assert len(TEXT["questionnaire"]["demographics"]) == 4
    gap = STAGE["report"]["questionnaire_gap"]
    for word in TEXT["questionnaire"]["demographics"]:
        assert word in gap


# ---------- panel model and condition as input ----------


@pytest.mark.parametrize("model,condition", [("", "C1"), (" ", "C1"), (TERRA, ""), (TERRA, "x"), (None, "C1"), (TERRA, None)])
def test_ingest_refuses_without_a_named_panel(tmp_path, model, condition):
    real, panel = write_files(tmp_path)
    d = run_dir(tmp_path)
    with pytest.raises(ingest.IngestRefused, match="panel"):
        ingest.ingest(real, panel, d, tmp_path / "l.jsonl", "field survey", "tester", STAGE, model, condition)
    assert not (tmp_path / "l.jsonl").exists()


def test_the_panel_named_is_recorded_and_the_wording_follows_it(tmp_path):
    real, panel = write_files(tmp_path)
    ledger = tmp_path / "l.jsonl"
    doc = run_ingest(tmp_path, real, panel, fresh_dir(tmp_path, "luna"), ledger, "field survey", model=LUNA, condition="C1")
    assert doc["panel"] == {"model": LUNA, "condition": "C1"}
    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    assert row["real_results"]["panel"] == {"model": LUNA, "condition": "C1"}
    joined = " ".join(doc["lines"])
    assert "Luna C1" in joined and f"{LUNA} C1" in joined
    assert STAGE["real"]["grade_rate"].format(panel="Luna C1", rate="2.0%", others="Terra C2 30.0%") in doc["lines"]
    assert STAGE["real"]["grade_limit"].format(panel="Luna C1", false_keep="10.0%", missed="90.0%") in doc["lines"]


def test_a_panel_with_no_measured_rate_says_so(tmp_path):
    real, panel = write_files(tmp_path)
    doc = run_ingest(tmp_path, real, panel, fresh_dir(tmp_path, "x"), tmp_path / "l.jsonl", "field survey", model="gpt-9-sun", condition="C7")
    assert STAGE["real"]["grade_rate_unknown"].format(panel="Sun C7", others="Luna C1 2.0%, Terra C2 30.0%") in doc["lines"]


def test_a_stand_in_on_another_condition_says_what_the_demo_condition_gives(tmp_path):
    post = tmp_path / "post.json"
    post.write_text(json.dumps({"frozen_draw0_keep": {"terra_C2": True, "terra_C1": False}}), encoding="utf-8")
    real, panel = write_files(tmp_path)
    doc = ingest.ingest(real, panel, fresh_dir(tmp_path, "s"), tmp_path / "l.jsonl", ingest.STANDIN_LABEL, "tester", STAGE, TERRA, "C2", validity_path=validity(tmp_path), seed_path=tmp_path / "none.json", post_hoc_path=post)
    assert ingest.demo_condition() == "C1"
    assert STAGE["real"]["standin_condition"].format(panel="Terra C2", demo="C1", other="drop") in doc["lines"]


def test_the_ingest_tool_passes_the_registered_panel(tmp_path):
    ctx = product_ctx(tmp_path)
    to_diagnostics(ctx)
    toolimpl.decide_verdict(ctx)
    toolimpl.allocate_real_sample(ctx)
    toolimpl.build_questionnaire(ctx)
    for card in ("A", "B", "C"):
        toolimpl.explore_card(ctx, card)
    toolimpl.write_ledger(ctx)
    real, panel = write_files(tmp_path)
    ctx.real_input = {"real_csv": str(real), "panel_csv": str(panel), "source_label": "field survey", "approver": "w"}
    with pytest.raises(ingest.IngestRefused, match="panel"):
        toolimpl.ingest_real(ctx)
    ctx.real_input.update(panel_model=TERRA, panel_condition="C1")
    out = toolimpl.ingest_real(ctx)
    assert out["status"] == "done" and out["panel"] == {"model": TERRA, "condition": "C1"} and out["report_status"] == STATUS


# ---------- unit-intact folds ----------


def test_folds_keep_a_survey_unit_whole():
    rng = np.random.default_rng(1)
    units = rng.integers(0, 12, 200).astype(str)
    fold = duel_units.folds_by_unit(units, 5, np.random.default_rng(2))
    assert {len(set(fold[units == u])) for u in np.unique(units)} == {1}
    assert set(fold.tolist()) == set(range(5))


def test_the_rule_on_a_given_fold_column_is_the_frozen_rule():
    rng = np.random.default_rng(3)
    n = 200
    cells = rng.integers(0, 12, n)
    w = rng.uniform(0.5, 2.0, n)
    y = (rng.uniform(size=n) < 0.3).astype(float)
    p = np.clip(0.2 + 0.5 * y + rng.normal(0, 0.1, n), 0.01, 0.99)
    cell_age, cell_sex = np.arange(12) // 2, np.arange(12) % 2
    answers = {"a": (y, p), "b": (1 - y, 1 - p)}
    frozen = duel.duel(answers, cells, w, cell_age.astype(float), cell_sex.astype(float), [42, 5, 0])
    fold = duel.folds_by_cell(cells, 5, np.random.default_rng([42, 5, 0]))
    assert duel_units.duel_on_folds(answers, cells, w, cell_age.astype(float), cell_sex.astype(float), fold) == frozen


@pytest.mark.parametrize("edit,needle", [("few", "survey units"), ("blank", "survey unit")])
def test_ingest_refuses_bad_survey_units(tmp_path, edit, needle):
    real, panel = write_files(tmp_path)
    with_units(real, units=3 if edit == "few" else 10)
    if edit == "blank":
        df = pd.read_csv(real)
        df.loc[0, "unit_id"] = None
        df.to_csv(real, index=False)
    with pytest.raises(ingest.IngestRefused, match=needle):
        ingest.read_real(real)


# ---------- the action table ----------


def by_order(terra, luna, first):
    pair = {TERRA: terra, LUNA: luna}
    return {"by_model": {m: pair[m] for m in ([TERRA, LUNA] if first == TERRA else [LUNA, TERRA])}}


@pytest.mark.parametrize("first", [TERRA, LUNA])
def test_models_oppose_does_not_depend_on_the_model_order(first):
    terra = block(["A", "B", "C"], {"A|B": g(4.0), "A|C": g(6.0), "B|C": g(2.0)}, SEP)
    luna = block(["B", "A", "C"], {"A|B": g(-4.0), "A|C": g(1.5), "B|C": g(5.5)}, SEP)
    d = by_order(terra, luna, first)
    labels = {c: action.decide_card(c, ["A", "B", "C"], d, 5.0, True, set(), STAGE)[0] for c in "ABC"}
    assert labels["A"] == action.CANT_TELL and labels["B"] == action.CANT_TELL


def test_the_labels_of_a_mixed_case_are_the_same_in_both_orders():
    terra = block(["A", "B", "C"], {"A|B": g(4.0), "A|C": g(6.0), "B|C": g(2.0)}, SEP)
    luna = block(["B", "A", "C"], {"A|B": g(-4.0), "A|C": g(1.5), "B|C": g(5.5)}, SEP)
    one = {c: action.decide_card(c, ["A", "B", "C"], by_order(terra, luna, TERRA), 5.0, True, set(), STAGE)[0] for c in "ABC"}
    two = {c: action.decide_card(c, ["A", "B", "C"], by_order(terra, luna, LUNA), 5.0, True, set(), STAGE)[0] for c in "ABC"}
    assert one == two


def demo_like():
    terra = block(["C", "B", "A"], {"A|B": g(-2.02), "A|C": g(-4.08), "B|C": g(-2.06)}, SEP, noise=0.882)
    luna = block(["C", "B", "A"], {"A|B": g(-1.9, False), "A|C": g(-4.8), "B|C": g(-2.9)}, SEP, noise=2.231)
    return {"by_model": {TERRA: terra, LUNA: luna}}


def test_threshold_sensitivity_is_read_off_the_rule():
    rows = action.threshold_sensitivity(["A", "B", "C"], demo_like(), True, set(), STAGE)
    assert {r["limit_pp"]: r["drop_proposed"] for r in rows} == {5.0: [], 4.5: [], 4.0: ["A"], 3.0: ["A"], 2.0: ["A", "B"]}
    line = action.sensitivity_line(rows, STAGE)
    assert "5pp, 4.5pp" in line and "4pp, 3pp" in line and "2pp" in line and "A, B" in line


def test_the_action_table_carries_the_sensitivity_and_the_counts():
    roles = {"A": {"role": "candidate"}, "B": {"role": "candidate"}, "C": {"role": "candidate"}}
    doc = action.action_table(demo_like(), roles, True, [], RULES, STAGE, accuracy=ACC)
    assert [r["drop_proposed"] for r in doc["threshold_sensitivity"]] == [[], [], ["A"], ["A"], ["A", "B"]]
    assert any("A, B" in n for n in doc["notes"])
    assert "5/10" in doc["order"][0] and "10/20" in doc["order_notes"][0]


def test_pair_accuracy_counts_come_from_the_stored_file():
    assert action.pair_counts(*[action.ranking_accuracy("3_to_5pp")[i] for i in (0, 2)]) == (8, 18)
    assert action.pair_counts(*[action.ranking_accuracy("1_to_3pp")[i] for i in (0, 2)]) == (29, 36)
    roles = {"A": {"role": "candidate"}, "B": {"role": "candidate"}, "C": {"role": "candidate"}}
    doc = action.action_table(demo_like(), roles, True, [], RULES, STAGE)
    joined = " ".join(doc["order"])
    assert "8/18" in joined and "29/36" in joined and "37/54" in doc["order_notes"][0]
    assert action.RANKING_SOURCE in doc["order_notes"][0]


# ---------- the exploration filter ----------


SCENARIOS = json.loads(explore.SCENARIOS.read_text(encoding="utf-8"))


def test_the_filter_scenarios_all_pass():
    doc = explore.filter_scenarios(TEXT, STAGE, LIMITS)
    assert doc["failed"] == [] and doc["passed"] == doc["total"] == 3 * (len(SCENARIOS["drop"]) + len(SCENARIOS["keep"]))


@pytest.mark.parametrize("name", sorted(SCENARIOS["drop"]))
def test_a_planted_sentence_never_reaches_the_file_or_the_report(tmp_path, name):
    planted = SCENARIOS["drop"][name]
    ctx = product_ctx(tmp_path, explorer=StubExplorer({"objections": [planted, GOOD_OBJECTION], "attractions": [GOOD_OBJECTION], "segment_hypotheses": [GOOD_OBJECTION], "survey_questions": [GOOD_QUESTION]}))
    to_diagnostics(ctx)
    toolimpl.decide_verdict(ctx)
    out = toolimpl.explore_card(ctx, "A")
    assert out["status"] == "done" and sum(out["dropped_by_code"].values()) >= 1
    assert planted not in json.dumps(ctx.explore["A"], ensure_ascii=False)


def test_the_sentences_already_published_still_pass_the_new_filter():
    folder = STAGE4_SAMPLES / "demo7"
    if not folder.exists():
        pytest.skip("no samples")
    prefix = STAGE["explore"]["label_prefix"]
    for card in ("A", "B", "C"):
        doc = json.loads((folder / f"{card}.json").read_text(encoding="utf-8"))
        raw = {s: [x[len(prefix) :] for x in items] for s, items in doc["sections"].items()}
        got = explore.filter_output(raw, TEXT, STAGE, {s: 99 for s in LIMITS}, [], [], "")
        assert got["dropped"] == {}, card


def test_the_banner_makes_no_promise_about_the_tool():
    assert "\ub098\uc5f4\ub41c \ud615\ud0dc" in STAGE["explore"]["banner"]


# ---------- the stored numbers ----------


def posthoc():
    if not POST_HOC.exists():
        pytest.skip("post hoc file not computed")
    return json.loads(POST_HOC.read_text(encoding="utf-8"))


def test_the_post_hoc_file_says_what_it_is_and_cross_checks_the_frozen_file():
    doc = posthoc()
    assert doc["written_after_seeing_the_frozen_result"] is True and doc["cross_check_terra_C2_equals_frozen"] is True
    assert doc["frozen_label_kept_in_records"] == "decision_rule"
    assert doc["frozen_draw0_keep"]["terra_C2"] is True


def test_the_frozen_stage_4_files_are_unchanged():
    import stage4_measures as sm

    sm.check_frozen()
    frozen = json.loads((paths.RESULTS / "stage4" / "duel_validity.json").read_text(encoding="utf-8"))
    assert frozen["acceptance"]["label"] == "decision_rule" and frozen["acceptance"]["passed"] is True


def test_report_lines_quote_the_post_hoc_file():
    doc = posthoc()
    lines = report4.measure_lines(STAGE)
    joined = " ".join(lines)
    d0 = doc["same_sample"]["draw0"]["terra_C2"]
    flip = doc["same_sample"]["all_draws"]["terra_C2"]
    assert f"{100 * d0['pooled_keep_share']:.1f}%" in joined and f"{100 * flip['share_draws_decision_changes']:.1f}%" in joined
    assert str(doc["unit_intact"]["row"]["keep_rate"]["terra_C2"]["mean"]) in joined
    assert str(doc["row"]["floor_no_llm"]["pooled"]["panel_excluded"]["keep_rate"]) in joined


def test_the_measure_lines_state_the_allocation_and_flag_limits():
    joined = " ".join(report4.measure_lines(STAGE))
    assert "oracle" in joined and "2024" in joined and "2025" in joined and "train" in joined
    assert "\uac80\uc815\ub825" in joined
    alloc = json.loads((paths.RESULTS / "stage4" / "allocation.json").read_text(encoding="utf-8"))
    assert alloc["reference_sources"]["carb"].startswith("a2024") and alloc["reference_sources"]["ever"] == "train split" and alloc["reference_sources"]["weekly"] == "train split"


# ---------- demo8 ----------


def demo8():
    if not (DEMO8 / "manifest.json").exists():
        pytest.skip("demo8 not run")
    return DEMO8


def test_demo8_keeps_the_verdict_and_gaps_and_makes_no_panel_call():
    root = demo8()
    a = json.loads((root / "verdict.json").read_text(encoding="utf-8"))
    b = json.loads((paths.RESULTS / "fix_stage" / "demo6" / "verdict.json").read_text(encoding="utf-8"))
    assert a["rows"] == b["rows"]
    ad = json.loads((root / "diagnostics.json").read_text(encoding="utf-8"))
    bd = json.loads((paths.RESULTS / "fix_stage" / "demo6" / "diagnostics.json").read_text(encoding="utf-8"))
    assert ad["by_model"] == bd["by_model"]
    panel = json.loads((paths.RESULTS / "stage4" / "run_summary.json").read_text(encoding="utf-8"))["panel"]
    assert not panel.get("models") or all(m.get("attempts", 0) == 0 for m in panel["models"].values())


def test_demo8_states_the_sensitivity_on_its_own_diagnostics():
    doc = json.loads((demo8() / "action.json").read_text(encoding="utf-8"))
    assert {r["limit_pp"]: r["drop_proposed"] for r in doc["action"]["threshold_sensitivity"]} == {5.0: [], 4.5: [], 4.0: ["A"], 3.0: ["A"], 2.0: ["A", "B"]}
    assert all(r["action"] == "keep" for r in doc["action"]["rows"])


def test_demo8_report_and_records_follow_the_policy():
    root = demo8()
    text = (root / "report.md").read_text(encoding="utf-8")
    assert STATUS in text and HELD_VALUE not in text and "oracle" in text and STAGE["report"]["questionnaire_gap"] in text
    assert "8/18" in text and "29/36" in text and "37/54" in text
    doc = json.loads((root / "real_results.json").read_text(encoding="utf-8"))
    assert doc["source_label"] == ingest.STANDIN_LABEL and doc["is_real_concept_survey"] is False
    assert doc["panel"] == {"model": TERRA, "condition": "C2"} and doc["panel_values_in_report"] is False and doc["panel_values_may_enter"] is False
    assert doc["health_check"]["counts_toward_run"] is False and doc["duel_grade"]["label"] == "decision_rule" and doc["duel_grade"]["label_caveat"]
    rows = [json.loads(x) for x in (paths.RESULTS / "stage4" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    last = [r for r in rows if r.get("run_id") == "demo8" and r.get("kind") == "real_results"]
    assert len(last) == 1 and last[0]["real_results"]["report_status"] == STATUS and last[0]["human_decision"] is None


def test_demo8_stand_in_is_the_same_duel_as_demo7():
    a = json.loads((demo8() / "real_results.json").read_text(encoding="utf-8"))
    b = json.loads((paths.RESULTS / "stage4" / "demo7" / "real_results.json").read_text(encoding="utf-8"))
    assert a["anchors"] == b["anchors"] and a["duel_outcome"] == b["decision"]


def test_the_config_is_loaded_from_this_stage():
    assert CFG["models"]["main"]["id"] == TERRA
