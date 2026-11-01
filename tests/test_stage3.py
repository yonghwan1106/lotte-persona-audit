"""Tests for stage 3. All HTTP is mocked and all answers are synthetic. Real-data tests skip without the key."""
import hashlib
import json
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

import main_run
import panel_run
import stage3_run
from lotte_audit import main_score, option_ranking as rank, paths, splits, verdict, verdict_study, verdict_v2
from test_main_run import synthetic_context

ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "s" + "k-" + "unit-test-not-a-real-key-000000"
USAGE = {"input_tokens": 1000, "output_tokens": 300, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 150}}
GOOD = {f: round(1 / 17, 4) for f in stage3_run.FIELDS}
SLOPE_CI = [-8.0, -2.0]


def body(answer=None):
    return {"status": "completed", "model": "served", "service_tier": "default", "usage": USAGE, "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer or GOOD)}]}]}


def comparison(mean, lo, hi):
    return {"mean_diff": mean, "ci95": [lo, hi]}


WIN = {"E4": comparison(-1.0, -2.0, -0.1)}
LOSE = {"E4": comparison(-1.0, -2.0, 0.1)}


def v2(row_r1=None, cluster_r1=None, row_e2=None, cluster_e2=None, slope=-5.0, ci=SLOPE_CI, r=0.9, ud=1.0, gap=(-1.0, 1.0)):
    return verdict_v2.item_verdict(row_r1 or {}, cluster_r1 or {}, row_e2 or {}, cluster_e2 or {}, slope, ci, r, ud, gap)


# ---------- rule v2 ----------


def test_calibrated_needs_the_same_estimator_below_r1_in_both_draw_kinds():
    assert v2(WIN, WIN)["verdict"] == verdict_v2.CALIBRATED
    assert v2(WIN, WIN)["estimators_beating_r1"] == ["E4"]
    assert v2({"E4": WIN["E4"]}, {"E5": WIN["E4"]})["verdict"] == verdict_v2.DIRECTION


@pytest.mark.parametrize("row,cluster", [(WIN, LOSE), (LOSE, WIN), (LOSE, LOSE), ({"E4": comparison(-1.0, -2.0, 0.0)}, WIN), (WIN, {"E4": comparison(+1.0, 0.5, 2.0)})])
def test_an_interval_touching_or_above_zero_is_not_a_win_over_r1(row, cluster):
    assert v2(row, cluster)["estimators_beating_r1"] == []


def test_row_mean_with_cluster_mean_only_is_not_enough_unlike_v1():
    row_only = {"E4": comparison(-1.0, -2.0, -0.1)}
    cluster_mean_negative = {"E4": comparison(-1.0, -3.0, 1.0)}
    assert verdict.item_verdict(row_only, cluster_mean_negative, -5.0, SLOPE_CI, 0.9, 1.0)["verdict"] == verdict.CALIBRATED
    assert v2(row_only, cluster_mean_negative)["verdict"] == verdict_v2.DIRECTION


def test_beating_e2_alone_gives_no_calibrated_label_and_is_named_beats_e2():
    out = v2(LOSE, LOSE, WIN, WIN, r=0.2)
    assert out["verdict"] == verdict_v2.REAL_ONLY
    assert out["beats_e2"] is True and out["estimators_beating_e2"] == ["E4"]
    assert "level_trusted" not in out


@pytest.mark.parametrize(
    "slope,ci,r,ud,expected",
    [
        (-5.0, SLOPE_CI, 0.7, 0.5, verdict_v2.DIRECTION),
        (-5.0, SLOPE_CI, 0.7, 2.0, verdict_v2.DIRECTION),
        (-5.0, SLOPE_CI, 0.69, 1.0, verdict_v2.REAL_ONLY),
        (-5.0, SLOPE_CI, 0.9, 2.01, verdict_v2.REAL_ONLY),
        (-5.0, SLOPE_CI, 0.9, 0.49, verdict_v2.REAL_ONLY),
        (5.0, SLOPE_CI, 0.9, 1.0, verdict_v2.REAL_ONLY),
        (-5.0, [-3.0, 1.0], 0.9, 1.0, verdict_v2.REAL_ONLY),
        (None, SLOPE_CI, 0.9, 1.0, verdict_v2.REAL_ONLY),
    ],
)
def test_direction_branch_boundaries(slope, ci, r, ud, expected):
    assert v2(slope=slope, ci=ci, r=r, ud=ud)["verdict"] == expected


@pytest.mark.parametrize("gap,banned", [((-1.0, 1.0), False), ((0.0, 1.0), False), ((0.1, 1.0), True), ((-2.0, -0.1), True), (None, True), ((None, None), True)])
def test_gender_flag_is_set_when_the_interval_excludes_zero_and_never_changes_the_label(gap, banned):
    out = v2(WIN, WIN, gap=gap)
    assert out["gender_gap_use_banned"] is banned
    assert out["flags"] == ([verdict_v2.GENDER_GAP_BAN] if banned else [])
    assert out["verdict"] == verdict_v2.CALIBRATED


def test_flag_text_is_the_korean_label():
    assert verdict_v2.GENDER_GAP_BAN == "\uc131\ubcc4 \ucc28\uc774 \uc0ac\uc6a9 \uae08\uc9c0"


def test_raw_panel_number_is_never_a_market_number_under_any_label():
    for out in (v2(WIN, WIN), v2(), v2(r=0.1)):
        assert out["raw_panel_number_as_market_number"] is False


def test_v2_states_it_is_not_preregistered_for_the_stage_2_answers():
    assert verdict_v2.PREREGISTERED_FOR_STAGE2_ANSWERS is False
    assert "NOT PRE-REGISTERED" in verdict_v2.__doc__
    prereg = json.loads(stage3_run.PREREG.read_text(encoding="utf-8"))
    assert prereg["part1_verdict"]["status"].startswith("NOT PRE-REGISTERED")


def test_v1_view_renames_only_the_field():
    out = verdict.item_verdict(WIN, WIN, -5.0, SLOPE_CI, 0.9, 1.0)
    view = verdict_v2.v1_view(out)
    assert view["beats_e2"] is out["level_trusted"] and "level_trusted" not in view
    assert view["verdict"] == out["verdict"] and view["winning_estimators"] == out["winning_estimators"]


def test_v1_module_is_byte_identical_to_the_stage_2_freeze():
    frozen = json.loads(main_run.FROZEN.read_text(encoding="utf-8"))["files"]
    for name in ("src/lotte_audit/verdict.py", "src/lotte_audit/main_score.py", "src/lotte_audit/calibration.py", "src/main_run.py"):
        got = hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        assert got == frozen[name], name
    assert "level_trusted" in (ROOT / "src/lotte_audit/verdict.py").read_text(encoding="utf-8")


# ---------- study path on synthetic answers ----------

PLAN = {"repeats": 40, "seed": 42, "pi_draws": 500, "pi_seed": 43, "bootstrap": 60}


@pytest.fixture(scope="module")
def study():
    ctx, answers = synthetic_context()
    return ctx, answers, verdict_study.study_answers(ctx, answers, PLAN)


def test_side_by_side_rows_hold_both_rules(study):
    ctx, answers, doc = study
    assert len(doc["rows"]) == len(answers) * len(ctx["items"])
    for row in doc["rows"]:
        assert "beats_e2" in row["v1"] and "level_trusted" not in row["v1"]
        assert row["v2"]["rule_version"] == 2


def test_an_age_only_panel_cannot_beat_r1(study):
    _, _, doc = study
    good = [r for r in doc["rows"] if r["model"] == "gpt-6.1-terra"]
    assert all(r["v2"]["verdict"] != verdict_v2.CALIBRATED for r in good)
    assert any(r["v1"]["verdict"] == verdict.CALIBRATED for r in good)


def test_outside_diagnostics_use_no_panel_row(study):
    ctx, answers, _ = study
    keep = verdict_study.outside_mask(ctx)
    assert keep.sum() == len(ctx["test"]["w"]) - len(ctx["panel"]["w"])
    assert not keep[ctx["panel"]["positions_in_test"]].any()
    diag = verdict_study.outside_diagnostics(ctx, answers, 20, 42)
    t = ctx["items"][0]
    from lotte_audit import metrics

    expected = metrics.gender_gap(ctx["test"]["y"][t][keep], ctx["test"]["w"][keep], ctx["test"]["sexes"][keep])
    assert diag[t]["real_gender_gap_pp"] == pytest.approx(expected, abs=0.001)


def test_comparisons_are_taken_on_the_outside_truth_for_the_rule():
    ctx, answers = synthetic_context()
    plan = {**PLAN, "repeats": 12}
    run = main_score.calibration_study(ctx, answers, [200], ["row", "cluster"], plan["repeats"], plan["seed"], plan["pi_draws"], plan["pi_seed"])
    comps = verdict_study.comparisons(run, answers, ctx["items"])
    t = ctx["items"][0]
    key = "gpt-6.1-terra|C2|E4"
    r = run[(200, "row")]
    assert comps["row"][key][t]["vs_r1_outside"]["mean_diff"] == pytest.approx(np.mean(np.array(r["mae_outside"][key][t]) - np.array(r["mae_outside"]["R1"][t])), abs=0.001)
    assert comps["row"][key][t]["vs_e2_whole"]["mean_diff"] == pytest.approx(np.mean(np.array(r["mae"][key][t]) - np.array(r["mae"]["E2"][t])), abs=0.001)


def test_markdown_renders_side_by_side(study):
    ctx, answers, doc = study
    full = {"answers": doc, "surrogate": doc, "positive_control": {**doc, "auc": {r["model"]: {t: 0.5 for t in ctx["items"]} for r in doc["rows"]}}, "v1_reproduced_from_main_score": True}
    text = verdict_study.to_markdown(full)
    assert "not pre-registered" in text
    assert "beats_e2" in text and "level_trusted" in text
    assert verdict_v2.GENDER_GAP_BAN in text


# ---------- ranking metrics ----------


def test_average_ranks_match_pandas():
    x = np.array([0.1, 0.3, 0.3, 0.0, 0.3, 0.9])
    assert rank.average_ranks(x).tolist() == pd.Series(x).rank().tolist()


def test_spearman_by_hand_and_constant():
    assert rank.spearman(np.array([1.0, 2.0, 3.0]), np.array([3.0, 4.0, 5.0])) == pytest.approx(1.0)
    assert rank.spearman(np.array([3.0, 2.0, 1.0]), np.array([1.0, 2.0, 3.0])) == pytest.approx(-1.0)
    assert np.isnan(rank.spearman(np.array([1.0, 1.0, 1.0]), np.array([1.0, 2.0, 3.0])))


def test_pair_scores_by_hand_with_ties_and_no_true_gap():
    truth = np.array([0.50, 0.30, 0.20, 0.00])
    est = np.array([0.40, 0.40, 0.10, 0.10])
    t_gap, e_gap, score = rank.pair_scores(est, truth)
    # pairs (0,1) (0,2) (0,3) (1,2) (1,3) (2,3)
    assert t_gap == pytest.approx([20, 30, 50, 10, 30, 20])
    assert e_gap == pytest.approx([0, 30, 30, 30, 30, 0])
    assert score.tolist() == [0.5, 1.0, 1.0, 1.0, 1.0, 0.5]
    _, _, with_tie = rank.pair_scores(np.array([0.2, 0.1]), np.array([0.3, 0.3]))
    assert np.isnan(with_tie[0])


def test_reversed_pair_scores_zero():
    assert rank.pair_scores(np.array([0.1, 0.9]), np.array([0.8, 0.2]))[2].tolist() == [0.0]


@pytest.mark.parametrize("gap,band", [(0.5, "under_1pp"), (1.0, "1_to_3pp"), (2.999, "1_to_3pp"), (3.0, "3_to_5pp"), (5.0, "5pp_and_over"), (40.0, "5pp_and_over")])
def test_gap_band_boundaries(gap, band):
    truth = np.array([0.5 + gap / 200, 0.5 - gap / 200])
    m = rank.metrics_one(truth.copy(), truth, ((1,), (2,)))
    assert m[f"true_gap|{band}|n_pairs"] == 1
    assert m[f"true_gap|{band}|accuracy"] == 1.0
    assert sum(m[f"true_gap|{n}|n_pairs"] for n, _, _ in rank.GAP_BANDS) == 1


def test_estimate_equal_to_truth_scores_perfectly():
    truth = np.array([0.4, 0.3, 0.2, 0.08, 0.02])
    m = rank.metrics_one(truth.copy(), truth, tuple((o,) for o in range(1, 6)))
    assert m["spearman"] == pytest.approx(1.0) and m["pair_accuracy"] == 1.0
    assert m["top3_overlap"] == 3 and m["share_mae_pp"] == pytest.approx(0.0)
    assert m["bias|1"] == pytest.approx(0.0)


def test_mae_bias_and_top3_by_hand():
    truth = np.array([0.5, 0.3, 0.15, 0.05])
    est = np.array([0.1, 0.2, 0.3, 0.4])
    m = rank.metrics_one(est, truth, tuple((o,) for o in range(1, 5)))
    assert m["share_mae_pp"] == pytest.approx(100 * np.mean([0.4, 0.1, 0.15, 0.35]))
    assert m["bias|1"] == pytest.approx(-40.0) and m["bias|4"] == pytest.approx(35.0)
    assert m["top3_overlap"] == 2


def test_top_k_breaks_ties_by_position():
    assert rank.top_k(np.array([0.2, 0.2, 0.2, 0.2])) == {0, 1, 2}


def test_option_sets_merge_coffee_drop_16_and_renormalise():
    assert rank.OPTION_SETS["merged_coffee_15"][12] == (13, 14)
    assert len(rank.OPTION_SETS["merged_coffee_15"]) == 15 and len(rank.OPTION_SETS["no_16"]) == 16 and len(rank.OPTION_SETS["all_17"]) == 17
    assert all(16 not in c and 14 not in c or c == (13, 14) for c in rank.OPTION_SETS["merged_coffee_15"])
    shares = np.zeros(17)
    shares[12], shares[13], shares[15], shares[0] = 0.25, 0.25, 0.25, 0.25
    out = rank.collapse(shares, rank.OPTION_SETS["merged_coffee_15"])
    assert out.sum() == pytest.approx(1.0)
    assert out[12] == pytest.approx(2 / 3) and out[0] == pytest.approx(1 / 3)


def test_normalise_records_raw_sum_and_refuses_zero():
    raw = np.array([[0.5] * 17, [1 / 17] * 17])
    norm, sums = rank.normalise_answers(raw)
    assert norm.sum(axis=1) == pytest.approx([1.0, 1.0])
    assert sums[0] == pytest.approx(8.5)
    check = rank.sum_check(sums)
    assert check["max"] == 8.5 and check["share_over_0_05_from_1"] == 0.5
    with pytest.raises(ValueError):
        rank.normalise_answers(np.zeros((1, 17)))


def ranking_context(seed=11, n_truth=1300, n_gate=300, n_pool=632):
    rng = np.random.default_rng(seed)
    probs = np.array([0.1, 0.02, 0.12, 0.02, 0.08, 0.06, 0.05, 0.02, 0.03, 0.06, 0.03, 0.02, 0.17, 0.17, 0.02, 0.0, 0.03])
    probs = probs / probs.sum()
    draw = lambda n: rng.choice(np.arange(1, 18), size=n, p=probs)  # noqa: E731
    truth_units = np.repeat(np.arange(200), 7)[:n_truth]
    gate_units = rng.integers(0, 200, n_gate)
    pool_units = 1000 + np.repeat(np.arange(51), 13)[:n_pool]
    krei = rank.group_shares(rank.one_hot(draw(3000)), np.ones(3000), rng.integers(4, 10, 3000))
    train = rank.group_shares(rank.one_hot(draw(2900)), np.ones(2900), rng.integers(4, 10, 2900))
    truth_w = rng.lognormal(0, 0.3, n_truth)
    return {
        "truth": {"options": draw(n_truth), "w": truth_w, "w_poststratified": truth_w * 1.1, "ages": rng.integers(4, 10, n_truth), "units": truth_units},
        "gate": {"options": draw(n_gate), "w": rng.lognormal(0, 0.3, n_gate), "ages": rng.integers(4, 10, n_gate), "units": gate_units},
        "pool": {"options": draw(n_pool), "w": rng.lognormal(0, 0.3, n_pool), "ages": rng.integers(4, 10, n_pool), "units": pool_units},
        "krei_2024": krei,
        "train": train,
    }, probs


RANK_PLAN = {"draws": 15, "seed": 42, "pi_draws": 200, "pi_seed": 43, "bootstrap": 40}


@pytest.fixture(scope="module")
def ranked():
    ctx, probs = ranking_context()
    rng = np.random.default_rng(12)
    good = np.tile(probs, (300, 1)) + rng.normal(0, 0.001, (300, 17))
    good = np.clip(good, 1e-4, 1)
    reverse = np.tile(probs.max() - probs + 0.001, (300, 1))
    answers = {"C2": rank.normalise_answers(good)[0], "C1": rank.normalise_answers(reverse)[0]}
    return ctx, rank.score_ranking(ctx, answers, RANK_PLAN)


def test_a_right_panel_outranks_a_reversed_panel(ranked):
    _, r = ranked
    e = r["sets"]["all_17"]["groups"]["overall"]["estimators"]
    assert e["panel_C2"]["spearman"]["value"] > 0.6
    assert e["panel_C1"]["spearman"]["value"] < -0.6
    assert e["panel_C2"]["pair_accuracy"]["value"] > e["panel_C1"]["pair_accuracy"]["value"]
    assert e["panel_C2"]["pair_accuracy"]["ci95"][0] > 0.5


def test_krei_is_scored_only_on_comparable_sets(ranked):
    _, r = ranked
    assert "krei_2024" not in r["sets"]["all_17"]["groups"]["overall"]["estimators"]
    for s in rank.KREI_SETS:
        assert "krei_2024" in r["sets"][s]["groups"]["overall"]["estimators"]
        assert "panel_C2_minus_krei_2024" in r["sets"][s]["groups"]["overall"]["differences"]


def test_every_group_and_comparator_has_the_same_metrics(ranked):
    _, r = ranked
    for s in rank.OPTION_SETS:
        for g in rank.GROUPS:
            block = r["sets"][s]["groups"][g]
            names = set(block["estimators"]["panel_C2"]) - {"_shares_pct"}
            assert names == set(block["direct"]["direct_row"]) == set(block["direct"]["direct_cluster"])
            assert block["estimators"]["panel_C2"]["spearman"]["resamples_used"] == RANK_PLAN["bootstrap"]


def test_operating_rule_is_on_the_primary_set_with_all_bands(ranked):
    _, r = ranked
    rows = r["operating_rule"]
    assert len(rows) == 2 * 2 * len(rank.GAP_BANDS)
    assert {x["gap_kind"] for x in rows} == {"true_gap", "estimated_gap"}


def test_scoring_is_deterministic():
    ctx, probs = ranking_context()
    answers = {"C2": rank.normalise_answers(np.tile(probs + 0.001, (300, 1)))[0]}
    plan = {**RANK_PLAN, "bootstrap": 10, "draws": 5}
    assert json.dumps(rank.score_ranking(ctx, answers, plan)) == json.dumps(rank.score_ranking(ctx, answers, plan))


def test_group_with_no_row_takes_the_overall_share():
    out = rank.group_shares(rank.one_hot(np.array([1, 1, 2])), np.ones(3), np.array([4, 4, 5]))
    assert out["70+"].tolist() == out["overall"].tolist()
    assert out["19-29"][0] == 1.0


def test_unit_table_matches_a_direct_weighted_mean():
    rng = np.random.default_rng(4)
    opts = rng.integers(1, 18, 200)
    w = rng.uniform(0.5, 2, 200)
    ages = rng.integers(4, 10, 200)
    units = rng.integers(0, 20, 200)
    table = rank.UnitTable(rank.one_hot(opts), w, ages, units, 20)
    counts = np.bincount(rng.integers(0, 20, 20), minlength=20).astype(float)
    rows = np.concatenate([np.flatnonzero(units == u) for u in range(20) for _ in range(int(counts[u]))])
    assert table.shares(counts, "overall") == pytest.approx(rank.weighted_shares(rank.one_hot(opts)[rows], w[rows]))
    mask = ages[rows] == 7
    assert table.shares(counts, "50-59") == pytest.approx(rank.weighted_shares(rank.one_hot(opts)[rows][mask], w[rows][mask]))


def test_markdown_renders_every_section(ranked):
    _, r = ranked
    labels = {str(o): f"label{o}" for o in rank.OPTIONS}
    meta = {"frame": "frame", "sum_check": {}, "truth_rows": 1, "truth_units": 1, "scored": [], "incomplete": []}
    text = rank.to_markdown(r, labels, meta)
    for section in ("Truth shares", "Option set merged_coffee_15", "Pair accuracy by true gap band", "Per age band", "Per option bias", "Frozen operating rule", "post-stratified"):
        assert section in text


# ---------- prompt and config ----------


@pytest.fixture()
def frozen():
    return stage3_run.load_config()


def test_prompt_has_the_gate_framing_and_exact_a15_wording(frozen):
    _, template = frozen
    gate = json.loads((paths.CONFIG / "gate_prompt.json").read_text(encoding="utf-8"))
    assert template.startswith(gate["instruction"] + "\n\n" + gate["question_a15"] + "\n\n")
    assert template.endswith("\n\n----\n\n[\uc751\ub2f5\uc790]\n{PERSONA}")
    assert "A19" not in template and "p_carb" not in template
    for f in stage3_run.FIELDS:
        assert template.count(f + ":") == 1


def test_prompt_gives_no_rate_and_no_hint(frozen):
    _, template = frozen
    head = template.split("----")[0]
    # The only percent sign is the printed option 1 wording.
    assert head.count("%") == 1 and "100% " in head
    spec = json.loads(stage3_run.PROMPT.read_text(encoding="utf-8"))["output_spec"]
    assert "%" not in spec and "\ud569" not in spec
    assert not set(spec) & set("\u2248\xb1")


def test_config_matches_the_gate_on_the_request(frozen):
    cfg, template = frozen
    gate_cfg, _ = panel_run.load_config()
    assert cfg["request"] == gate_cfg["request"]
    assert cfg["request"]["store"] is False and cfg["request"]["reasoning_effort"] == "medium"
    assert cfg["models"]["main"]["id"] == "gpt-6.1-terra" and list(cfg["models"]) == ["main"]
    assert cfg["limits"]["budget_usd"] == 3.0
    assert panel_run.template_sha256(template) == cfg["prompt_sha256"]


@pytest.mark.parametrize("field,value,match", [("request", {"reasoning_effort": "high"}, "request"), ("endpoint", "https://example.invalid", "endpoint")])
def test_config_differing_from_the_gate_is_refused(monkeypatch, tmp_path, field, value, match):
    cfg = json.loads(stage3_run.RUN_CONFIG.read_text(encoding="utf-8"))
    cfg[field] = {**cfg[field], **value} if isinstance(value, dict) else value
    changed = tmp_path / "stage3_run.json"
    changed.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(stage3_run, "RUN_CONFIG", changed)
    with pytest.raises(RuntimeError, match=match):
        stage3_run.load_config()


def test_changed_prompt_is_refused(monkeypatch, tmp_path):
    doc = json.loads(stage3_run.PROMPT.read_text(encoding="utf-8"))
    doc["template"] = doc["template"].replace("A15", "A16", 1)
    changed = tmp_path / "prompt.json"
    changed.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(stage3_run, "PROMPT", changed)
    with pytest.raises(RuntimeError, match="stage3_prompt"):
        stage3_run.load_config()


def test_frozen_change_is_refused(monkeypatch, tmp_path):
    if not stage3_run.FROZEN.exists() or not stage3_run.KEY.exists():
        pytest.skip("stage 3 not frozen yet")
    key = stage3_run.load_key()
    doc = json.loads(stage3_run.FROZEN.read_text(encoding="utf-8"))
    doc["files"]["src/stage3_run.py"] = "0" * 64
    moved = tmp_path / "frozen.json"
    moved.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(stage3_run, "FROZEN", moved)
    with pytest.raises(RuntimeError, match="frozen files changed"):
        stage3_run.check_frozen(key)


# ---------- runner ----------


def persona_items(n=3, cond="C2"):
    return [{"condition": cond, "code": f"CODE{i:04d}", "persona": f"PERSONA-MARKER {i}"} for i in range(n)]


def runner(frozen, tmp_path, handler, ledger=None):
    cfg, template = frozen
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return stage3_run.Stage3Runner(cfg, template, cfg["models"]["main"]["id"], FAKE_KEY, client=client, log_path=tmp_path / "calls.jsonl", cache_dir=tmp_path / "cache", sleep=lambda s: None, ledger=ledger or panel_run.Ledger(cfg["limits"]["budget_usd"]))


def test_one_call_per_respondent_with_the_frozen_request(frozen, tmp_path):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=body())

    r = runner(frozen, tmp_path, handler)
    out = r.run(persona_items(3))
    assert out["counts"]["called"] == 3 and len(seen) == 3
    for req in seen:
        assert req["model"] == "gpt-6.1-terra" and req["store"] is False and req["reasoning"]["effort"] == "medium"
        assert "temperature" not in req
        assert req["text"]["format"]["strict"] is True
        assert set(req["text"]["format"]["schema"]["required"]) == set(stage3_run.FIELDS) and len(stage3_run.FIELDS) == 17
        assert req["input"][0]["content"][0]["text"].count("PERSONA-MARKER") == 1


def test_cached_answer_is_not_called_again_and_raw_sum_is_stored(frozen, tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=body())

    runner(frozen, tmp_path, handler).run(persona_items(2))
    second = runner(frozen, tmp_path, handler).run(persona_items(2))
    assert len(calls) == 2 and second["counts"]["cached"] == 2
    record = json.loads(next((tmp_path / "cache" / "gpt-6.1-terra").glob("*.json")).read_text(encoding="utf-8"))
    assert record["raw_sum"] == pytest.approx(sum(GOOD.values()))


def test_log_holds_no_persona_text_and_no_key(frozen, tmp_path):
    runner(frozen, tmp_path, lambda request: httpx.Response(200, json=body())).run(persona_items(2))
    log = (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    assert "PERSONA-MARKER" not in log and FAKE_KEY not in log


@pytest.mark.parametrize(
    "answer",
    [
        {f: 0.0 for f in stage3_run.FIELDS},
        {f: 0.1 for f in stage3_run.FIELDS[:-1]},
        {**GOOD, "opt_01": 1.5},
        {**GOOD, "extra": 0.1},
        {**GOOD, "opt_02": True},
    ],
)
def test_bad_answers_are_refused(answer):
    with pytest.raises(panel_run.AnswerError):
        stage3_run.parse_answer(body(answer))


def test_values_that_do_not_sum_to_one_are_valid():
    got = stage3_run.parse_answer(body({f: 0.2 for f in stage3_run.FIELDS}))
    assert sum(got.values()) == pytest.approx(3.4)


def test_budget_stop(frozen, tmp_path):
    cfg, _ = frozen
    r = runner(frozen, tmp_path, lambda request: httpx.Response(200, json=body()), ledger=panel_run.Ledger(cfg["limits"]["budget_usd"], spent=cfg["limits"]["budget_usd"] - 0.001))
    out = r.run(persona_items(4))
    assert out["stop_reason"] == "budget" and out["counts"]["called"] == 0


def test_empty_balance_stops_at_once(frozen, tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, json={"error": {"type": "insufficient_quota", "code": "insufficient_quota"}})

    r = runner(frozen, tmp_path, handler)
    r.concurrency = 1
    out = r.run(persona_items(5))
    assert out["stop_reason"] == "insufficient_quota" and len(calls) == 1


def test_retry_on_server_error_then_success(frozen, tmp_path):
    answers = iter([httpx.Response(500, json={}), httpx.Response(200, json=body())])
    out = runner(frozen, tmp_path, lambda request: next(answers)).run(persona_items(1))
    assert out["counts"]["called"] == 1


def test_run_all_follows_the_frozen_order_and_stops_later_conditions(frozen, tmp_path):
    cfg, template = frozen
    order = []

    def handler(request):
        text = json.loads(request.content)["input"][0]["content"][0]["text"]
        order.append(text.rsplit("MARK", 1)[1][:2])
        return httpx.Response(429, json={"error": {"type": "insufficient_quota", "code": "insufficient_quota"}})

    items = {c: [{"condition": c, "code": f"{c}CODE01", "persona": f"MARK{c}"}] for c in cfg["run_order"]}
    client = httpx.Client(transport=httpx.MockTransport(handler))
    _, complete = stage3_run.run_all(cfg, template, None, None, FAKE_KEY, client=client, sleep=lambda s: None, log_path=tmp_path / "c.jsonl", cache_dir=tmp_path / "cache", items_by_condition=items, progress=None)
    assert complete is False and order == ["C2"]


def test_partial_answers_are_not_scored(frozen, tmp_path):
    cfg, template = frozen
    items = persona_items(3)
    key = pd.DataFrame({"condition": "C2", "code": [i["code"] for i in items], "row_index": [1, 2, 3]})
    personas = {i["code"]: i["persona"] for i in items}
    calls = iter([httpx.Response(200, json=body())] * 2)
    r = runner(frozen, tmp_path, lambda request: next(calls))
    r.concurrency = 1
    r.run(items[:2])
    assert stage3_run.load_answers(cfg["models"]["main"]["id"], "C2", key, personas, template, cache_dir=tmp_path / "cache") is None
    r2 = runner(frozen, tmp_path, lambda request: httpx.Response(200, json=body()))
    r2.run(items)
    got = stage3_run.load_answers(cfg["models"]["main"]["id"], "C2", key, personas, template, cache_dir=tmp_path / "cache")
    assert got.shape == (3, 17)


# ---------- real data, synthetic answers ----------


@pytest.fixture(scope="module")
def stage_key():
    if not stage3_run.KEY.exists():
        pytest.skip("stage 3 key not present; run src/stage3_run.py prepare")
    return stage3_run.load_key()


def test_real_key_is_the_gates_300_in_c1_and_c2(key, stage_key):
    assert len(stage_key) == 600 and stage_key["code"].is_unique
    for cond in ("C1", "C2"):
        got = stage_key.loc[stage_key.condition == cond].set_index("code").sort_index()
        gate = key.loc[key.condition == cond].set_index("code").sort_index()
        assert got.index.tolist() == gate.index.tolist()
        assert got["row_index"].tolist() == gate["row_index"].tolist()
        assert got["panel_weight"].tolist() == pytest.approx(gate["panel_weight"].tolist())


def test_real_truth_excludes_all_panel_respondents(real, stage_key):
    df = real["df"]
    main_key = main_run.load_key()
    ctx = stage3_run.build_ranking_context(df, stage3_run.load_2024(), main_key, stage_key)
    mk = splits.masks(splits.load_manifest(df))
    assert len(ctx["truth"]["w"]) == int(mk["test"].sum()) - 1000
    assert len(ctx["gate"]["w"]) == 300
    assert len(ctx["pool"]["w"]) == 632
    assert all(abs(v.sum() - 1) < 1e-9 for v in ctx["krei_2024"].values())


def test_real_ranking_path_runs_on_synthetic_answers(real, stage_key):
    df = real["df"]
    ctx = stage3_run.build_ranking_context(df, stage3_run.load_2024(), main_run.load_key(), stage_key)
    rng = np.random.default_rng(3)
    answers = {"C2": rank.normalise_answers(rng.uniform(0.01, 1, (300, 17)))[0]}
    r = rank.score_ranking(ctx, answers, {"draws": 3, "seed": 42, "pi_draws": 100, "pi_seed": 43, "bootstrap": 5})
    dumped = json.dumps(r)
    assert list(r["truth_shares_pct"]) == list(rank.GROUPS)
    for code in stage_key["code"].head(100):
        assert code not in dumped


def test_real_surrogate_path_runs_without_any_answer_file(real):
    df = real["df"]
    main_key = main_run.load_key()
    mk = splits.masks(splits.load_manifest(df))
    from lotte_audit import data

    targets = data.derive_targets(df)
    t_rows = main_key.loc[(main_key.split == "test") & (main_key.condition == "C1")].sort_values("row_index")["row_index"].to_numpy()
    c_rows = main_key.loc[(main_key.split == "calibration") & (main_key.condition == "C1")].sort_values("row_index")["row_index"].to_numpy()
    fake = verdict_study.surrogate_answers(df, targets, mk["train"], t_rows, c_rows)
    assert list(fake) == ["gpt-6.1-terra|C2", "gpt-6.1-terra|C1", "gpt-6-luna|C2", "gpt-6-luna|C1"]
    assert fake["gpt-6.1-terra|C2"]["test"]["ever"].shape == (1000,)
    again = verdict_study.surrogate_answers(df, targets, mk["train"], t_rows, c_rows)
    assert (fake["gpt-6-luna|C1"]["calibration"]["carb"] == again["gpt-6-luna|C1"]["calibration"]["carb"]).all()
    control = verdict_study.known_signal_answers(df, targets, mk["train"], t_rows, c_rows, [1.0])
    y = targets["ever"].to_numpy()[t_rows]
    p = control["control_s1.0|C2"]["test"]["ever"]
    assert p[y == 1].mean() > p[y == 0].mean()


def test_committed_stage3_results_hold_no_codes(stage_key):
    folder = paths.RESULTS / "stage3"
    if not folder.exists():
        pytest.skip("no stage 3 results yet")
    text = "".join(p.read_text(encoding="utf-8") for p in folder.glob("*"))
    assert not [c for c in stage_key["code"] if c in text]
