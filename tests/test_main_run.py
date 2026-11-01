"""Tests for the main stage. All HTTP is mocked and all answers are synthetic. Real-data tests skip without the key."""
import json
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

import main_run
import panel_run
from lotte_audit import baselines, calibration as cal, data, main_score, metrics, paths, splits, verdict

ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "s" + "k-" + "unit-test-not-a-real-key-000000"
GOOD = {"p_zero_ever": 0.4, "p_zero_weekly": 0.1, "p_carb_top1": 0.05}
USAGE = {"input_tokens": 1000, "output_tokens": 200, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 150}}
SLOPE_CI = [-8.0, -2.0]


def body():
    return {"status": "completed", "model": "served", "service_tier": "default", "usage": USAGE, "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(GOOD)}]}]}


def comparison(mean, lo, hi):
    return {"mean_diff": mean, "ci95": [lo, hi]}


# ---------- verdict rule ----------


def test_labels_match_the_preregistration():
    labels = json.loads(main_run.PREREG.read_text(encoding="utf-8"))["F_verdict"]["labels"]
    assert labels == {"calibrated": verdict.CALIBRATED, "direction": verdict.DIRECTION, "real_only": verdict.REAL_ONLY}


def test_calibrated_needs_row_interval_below_zero_and_cluster_same_direction():
    row = {"E4": comparison(-1.0, -2.0, -0.1)}
    v = verdict.item_verdict(row, {"E4": comparison(-0.5, -3.0, 2.0)}, -5.0, SLOPE_CI, 0.9, 1.0)
    assert v["verdict"] == verdict.CALIBRATED
    assert v["winning_estimators"] == ["E4"]
    assert v["level_trusted"] is True


def test_row_win_with_cluster_in_the_other_direction_is_not_calibrated():
    v = verdict.item_verdict({"E5": comparison(-1.0, -2.0, -0.1)}, {"E5": comparison(0.2, -1.0, 1.0)}, -5.0, SLOPE_CI, 0.9, 1.0)
    assert v["verdict"] == verdict.DIRECTION
    assert v["level_trusted"] is False


def test_interval_touching_zero_or_above_is_not_a_win():
    for lo, hi in ((-2.0, 0.0), (-2.0, 0.5), (0.1, 2.0)):
        v = verdict.item_verdict({"E6": comparison(-0.5, lo, hi)}, {"E6": comparison(-0.5, -1, 0)}, -5.0, SLOPE_CI, 0.9, 1.0)
        assert v["winning_estimators"] == []


def test_winner_must_be_the_same_estimator_in_both_draw_kinds():
    v = verdict.item_verdict({"E4": comparison(-1, -2, -0.1), "E5": comparison(0.5, 0.1, 1)}, {"E4": comparison(0.5, 0, 1), "E5": comparison(-0.5, -1, 0)}, -5.0, SLOPE_CI, 0.3, 1.0)
    assert v["verdict"] == verdict.REAL_ONLY


@pytest.mark.parametrize(
    "slope,ci,r,ud,expected",
    [
        (-5.0, [-8.0, -2.0], 0.7, 0.5, verdict.DIRECTION),
        (-5.0, [-8.0, -2.0], 0.7, 2.0, verdict.DIRECTION),
        (3.0, [1.0, 4.0], 0.9, 1.0, verdict.DIRECTION),
        (5.0, [-8.0, -2.0], 0.9, 1.0, verdict.REAL_ONLY),
        (-5.0, [-8.0, 1.0], 0.9, 1.0, verdict.REAL_ONLY),
        (-5.0, [-8.0, -2.0], 0.699, 1.0, verdict.REAL_ONLY),
        (-5.0, [-8.0, -2.0], 0.9, 0.49, verdict.REAL_ONLY),
        (-5.0, [-8.0, -2.0], 0.9, 2.01, verdict.REAL_ONLY),
        (None, [-8.0, -2.0], 0.9, 1.0, verdict.REAL_ONLY),
        (-5.0, [-8.0, -2.0], None, 1.0, verdict.REAL_ONLY),
        (-5.0, [-8.0, -2.0], 0.9, None, verdict.REAL_ONLY),
    ],
)
def test_direction_branch_boundaries(slope, ci, r, ud, expected):
    assert verdict.item_verdict({}, {}, slope, ci, r, ud)["verdict"] == expected


def test_raw_panel_number_is_never_a_market_number_under_any_label():
    cases = [
        verdict.item_verdict({"E4": comparison(-1, -2, -1)}, {"E4": comparison(-1, -2, 0)}, -5, SLOPE_CI, 0.9, 1),
        verdict.item_verdict({}, {}, -5, SLOPE_CI, 0.9, 1),
        verdict.item_verdict({}, {}, 5, SLOPE_CI, 0.1, 9),
    ]
    assert [c["verdict"] for c in cases] == [verdict.CALIBRATED, verdict.DIRECTION, verdict.REAL_ONLY]
    assert all(c["raw_panel_number_as_market_number"] is False for c in cases)


# ---------- estimators ----------


def test_offset_fit_matches_the_weighted_total():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.1, 0.6, 500)
    y = (rng.uniform(size=500) < p * 0.5).astype(float)
    w = rng.uniform(0.5, 2.0, 500)
    d = cal.fit_offset(p, y, w)
    assert d < 0
    assert abs(np.sum(w * cal.expit(cal.logit(p) + d)) - np.sum(w * y)) < 1e-6


def test_offset_is_bounded_when_one_class():
    p = np.full(10, 0.3)
    assert cal.fit_offset(p, np.zeros(10), np.ones(10)) == -cal.OFFSET_BOUND
    assert cal.fit_offset(p, np.ones(10), np.ones(10)) == cal.OFFSET_BOUND


def test_recalibration_recovers_known_coefficients():
    rng = np.random.default_rng(2)
    lp = rng.normal(0, 1.5, 20000)
    p = cal.expit(lp)
    y = (rng.uniform(size=len(p)) < cal.expit(-1.0 + 0.5 * lp)).astype(float)
    a, b, status = cal.fit_recalibration(p, y, np.ones(len(p)))
    assert status == "ok"
    assert abs(a + 1.0) < 0.05 and abs(b - 0.5) < 0.05


def test_recalibration_matches_sklearn_with_weights():
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(3)
    lp = rng.normal(0, 1.0, 400)
    p = cal.expit(lp)
    y = (rng.uniform(size=400) < cal.expit(0.3 + 0.7 * lp)).astype(int)
    w = rng.uniform(0.2, 3.0, 400)
    a, b, _ = cal.fit_recalibration(p, y, w)
    ref = LogisticRegression(C=1e8, max_iter=2000).fit(lp[:, None], y, sample_weight=w * 400 / w.sum())
    assert abs(a - ref.intercept_[0]) < 1e-3 and abs(b - ref.coef_[0][0]) < 1e-3


def test_recalibration_falls_back_on_one_class():
    a, b, status = cal.fit_recalibration(np.full(20, 0.3), np.zeros(20), np.ones(20))
    assert status == "fallback_one_class" and b == 1.0 and a == -cal.OFFSET_BOUND


def test_age_sex_model_matches_sklearn_and_uses_no_panel():
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(11)
    n = 400
    cells = rng.integers(0, 12, n)
    cell_age = np.array([i // 2 for i in range(12)], dtype=float)
    cell_sex = np.array([i % 2 for i in range(12)], dtype=float)
    y = (rng.uniform(size=n) < cal.expit(0.5 - 0.4 * cell_age[cells] + 0.2 * cell_sex[cells])).astype(int)
    w = rng.uniform(0.3, 3.0, n)
    got = cal.age_sex_model_cells(y, w, cells, cell_age, cell_sex)
    x = np.column_stack([cell_age[cells], cell_sex[cells]])
    ref = LogisticRegression(C=1e8, max_iter=3000).fit(x, y, sample_weight=w * n / w.sum())
    want = ref.predict_proba(np.column_stack([cell_age, cell_sex]))[:, 1]
    assert np.abs(got - want).max() < 1e-3


def test_age_sex_model_uses_the_sample_mean_on_one_class():
    got = cal.age_sex_model_cells(np.zeros(20), np.ones(20), np.arange(20) % 4, np.array([0.0, 0.0, 1.0, 1.0]), np.array([0.0, 1.0, 0.0, 1.0]))
    assert got.tolist() == [0.0, 0.0, 0.0, 0.0]


def test_clip_handles_exact_zero_and_one():
    assert np.isfinite(cal.logit(np.array([0.0, 1.0]))).all()
    assert cal.clip(np.array([0.0, 1.0])).tolist() == [0.001, 0.999]


def test_direct_and_shrunk_equal_the_existing_baseline():
    rng = np.random.default_rng(4)
    n = 300
    cells = rng.integers(0, 12, n)
    y = (rng.uniform(size=n) < 0.2 + cells * 0.03).astype(float)
    w = rng.uniform(0.5, 2.0, n)
    truth = {i: 0.1 + 0.05 * i for i in range(12)}
    curve = baselines.real_sample_curve(y, w, cells, truth, repeats=1, sizes=(n,))
    direct, shrunk = cal.direct_and_shrunk(y, w, cells, 12)
    arr = np.array([truth[i] for i in range(12)])
    assert abs(cal.cell_mae(direct, arr) - curve[n]["raw"]) < 1e-9
    assert abs(cal.cell_mae(shrunk, arr) - curve[n]["shrunk"]) < 1e-9


def test_cell_mae_equals_the_gate_metric():
    est = {i: 0.1 * i for i in range(5)}
    tru = {i: 0.1 * i + 0.02 for i in range(5)}
    assert abs(cal.cell_mae(np.array(list(est.values())), np.array(list(tru.values()))) - metrics.cell_mae(est, tru)) < 1e-12


def test_empty_cells_fall_back():
    y = np.array([1.0, 0.0, 1.0, 1.0])
    w = np.ones(4)
    cells = np.array([0, 0, 1, 1])
    direct, shrunk = cal.direct_and_shrunk(y, w, cells, 3)
    assert direct[2] == pytest.approx(0.75)
    assert shrunk[2] == pytest.approx(0.75)
    est = cal.difference_estimate(np.full(4, 0.5), y, w, cells, np.array([0.4, 0.4, 0.4]), np.ones(3), np.array([0, 1, 2]), 3)
    assert est[2] == pytest.approx(0.4 + 0.25)


def test_difference_estimator_by_hand_with_shrinkage_and_clip():
    y = np.array([1.0, 1.0, 0.0, 0.0])
    p = np.array([0.5, 0.5, 0.5, 0.5])
    w = np.ones(4)
    cells = np.array([0, 0, 1, 1])
    est = cal.difference_estimate(p, y, w, cells, np.array([0.2, 0.2]), np.ones(2), np.array([0, 1]), 2, k=2)
    # Global residual is 0. Cell 0 residual 0.5 with count 2 and k 2 shrinks to 0.25, cell 1 to -0.25, clipped at 0.
    assert est.tolist() == pytest.approx([0.45, 0.0])


# ---------- draws ----------


def pool_for_draws():
    rng = np.random.default_rng(5)
    units = np.repeat(np.arange(40), rng.integers(5, 25, 40))
    n = len(units)
    w = rng.lognormal(0, 0.7, n) * (1 + (units % 3))
    # The answer rises with the weight, so a double-weighted mean is visibly too high.
    y = (rng.uniform(size=n) < np.clip(0.05 + 0.1 * w, 0, 0.95)).astype(float)
    return w, units, y


@pytest.mark.parametrize("kind", ["row", "cluster"])
def test_sample_weights_repair_the_draw_and_do_not_double_weight(kind):
    w, units, y = pool_for_draws()
    target = float(np.average(y, weights=w))
    draws = cal.make_draws(w, units, 100, kind, 600, 42, 4000, 43)
    repaired = np.mean([np.average(y[i], weights=wt) for i, wt in draws])
    doubled = np.mean([np.average(y[i], weights=w[i]) for i, _ in draws])
    assert abs(repaired - target) < 0.02
    assert doubled - target > 2 * abs(repaired - target)


def test_cluster_draws_take_whole_units_until_n_reached():
    w, units, _ = pool_for_draws()
    sizes = pd.Series(units).value_counts()
    for idx, _ in cal.make_draws(w, units, 100, "cluster", 50, 42, 200, 43):
        got = pd.Series(units[idx]).value_counts()
        assert (got == sizes[got.index]).all()
        assert len(idx) >= 100
        # Dropping the last unit drawn would go below n: order is draw order.
        assert len(idx) - got[units[idx[-1]]] < 100


def test_row_draws_are_exactly_n_without_replacement():
    w, units, _ = pool_for_draws()
    for idx, _ in cal.make_draws(w, units, 50, "row", 20, 42, 200, 43):
        assert len(set(idx.tolist())) == 50


def test_draws_are_deterministic():
    w, units, _ = pool_for_draws()
    a = cal.make_draws(w, units, 100, "cluster", 5, 42, 200, 43)
    b = cal.make_draws(w, units, 100, "cluster", 5, 42, 200, 43)
    assert all((x[0] == y[0]).all() and (x[1] == y[1]).all() for x, y in zip(a, b))


def test_paired_difference_sign_and_interval():
    s = cal.difference_summary(np.arange(1.0, 101.0), np.arange(1.0, 101.0) + 2)
    assert s["mean_diff"] == -2.0 and s["ci95"] == [-2.0, -2.0] and s["share_below_zero"] == 1.0


# ---------- synthetic end to end ----------


def synthetic_context(seed=6):
    rng = np.random.default_rng(seed)
    items = ["ever", "weekly", "carb"]
    n_test, n_pool, m = 2400, 632, 12
    units_test = np.repeat(np.arange(200), 12)
    units_pool = 1000 + np.repeat(np.arange(51), 13)[:n_pool]
    ages = rng.integers(1, 7, n_test)
    sexes = rng.integers(1, 3, n_test)
    ages_pool = rng.integers(1, 7, n_pool)
    sexes_pool = rng.integers(1, 3, n_pool)
    cells = (ages - 1) * 2 + (sexes - 1)
    cells_pool = (ages_pool - 1) * 2 + (sexes_pool - 1)
    w_test = rng.lognormal(0, 0.4, n_test)
    w_pool = rng.lognormal(0, 0.4, n_pool)
    base = {"ever": 1.5, "weekly": -0.5, "carb": -1.5}

    def eta(t, a):
        return base[t] - 0.45 * (a - 3.5)

    y_test = {t: (rng.uniform(size=n_test) < cal.expit(eta(t, ages))).astype(float) for t in items}
    y_pool = {t: (rng.uniform(size=n_pool) < cal.expit(eta(t, ages_pool))).astype(float) for t in items}
    panel_pos = np.sort(rng.choice(n_test, 1000, replace=False))
    outside = np.ones(n_test, dtype=bool)
    outside[panel_pos] = False
    ctx = {
        "items": items,
        "m": m,
        "cell_age": np.array([i // 2 for i in range(m)], dtype=float),
        "cell_sex": np.array([i % 2 for i in range(m)], dtype=float),
        "truth": {t: cal.cell_mean(y_test[t], w_test, cells, m) for t in items},
        "truth_outside_panel": {t: cal.cell_mean(y_test[t][outside], w_test[outside], cells[outside], m) for t in items},
        "constant": {t: float(np.average(y_test[t], weights=w_test)) for t in items},
        "noise_floor_pp": 4.04,
        "noise_floor_by_item_pp": {t: 4.0 for t in items},
        "panel": {
            "w": w_test[panel_pos],
            "cells": cells[panel_pos],
            "y": {t: y_test[t][panel_pos] for t in items},
            "units": units_test[panel_pos],
            "ages": ages[panel_pos],
            "sexes": sexes[panel_pos],
            "floor_p": {t: cal.expit(eta(t, ages[panel_pos])) for t in items},
            "positions_in_test": panel_pos,
        },
        "pool": {"w": w_pool, "cells": cells_pool, "y": y_pool, "units": units_pool},
        "test": {"w": w_test, "y": y_test, "units": units_test, "ages": ages, "sexes": sexes, "cells": cells},
    }
    good = {
        "test": {t: cal.expit(eta(t, ages[panel_pos]) + 1.2) for t in items},
        "calibration": {t: cal.expit(eta(t, ages_pool) + 1.2) for t in items},
    }
    noise = {
        "test": {t: rng.uniform(0.2, 0.8, 1000) for t in items},
        "calibration": {t: rng.uniform(0.2, 0.8, n_pool) for t in items},
    }
    answers = {"gpt-6.1-terra|C2": good, "gpt-6-luna|C2": noise}
    return ctx, answers


PLAN = {"n": [100, 200], "kinds": ["row", "cluster"], "repeats": 40, "seed": 42, "pi_draws": 500, "pi_seed": 43, "bootstrap": 60}


@pytest.fixture(scope="module")
def synthetic_result():
    ctx, answers = synthetic_context()
    stable = {t: np.tile(answers["gpt-6.1-terra|C2"]["test"][t][:100, None], (1, 4)) for t in ctx["items"]}
    return ctx, answers, main_score.score_main(ctx, answers, stable, PLAN)


def verdicts_of(result, model):
    return {v["item"]: v for v in result["trust_map"] if v["model"] == model}


def test_a_biased_but_right_panel_beats_e2_after_calibration(synthetic_result):
    _, _, r = synthetic_result
    e = r["calibration"]["200|row"]["estimators"]
    avg = e["gpt-6.1-terra|C2|E4"]["average"]
    assert avg["mean_diff"] < 0 and avg["ci95"][1] < 0
    assert e["gpt-6.1-terra|C2|E3"]["average"]["cell_mae"] > e["gpt-6.1-terra|C2|E4"]["average"]["cell_mae"]
    assert {v["verdict"] for v in verdicts_of(r, "gpt-6.1-terra").values()} == {verdict.CALIBRATED}


def test_a_noise_panel_gets_no_trust(synthetic_result):
    _, _, r = synthetic_result
    assert {v["verdict"] for v in verdicts_of(r, "gpt-6-luna").values()} == {verdict.REAL_ONLY}
    assert all(not v["level_trusted"] for v in verdicts_of(r, "gpt-6-luna").values())


def test_noise_panel_person_level_is_below_the_floor(synthetic_result):
    _, _, r = synthetic_result
    for t in ("ever", "weekly", "carb"):
        assert r["person_level"][t]["by_panel"]["gpt-6-luna|C2"]["auc"] < r["person_level"][t]["floor_auc"]


def test_r1_is_reported_but_not_read_by_the_rule(synthetic_result):
    _, _, r = synthetic_result
    e = r["calibration"]["200|row"]["estimators"]
    assert e["R1"]["average"]["mean_diff"] < 0
    assert "gpt-6.1-terra|C2|E4" in r["calibration"]["200|row"]["difference_to_R1"]
    # The stand-in panel holds no signal beyond age, so its win over R1 cannot be large.
    assert abs(r["calibration"]["200|row"]["difference_to_R1"]["gpt-6.1-terra|C2|E4"]["average"]["mean_diff"]) < 3.0


def test_holm_only_on_the_primary_row(synthetic_result):
    _, _, r = synthetic_result
    for t in ("ever", "weekly", "carb"):
        assert "holm_p" in r["person_level"][t]["by_panel"]["gpt-6.1-terra|C2"]
        assert "holm_p" not in r["person_level"][t]["by_panel"]["gpt-6-luna|C2"]


def test_stability_of_identical_answers_is_perfect(synthetic_result):
    _, _, r = synthetic_result
    for t in ("ever", "weekly", "carb"):
        assert r["stability"][t]["mean_abs_diff_pp"] == 0.0
        assert r["stability"][t]["pairs"] == 6
        assert r["stability"][t]["rank_correlation_mean"] == pytest.approx(1.0)


def test_markdown_renders_every_section(synthetic_result):
    ctx, _, r = synthetic_result
    text = main_score.to_markdown(r, ctx["items"])
    for section in ("## Primary", "## Calibration study", "## Person level", "## Stereotypes", "## Stability", "## Trust map"):
        assert section in text
    assert verdict.CALIBRATED in text and verdict.REAL_ONLY in text
    assert "never a market number" in text


def test_scoring_is_deterministic():
    ctx, answers = synthetic_context()
    small = {**PLAN, "repeats": 5, "n": [200], "bootstrap": 20, "pi_draws": 100}
    a = main_score.score_main(ctx, answers, None, small)
    b = main_score.score_main(ctx, answers, None, small)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_holm_by_hand():
    assert main_score.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert main_score.holm([0.5, 0.9, 0.9]) == pytest.approx([1.0, 1.0, 1.0])


def test_bootstrap_p_two_sided():
    assert main_score.bootstrap_p(np.ones(99)) == pytest.approx(2 / 100)
    assert main_score.bootstrap_p(np.array([-1.0, 1.0])) == 1.0


# ---------- runner ----------


@pytest.fixture()
def frozen():
    return main_run.load_config()


def runner(frozen, tmp_path, handler, repeat=0, ledger=None, gate_dir=None):
    cfg, template = frozen
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return main_run.MainRunner(cfg, template, cfg["models"]["main"]["id"], FAKE_KEY, client=client, log_path=tmp_path / "calls.jsonl", cache_dir=tmp_path / "cache", sleep=lambda s: None, ledger=ledger or panel_run.Ledger(cfg["limits"]["budget_usd"]), gate_cache_dir=gate_dir or tmp_path / "gate", repeat=repeat)


def persona_items(n=3, cond="C2"):
    return [{"condition": cond, "code": f"CODE{i:04d}", "persona": f"PERSONA-MARKER {i}"} for i in range(n)]


def write_gate_record(tmp_path, model, code, prompt):
    gate = tmp_path / "gate" / model
    gate.mkdir(parents=True, exist_ok=True)
    full = panel_run.prompt_hash(prompt)
    (gate / f"{code}_{full[:16]}.json").write_text(json.dumps({"code": code, "prompt_sha256": full, "answer": GOOD}), encoding="utf-8")


def test_main_config_matches_the_gate(frozen):
    cfg, template = frozen
    gate_cfg, _ = panel_run.load_config()
    assert cfg["prompt_sha256"].startswith("5173abd")
    assert cfg["request"] == gate_cfg["request"]
    assert cfg["request"]["reasoning_effort"] == "medium"
    assert panel_run.template_sha256(template) == cfg["prompt_sha256"]
    assert cfg["limits"]["budget_usd"] == 6.0


def test_config_differing_from_the_gate_is_refused(monkeypatch, tmp_path):
    cfg = json.loads(main_run.MAIN_RUN.read_text(encoding="utf-8"))
    cfg["request"]["reasoning_effort"] = "high"
    changed = tmp_path / "main_run.json"
    changed.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(main_run, "MAIN_RUN", changed)
    with pytest.raises(RuntimeError, match="request"):
        main_run.load_config()


def test_gate_answer_is_reused_without_a_call_when_code_and_prompt_match(frozen, tmp_path):
    cfg, template = frozen
    calls = []
    items = persona_items(3)
    write_gate_record(tmp_path, cfg["models"]["main"]["id"], items[0]["code"], panel_run.render(template, items[0]["persona"]))

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=body())

    r = runner(frozen, tmp_path, handler)
    summary = r.run(items)
    assert summary["counts"] == {"called": 2, "cached": 1, "failed": 0, "stopped": 0}
    assert len(calls) == 2
    assert all(items[0]["persona"] not in c["input"][0]["content"][0]["text"] for c in calls)


def test_gate_answer_is_not_reused_for_a_different_prompt(frozen, tmp_path):
    cfg, template = frozen
    item = persona_items(1)[0]
    # The file name matches, the stored hash does not.
    prompt = panel_run.render(template, item["persona"])
    gate = tmp_path / "gate" / cfg["models"]["main"]["id"]
    gate.mkdir(parents=True)
    (gate / f"{item['code']}_{panel_run.prompt_hash(prompt)[:16]}.json").write_text(json.dumps({"code": item["code"], "prompt_sha256": "other", "answer": GOOD}), encoding="utf-8")
    r = runner(frozen, tmp_path, lambda request: httpx.Response(200, json=body()))
    assert r.run([item])["counts"]["called"] == 1


def test_repeat_is_in_the_cache_key_only_and_the_prompt_is_identical(frozen, tmp_path):
    bodies = []

    def handler(request):
        bodies.append(request.content)
        return httpx.Response(200, json=body())

    item = persona_items(1)
    for repeat in (0, 1, 2):
        runner(frozen, tmp_path, handler, repeat=repeat).run(item)
    assert len(bodies) == 3 and len(set(bodies)) == 1
    files = sorted(p.name for p in (tmp_path / "cache" / frozen[0]["models"]["main"]["id"]).glob("*.json"))
    assert len(files) == 3
    assert sum("_r1" in f for f in files) == 1 and sum("_r2" in f for f in files) == 1
    # A second pass over a cached repeat calls nothing.
    assert runner(frozen, tmp_path, handler, repeat=1).run(item)["counts"]["cached"] == 1


def test_repeat_calls_are_marked_in_the_log(frozen, tmp_path):
    runner(frozen, tmp_path, lambda request: httpx.Response(200, json=body()), repeat=2).run(persona_items(1))
    rows = [json.loads(x) for x in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["repeat"] == 2


def test_budget_stop_applies_to_this_stage_alone(frozen, tmp_path):
    r = runner(frozen, tmp_path, lambda request: httpx.Response(200, json=body()), ledger=panel_run.Ledger(0.001))
    summary = r.run(persona_items(3))
    assert summary["stop_reason"] == "budget"
    assert summary["counts"]["called"] == 0


def test_empty_balance_stops_at_once(frozen, tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, json={"error": {"type": "insufficient_quota", "code": "credit_balance_exhausted"}})

    r = runner(frozen, tmp_path, handler)
    r.concurrency = 1
    summary = r.run(persona_items(5))
    assert summary["stop_reason"] == "insufficient_quota"
    assert len(calls) == 1


def key_frame(n_codes=6):
    rows = []
    for cond in ("C1", "C2"):
        for i in range(n_codes):
            rows.append({"split": "test", "condition": cond, "code": f"{cond}CODE{i:03d}", "row_index": i, "analysis_weight": 1.0, "gate_code": int(i < 2), "stability": int(cond == "C2" and i < 2)})
    return pd.DataFrame(rows)


def test_run_all_ledger_ignores_the_gate_log_and_follows_the_frozen_order(frozen, tmp_path):
    cfg, template = frozen
    cfg = {**cfg, "stability": {**cfg["stability"], "extra_repeats": 2}}
    key = key_frame()
    personas = {c: f"PERSONA-MARKER {c}" for c in key["code"]}
    seen = []

    def handler(request):
        seen.append(json.loads(request.content)["model"])
        return httpx.Response(200, json=body())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    log = tmp_path / "main_calls.jsonl"
    summaries, complete = main_run.run_all(cfg, template, key, personas, FAKE_KEY, client=client, sleep=lambda s: None, log_path=log, cache_dir=tmp_path / "cache", gate_cache_dir=tmp_path / "gate", progress=None)
    assert complete
    assert [s["stage"] for s in summaries] == ["gpt-6.1-terra|C2", "gpt-6.1-terra|C1", "gpt-6-luna|C2", "gpt-6-luna|C1", "stability_r1", "stability_r2"]
    assert seen[0] == "gpt-6.1-terra" and "gpt-6-luna" in seen
    assert summaries[0]["gate_spent_usd"] < 0.1
    stats = main_run.summarize_log(key, log)
    assert stats["models"]["gpt-6.1-terra"]["stability"]["billed"] == 4
    assert stats["stage_total_usd"] == pytest.approx(panel_run.spent_from_log(log), abs=1e-5)


def test_run_all_stops_later_stages_after_an_empty_balance(frozen, tmp_path):
    cfg, template = frozen
    key = key_frame()
    personas = {c: f"PERSONA-MARKER {c}" for c in key["code"]}
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429, json={"error": {"type": "insufficient_quota"}})))
    summaries, complete = main_run.run_all(cfg, template, key, personas, FAKE_KEY, client=client, sleep=lambda s: None, log_path=tmp_path / "c.jsonl", cache_dir=tmp_path / "cache", gate_cache_dir=tmp_path / "gate", progress=None)
    assert not complete
    assert len(summaries) == 1


def test_partial_answers_are_not_scored(frozen, tmp_path):
    cfg, template = frozen
    key = key_frame()
    personas = {c: f"PERSONA-MARKER {c}" for c in key["code"]}
    assert main_run.load_answer_arrays("gpt-6.1-terra", "C2", key, personas, template, tmp_path / "cache", tmp_path / "gate") is None


def test_answers_prefer_this_stage_and_read_the_gate_when_identical(frozen, tmp_path):
    cfg, template = frozen
    model = cfg["models"]["main"]["id"]
    key = key_frame(2)
    key["split"] = ["test", "calibration"] * 2
    personas = {c: f"PERSONA-MARKER {c}" for c in key["code"]}
    for code in key.loc[key.condition == "C2", "code"]:
        write_gate_record(tmp_path, model, code, panel_run.render(template, personas[code]))
    got = main_run.load_answer_arrays(model, "C2", key, personas, template, tmp_path / "cache", tmp_path / "gate")
    assert got["test"]["ever"].tolist() == [GOOD["p_zero_ever"]]
    assert got["calibration"]["carb"].tolist() == [GOOD["p_carb_top1"]]


def test_frozen_change_is_refused(monkeypatch, tmp_path):
    if not main_run.KEY.exists() or not main_run.FROZEN.exists():
        pytest.skip("main key or frozen manifest not present")
    doc = json.loads(main_run.FROZEN.read_text(encoding="utf-8"))
    doc["files"]["src/lotte_audit/verdict.py"] = "0" * 64
    changed = tmp_path / "frozen_main.json"
    changed.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(main_run, "FROZEN", changed)
    with pytest.raises(RuntimeError, match="verdict"):
        main_run.check_frozen(main_run.load_key())


def test_extended_panel_keeps_the_gate_rows_and_stays_in_the_test_rows():
    rng = np.random.default_rng(7)
    positions = np.arange(100, 2100)
    w = rng.lognormal(0, 0.6, len(positions))
    gate = np.sort(rng.choice(positions, 300, replace=False))
    a = main_run.extend_panel(positions, w, gate, 1000, 42)
    assert len(a) == 1000 and len(set(a.tolist())) == 1000
    assert set(gate.tolist()) <= set(a.tolist())
    assert set(a.tolist()) <= set(positions.tolist())
    assert (a == main_run.extend_panel(positions, w, gate, 1000, 42)).all()


def test_extension_inclusion_is_consistent_with_the_draw():
    rng = np.random.default_rng(8)
    w = rng.lognormal(0, 0.6, 500)
    pi = main_run.extension_inclusion(w, 50, 200, 3000, 43)
    assert abs(pi.sum() - 200) < 1.0
    assert pi[np.argmax(w)] > pi[np.argmin(w)]
    y = (rng.uniform(size=500) < 0.2).astype(float)
    # Horvitz-Thompson total of weights recovers the population total on average.
    totals = []
    draw = np.random.default_rng(9)
    for _ in range(300):
        first = draw.choice(500, 50, replace=False, p=w / w.sum())
        rest = np.setdiff1d(np.arange(500), first)
        second = draw.choice(rest, 150, replace=False, p=w[rest] / w[rest].sum())
        s = np.concatenate([first, second])
        totals.append(np.sum((w / pi)[s] * y[s]))
    assert abs(np.mean(totals) - np.sum(w * y)) / np.sum(w * y) < 0.03


# ---------- real data, synthetic answers ----------


@pytest.fixture(scope="module")
def main_key():
    if not main_run.KEY.exists():
        pytest.skip("main key not present; run src/main_run.py prepare")
    return main_run.load_key()


def test_real_panel_shape_and_no_crossing(real, main_key):
    df = real["df"]
    mk = splits.masks(splits.load_manifest(df))
    units = df[paths.PSU].to_numpy()
    t = main_key.loc[(main_key.split == "test") & (main_key.condition == "C2"), "row_index"].to_numpy()
    c = main_key.loc[(main_key.split == "calibration") & (main_key.condition == "C2"), "row_index"].to_numpy()
    assert len(t) == 1000 and len(c) == 632
    assert mk["test"][t].all() and mk["calibration"][c].all()
    assert c.tolist() == np.flatnonzero(mk["calibration"]).tolist()
    assert not set(units[t]) & set(units[c])
    assert int(main_key.stability.sum()) == 100
    assert main_key["code"].is_unique


def test_real_panel_extends_the_gate_with_the_same_codes(key, main_key):
    for cond in ("C1", "C2"):
        gate = key.loc[key.condition == cond].set_index("row_index")["code"]
        got = main_key.loc[(main_key.condition == cond) & (main_key.split == "test")].set_index("row_index")["code"]
        assert (got.loc[gate.index] == gate).all()
        assert int(main_key.loc[main_key.condition == cond, "gate_code"].sum()) == 300


def test_real_repaired_weights_recover_the_test_split_share(real, main_key):
    df = real["df"]
    mk = splits.masks(splits.load_manifest(df))
    w = df[paths.WEIGHT].to_numpy()
    cells = data.cell_id(df)
    sub = main_key.loc[(main_key.split == "test") & (main_key.condition == "C1")]
    rows = sub["row_index"].to_numpy()
    aw = sub["analysis_weight"].to_numpy()
    assert (aw > 0).all()
    # Age by sex mix of the repaired panel is close to the mix of the test split.
    for c in np.unique(cells[mk["test"]]):
        panel_share = aw[cells[rows] == c].sum() / aw.sum()
        test_share = w[mk["test"] & (cells == c)].sum() / w[mk["test"]].sum()
        assert abs(panel_share - test_share) < 0.03


def test_real_path_runs_on_synthetic_answers(real, main_key, baseline):
    df = real["df"]
    ctx = main_score.build_context(df, main_key, baseline)
    for t in paths.TARGETS:
        assert cal.cell_mae(np.full(ctx["m"], ctx["constant"][t]), ctx["truth"][t]) == pytest.approx(baseline["items"][t]["constant_cell_mae"], abs=0.005)
    assert ctx["m"] == 12
    assert ctx["cell_age"].tolist() == sorted(ctx["cell_age"].tolist())
    assert set(ctx["cell_age"].tolist()) == {0.0, 1.0, 2.0, 3.0, 4.0, 5.0} and set(ctx["cell_sex"].tolist()) == {0.0, 1.0}
    rng = np.random.default_rng(10)
    answers = {
        "gpt-6.1-terra|C2": {
            "test": {t: rng.uniform(0.01, 0.9, 1000) for t in paths.TARGETS},
            "calibration": {t: rng.uniform(0.01, 0.9, 632) for t in paths.TARGETS},
        }
    }
    plan = {"n": [100, 200, 400], "kinds": ["row", "cluster"], "repeats": 5, "seed": 42, "pi_draws": 200, "pi_seed": 43, "bootstrap": 20}
    r = main_score.score_main(ctx, answers, None, plan)
    assert r["calibration"]["400|cluster"]["realised_n_mean"] >= 400
    assert r["calibration"]["200|row"]["realised_n_min"] == 200
    assert r["calibration"]["200|row"]["estimators"]["E0"]["carb"]["cell_mae"] == pytest.approx(baseline["items"]["carb"]["constant_cell_mae"], abs=0.005)
    text = main_score.to_markdown(r, ctx["items"])
    assert "## Trust map" in text
    dumped = json.dumps(r)
    for code in main_key["code"].head(200):
        assert code not in dumped


def test_committed_main_results_hold_no_codes(main_key):
    folder = paths.RESULTS / "main"
    if not folder.exists():
        pytest.skip("no main results yet")
    text = "".join(p.read_text(encoding="utf-8") for p in folder.glob("*"))
    assert not [c for c in main_key["code"] if c in text]
