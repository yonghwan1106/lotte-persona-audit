"""Harness tests with synthetic answers on the real gate panel. No LLM calls."""
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from conftest import answers_from
from lotte_audit import baselines, batches, data, leakguard, metrics, paths, persona, score, splits

ROOT = Path(__file__).resolve().parents[1]
DRINK_LABEL = "\ud3c9\uc18c \ucf5c\ub77c \uc12d\ucde8 \ube48\ub3c4"  # planted drink item label
BENIGN_LABEL = "\ud3c9\uc18c \uc0b0\ucc45 \ube48\ub3c4"  # planted benign-looking label
ZERO_SENTENCE = "\uc81c\ub85c \ucf5c\ub77c\ub97c \uc990\uaca8 \ub9c8\uc2e0\ub2e4."  # planted persona sentence


def fake_meta(labels, value_labels=None):
    return SimpleNamespace(
        column_names_to_labels=labels,
        variable_value_labels=value_labels or {},
        column_names=list(labels),
    )


# ---------- metric units ----------


def test_weighted_auc_hand_case():
    y = np.array([0, 0, 1, 1])
    assert metrics.weighted_auc(y, np.array([0.1, 0.2, 0.3, 0.4]), np.ones(4)) == 1.0
    assert metrics.weighted_auc(y, np.array([0.5, 0.5, 0.5, 0.5]), np.ones(4)) == 0.5
    # A heavy misordered pair moves the value: 3 of 4 pairs are right, weight 9 on the wrong pair's negative.
    w = np.array([1.0, 9.0, 1.0, 1.0])
    p = np.array([0.1, 0.35, 0.3, 0.4])
    assert metrics.weighted_auc(y, p, w) == pytest.approx((1 + 1 + 0 + 9) / 20)


def test_cell_mae_and_underdispersion_hand_case():
    truth = {1: 0.2, 2: 0.6}
    est = {1: 0.3, 2: 0.5}
    assert metrics.cell_mae(est, truth) == pytest.approx(10.0)
    assert metrics.underdispersion(est, truth) == pytest.approx(0.5)
    assert metrics.constant_mae(0.4, truth) == pytest.approx(20.0)


def test_age_slope_and_gender_gap_hand_case():
    ages = np.array([4, 4, 5, 5, 6, 6])
    vals = np.array([0.8, 0.8, 0.6, 0.6, 0.4, 0.4])
    assert metrics.age_slope(vals, np.ones(6), ages) == pytest.approx(-20.0)
    assert metrics.gender_gap(np.array([0.1, 0.3]), np.ones(2), np.array([1, 2])) == pytest.approx(20.0)


def test_within_group_auc_removes_group_effect():
    # Across groups the score looks perfect; inside each group it is a coin flip.
    y = np.array([0, 1, 0, 1])
    p = np.array([0.1, 0.1, 0.9, 0.9])
    g = np.array([1, 1, 2, 2])
    within, used = metrics.within_group_auc(y, p, g, np.ones(4))
    assert used == 2 and within == pytest.approx(0.5)


def test_worth_n_conversion():
    curve = {100: 10.0, 250: 8.0, 500: 6.0, 1000: 4.0}
    assert metrics.worth_n(12.0, 11.0, curve)["label"] == "no value"
    assert metrics.worth_n(11.0, 11.0, curve)["label"] == "no value"
    assert metrics.worth_n(10.5, 11.0, curve)["label"] == "<100"
    assert metrics.worth_n(3.0, 11.0, curve)["label"] == ">=1000"
    assert metrics.worth_n(8.0, 11.0, curve)["n"] == 250
    assert 250 < metrics.worth_n(7.0, 11.0, curve)["n"] < 500


# ---------- answer validation ----------


def test_missing_code_raises(key):
    a = answers_from(key, lambda r, t: np.full(len(r), 0.5))
    with pytest.raises(score.AnswerValidationError, match="missing codes"):
        score.validate(a.iloc[1:], key)


def test_unknown_code_raises(key):
    a = answers_from(key, lambda r, t: np.full(len(r), 0.5))
    extra = a.iloc[[0]].copy()
    extra["code"] = "ZZZZZZZZ"
    with pytest.raises(score.AnswerValidationError, match="unknown codes"):
        score.validate(pd.concat([a, extra]), key)


def test_duplicate_code_raises(key):
    a = answers_from(key, lambda r, t: np.full(len(r), 0.5))
    with pytest.raises(score.AnswerValidationError, match="duplicate"):
        score.validate(pd.concat([a, a.iloc[[0]]]), key)


@pytest.mark.parametrize("bad", [1.2, -0.1, float("nan"), "x"])
def test_out_of_range_raises(key, bad):
    a = answers_from(key, lambda r, t: np.full(len(r), 0.5))
    a["p_zero_ever"] = a["p_zero_ever"].astype(object)
    a.loc[a.index[3], "p_zero_ever"] = bad
    with pytest.raises(score.AnswerValidationError):
        score.validate(a, key)


def test_read_answers_rejects_missing_column(tmp_path):
    pd.DataFrame({"code": ["A"], "p_zero_ever": [0.1]}).to_csv(tmp_path / "x.csv", index=False)
    with pytest.raises(score.AnswerValidationError, match="missing columns"):
        score.read_answers(tmp_path)


def test_frozen_config_guard(monkeypatch):
    real_hashes = score.config_hashes()
    tampered = dict(real_hashes)
    tampered["prereg.json"] = "0" * 64
    monkeypatch.setattr(score, "config_hashes", lambda: tampered)
    with pytest.raises(RuntimeError, match="prereg.json"):
        score.check_frozen()


# ---------- synthetic answers end to end ----------


def test_perfect_oracle_auc_is_one(real, key, baseline, tmp_path):
    y = real["targets"]
    a = answers_from(key, lambda r, t: y[t].to_numpy()[r].astype(float))
    r = score.score(a, key, real["df"], baseline)
    for cond in ("C1", "C2"):
        for t in paths.TARGETS:
            assert r["conditions"][cond]["items"][t]["auc"] == pytest.approx(1.0)
            assert r["conditions"][cond]["items"][t]["cell_mae"] == r["same_300_real_answers_cell_mae"][t]
    assert r["switch_rule"]["decision"] == "NO SWITCH"
    assert r["conditions"]["C0"]["items"]["ever"]["auc"] is None
    score.write(r, tmp_path, "oracle")
    assert json.loads((tmp_path / "oracle.json").read_text(encoding="utf-8"))["switch_rule"]["decision"] == "NO SWITCH"
    assert "NO SWITCH" in (tmp_path / "oracle.md").read_text(encoding="utf-8")


def test_constant_auc_half_and_no_value_and_switch(real, key, baseline):
    # A constant equal to the train mean ties the constant baseline, so it must print no value.
    train_means = {t: baseline["items"][t]["national_train_pct"] / 100 for t in paths.TARGETS}
    a = answers_from(key, lambda r, t: np.full(len(r), train_means[t]))
    for t in paths.TARGETS:
        a.loc[a.code.isin(key.loc[key.condition == "C0", "code"]), paths.ANSWER_COL[t]] = train_means[t]
    r = score.score(a, key, real["df"], baseline)
    for cond in ("C1", "C2"):
        for t in paths.TARGETS:
            item = r["conditions"][cond]["items"][t]
            assert item["auc"] == pytest.approx(0.5)
            assert item["worth_n"]["label"] == "no value"
            assert item["pattern"]["reproduces"] is False
    assert r["conditions"]["C0"]["items"]["ever"]["cell_mae"] == pytest.approx(baseline["items"]["ever"]["constant_cell_mae"], abs=0.02)
    assert r["switch_rule"]["decision"] == "SWITCH"


def test_shuffled_auc_about_half(real, key):
    sub = key.loc[key.condition == "C1"]
    rows = sub["row_index"].to_numpy()
    w = sub["panel_weight"].to_numpy()
    rng = np.random.default_rng(paths.SEED)
    for t in paths.TARGETS:
        y = real["targets"][t].to_numpy()[rows]
        vals = [metrics.weighted_auc(y, rng.permutation(y).astype(float), w) for _ in range(200)]
        assert abs(float(np.mean(vals)) - 0.5) < 0.02


def test_shuffled_answers_end_to_end_about_half(real, key, baseline):
    rng = np.random.default_rng(paths.SEED)
    y = real["targets"]
    # Same answers per respondent under a random reassignment, with no age or sex structure left.
    a = answers_from(key, lambda r, t: rng.permutation(y[t].to_numpy()[r].astype(float)))
    r = score.score(a, key, real["df"], baseline)
    aucs = [r["conditions"][c]["items"][t]["auc"] for c in ("C1", "C2") for t in paths.TARGETS]
    assert abs(float(np.mean(aucs)) - 0.5) < 0.12


def test_floor_answers_reproduce_floor(real, key, baseline, manifest):
    df, targets = real["df"], real["targets"]
    models = baselines.fit_reference_models(df, targets, splits.masks(manifest)["train"])

    def floor(rows, t):
        (m, cols), names = models[t]["floor"]
        return baselines.predict_logistic(m, cols, df.iloc[rows], names)

    a = answers_from(key, floor)
    r = score.score(a, key, df, baseline)
    for cond in ("C1", "C2"):
        for t in paths.TARGETS:
            item = r["conditions"][cond]["items"][t]
            assert item["auc"] == pytest.approx(item["floor_auc_same_respondents"], abs=1e-9)
    assert r["switch_rule"]["all_auc_at_or_below_floor"] is True
    # The floor carries the real age pattern, so the rule must not fire on it.
    assert r["switch_rule"]["any_reproducing_pattern"] is True
    assert r["switch_rule"]["decision"] == "NO SWITCH"


def test_baseline_floor_matches_recomputation(real, baseline, manifest):
    df, targets = real["df"], real["targets"]
    mk = splits.masks(manifest)
    tr, te = mk["train"], mk["test"]
    w = df[paths.WEIGHT].to_numpy()
    for t in paths.TARGETS:
        m, c = baselines.fit_logistic(df.loc[tr], targets[t].to_numpy()[tr], w[tr], baselines.floor_columns())
        p = baselines.predict_logistic(m, c, df.loc[te], baselines.floor_columns())
        assert round(metrics.weighted_auc(targets[t].to_numpy()[te], p, w[te]), 3) == baseline["items"][t]["floor_age_sex"]["auc"]


def test_switch_rule_logic_needs_all_items():
    prereg = json.loads((paths.CONFIG / "prereg.json").read_text(encoding="utf-8"))

    def item(auc, floor, repro=False):
        return {"auc": auc, "floor_auc_same_respondents": floor, "pattern": {"reproduces": repro}}

    def build(fn):
        return {"conditions": {c: {"items": {t: fn(c, t) for t in paths.TARGETS}} for c in ("C1", "C2")}}

    assert score.apply_switch_rule(build(lambda c, t: item(0.6, 0.7)), prereg)["decision"] == "SWITCH"
    assert score.apply_switch_rule(build(lambda c, t: item(0.7, 0.7)), prereg)["decision"] == "SWITCH"
    one_above = lambda c, t: item(0.71 if (c == "C2" and t == "carb") else 0.6, 0.7)
    assert score.apply_switch_rule(build(one_above), prereg)["decision"] == "NO SWITCH"
    one_pattern = lambda c, t: item(0.6, 0.7, c == "C1" and t == "ever")
    assert score.apply_switch_rule(build(one_pattern), prereg)["decision"] == "NO SWITCH"


# ---------- leak guard ----------


def test_leak_guard_blocks_planted_drink_item():
    meta = fake_meta({"X99": DRINK_LABEL})
    with pytest.raises(leakguard.LeakError, match="label regex: drinks"):
        leakguard.check_candidate("X99", meta)


def test_leak_guard_blocks_planted_value_label():
    meta = fake_meta({"X98": BENIGN_LABEL}, {"X98": {1.0: DRINK_LABEL}})
    with pytest.raises(leakguard.LeakError, match="value label regex"):
        leakguard.check_candidate("X98", meta)


def test_leak_guard_blocks_target_family_design_and_household():
    meta = fake_meta({"A19_2": BENIGN_LABEL, "A15_3": BENIGN_LABEL, "vuid": BENIGN_LABEL, "J_F8_1": BENIGN_LABEL})
    for var, msg in [("A19_2", "target family"), ("A15_3", "target family"), ("vuid", "survey design"), ("J_F8_1", "household")]:
        with pytest.raises(leakguard.LeakError, match=msg):
            leakguard.check_candidate(var, meta)


def test_screen_blocks_benign_label_with_high_train_auc():
    rng = np.random.default_rng(1)
    n = 2000
    y = rng.integers(0, 2, n)
    noisy = np.where(rng.random(n) < 0.8, y, 1 - y).astype(float) + 1.0
    df = pd.DataFrame({"X97": noisy, "X96": rng.integers(1, 6, n).astype(float), "SQ1": rng.integers(1, 3, n).astype(float), paths.WEIGHT: 1.0})
    # SQ1 is exempt even if it were predictive, so make it predictive too.
    df["SQ1"] = noisy
    targets = pd.DataFrame({"ever": y, "weekly": y, "carb": y})
    meta = fake_meta({"X97": BENIGN_LABEL, "X96": BENIGN_LABEL, "SQ1": BENIGN_LABEL, paths.WEIGHT: "w"})
    s = leakguard.screen(df, meta, targets)
    assert bool(s.loc[s["var"] == "X97", "over_threshold"].iloc[0]) is True
    assert bool(s.loc[s["var"] == "X96", "over_threshold"].iloc[0]) is False
    kept, rejected = leakguard.build_allowlist([{"var": "X97"}, {"var": "X96"}, {"var": "SQ1"}], meta, s)
    assert [i["var"] for i in kept] == ["X96", "SQ1"]
    assert rejected[0]["var"] == "X97"


def test_persona_scan_blocks_planted_sentence_and_ids():
    with pytest.raises(leakguard.LeakError):
        leakguard.scan_text(ZERO_SENTENCE)
    with pytest.raises(leakguard.LeakError, match="identifier"):
        leakguard.scan_text("abc 1A001101 def", ["1A001101"])


def test_planted_item_cannot_render(real):
    planted = {"var": "A4", "answers": {"1": ZERO_SENTENCE, "2": ZERO_SENTENCE}}
    row = real["df"].iloc[0]
    with pytest.raises(leakguard.LeakError):
        persona.render_c2(row, [planted])


def test_final_allowlist_is_clean_and_screened(real):
    final = persona.load_final_allowlist()
    screen = pd.read_csv(paths.RESULTS / "leakage_screen_train.csv")
    assert final["n_kept"] == len(final["items"]) > 0
    for item in final["items"]:
        leakguard.check_candidate(item["var"], real["meta"], screen)


# ---------- splits, panel and files ----------


def test_every_test_row_renders_and_passes_the_guard(real, manifest):
    """Later runs may use more of the test split, so every test row must render, not only the 300."""
    df = real["df"]
    allowlist = persona.load_final_allowlist()["items"]
    templates = persona.load_templates()
    for pos in np.flatnonzero(splits.masks(manifest)["test"]):
        persona.render_c2(df.iloc[pos], allowlist, templates)


def test_cli_scores_answer_files(real, key, tmp_path):
    answers = tmp_path / "answers"
    out = tmp_path / "out"
    answers.mkdir()
    y = real["targets"]
    a = answers_from(key, lambda r, t: y[t].to_numpy()[r].astype(float))
    for cond in ("C0", "C1", "C2"):
        a.loc[a.code.isin(key.loc[key.condition == cond, "code"])].to_csv(answers / f"{cond}.csv", index=False)
    done = subprocess.run(
        [sys.executable, str(ROOT / "audit.py"), "score", "--answers", str(answers), "--out", str(out)],
        capture_output=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().splitlines()[-1] == "NO SWITCH"
    assert (out / "gate_score.json").exists() and (out / "gate_score.md").exists()
    # A missing code must stop the command rather than score a partial panel.
    (answers / "C2.csv").write_text("code,p_zero_ever,p_zero_weekly,p_carb_top1" + chr(10), encoding="utf-8")
    bad = subprocess.run([sys.executable, str(ROOT / "audit.py"), "score", "--answers", str(answers), "--out", str(out)], capture_output=True, encoding="utf-8")
    assert bad.returncode != 0 and "missing codes" in bad.stderr


def test_splits_disjoint_and_cover_all_rows(real, manifest):
    df = real["df"]
    mk = splits.masks(manifest)
    assert sum(int(v.sum()) for v in mk.values()) == len(df)
    names = list(mk)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert not (mk[a] & mk[b]).any()
            assert not set(df[paths.PSU][mk[a]]) & set(df[paths.PSU][mk[b]])
            assert not set(df[paths.HOUSEHOLD][mk[a]]) & set(df[paths.HOUSEHOLD][mk[b]])


def test_split_is_deterministic(real, manifest):
    again = splits.assign_units(real["df"])
    assert (again == manifest.split.to_numpy()).all()


def test_panel_only_from_test_and_redraw_is_identical(real, key, manifest):
    test = splits.masks(manifest)["test"]
    c1 = key.loc[key.condition == "C1"]
    c2 = key.loc[key.condition == "C2"]
    assert len(c1) == len(c2) == 300
    assert test[c1["row_index"].to_numpy()].all()
    assert set(c1.row_index) == set(c2.row_index)
    positions = np.flatnonzero(test)
    redraw = batches.draw_panel(positions, real["df"][paths.WEIGHT].to_numpy()[test])
    assert set(redraw.tolist()) == set(c1.row_index)
    assert (key.loc[key.condition == "C0", "row_index"] == -1).all()


def test_codes_are_opaque_and_unique(key):
    assert key["code"].is_unique
    assert key["code"].str.fullmatch(r"[A-Z2-9]{8}").all()
    for cond in ("C1", "C2"):
        sub = key.loc[key.condition == cond]
        rho = pd.Series(sub["code"].rank().to_numpy()).corr(pd.Series(sub["row_index"].rank().to_numpy()))
        assert abs(rho) < 0.2
    merged = key.loc[key.condition == "C1"].merge(key.loc[key.condition == "C2"], on="row_index")
    assert (merged.code_x != merged.code_y).all()


def _blocks(path):
    text = path.read_text(encoding="utf-8")
    body = text.split("----\n", 1)[1]
    return re.findall(r"code: ([A-Z2-9]{8})\n(.*?)(?=\n\ncode: |\n*$)", body, flags=re.S)


def test_batches_have_the_right_shape_and_pass_the_guard(real, key):
    files = {p.name: p for p in paths.GATE_INPUTS.glob("*_batch*.txt")}
    assert sorted(files) == ["C0_batch01.txt", "C1_batch01.txt", "C1_batch02.txt", "C1_batch03.txt", "C2_batch01.txt", "C2_batch02.txt", "C2_batch03.txt"]
    seen = {"C0": set(), "C1": set(), "C2": set()}
    ids = set(real["df"][paths.HOUSEHOLD].astype(str)) | set(real["df"]["id"].astype(str))
    for name, path in files.items():
        cond = name[:2]
        blocks = _blocks(path)
        assert len(blocks) == 100, name
        for code, text in blocks:
            leakguard.scan_text(text)
            assert not any(tok in ids for tok in re.findall(r"[0-9A-Za-z]{6,}", text)), code
            seen[cond].add(code)
        if cond == "C0":
            assert len({t for _, t in blocks}) == 1
        else:
            order = key.set_index("code").loc[[c for c, _ in blocks], "row_index"].to_numpy()
            assert not (np.diff(order) > 0).all()
    for cond in seen:
        assert seen[cond] == set(key.loc[key.condition == cond, "code"])


def test_panel_weights_correct_for_the_weighted_draw(real, manifest):
    """Re-weighting by psfwt over the inclusion probability recovers the test mean; psfwt alone does not."""
    df, targets = real["df"], real["targets"]
    test = splits.masks(manifest)["test"]
    positions = np.flatnonzero(test)
    w = df[paths.WEIGHT].to_numpy()[test]
    y = targets["ever"].to_numpy()[test]
    truth = np.average(y, weights=w)
    pi = batches.inclusion_probabilities(positions, w, draws=1500)
    corrected, doubled = [], []
    index = {p: i for i, p in enumerate(positions.tolist())}
    for s in range(300):
        rows = np.array([index[p] for p in batches.draw_panel(positions, w, seed=1000 + s).tolist()])
        corrected.append(np.average(y[rows], weights=w[rows] / pi[rows]))
        doubled.append(np.average(y[rows], weights=w[rows]))
    assert abs(np.mean(corrected) - truth) < 0.01
    assert abs(np.mean(corrected) - truth) < abs(np.mean(doubled) - truth)


# ---------- repo hygiene ----------


def _git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")


def test_row_level_files_are_ignored():
    for rel in ["data/raw/a2025.sav", "runs/gate/key.csv", "runs/gate/inputs/C1_batch01.txt", "runs/gate/answers/C1.csv"]:
        assert _git("check-ignore", rel).returncode == 0, rel


def test_no_row_level_file_is_tracked():
    tracked = _git("ls-files").stdout.split()
    assert not [f for f in tracked if f.startswith(("data/", "runs/")) or f.endswith((".sav", ".zip"))]


def test_python_sources_are_ascii():
    files = [ROOT / "audit.py", *ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py")]
    for f in files:
        f.read_bytes().decode("ascii")


def test_no_llm_client_is_used():
    """Only the gate runner, src/panel_run.py, talks to an API. The scoring harness must stay offline."""
    pattern = re.compile(r"^\s*(import|from)\s+(openai|anthropic|httpx|requests|litellm)\b", re.M)
    for f in [ROOT / "audit.py", *ROOT.glob("src/**/*.py")]:
        if f.name == "panel_run.py":
            continue
        assert not pattern.search(f.read_text(encoding="utf-8")), f.name
