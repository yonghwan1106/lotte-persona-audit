"""Stage 4 measures on synthetic numbers. No file of answers, no API."""
import json

import numpy as np
import pytest
from scipy import stats

from lotte_audit import calibration as cal
from lotte_audit import duel, paths, stage4

CELLS = 12


def synthetic_ctx(seed=3, n_pool=632, n_panel=1000, n_test=2300):
    rng = np.random.default_rng(seed)
    base = rng.uniform(0.15, 0.75, CELLS)
    cell_age = np.repeat(np.arange(6.0), 2)
    cell_sex = np.tile([0.0, 1.0], 6)

    def block(n):
        cells = rng.integers(0, CELLS, n)
        w = rng.uniform(0.5, 2.0, n)
        y = {t: (rng.uniform(size=n) < np.clip(base[cells] * f, 0, 1)).astype(float) for t, f in (("ever", 1.0), ("weekly", 0.5), ("carb", 0.3))}
        return cells, w, y

    pc, pw, py = block(n_pool)
    tc, tw, ty = block(n_test)
    units = rng.integers(0, 200, n_test)
    pos = np.sort(rng.choice(n_test, n_panel, replace=False))
    keep = np.ones(n_test, dtype=bool)
    keep[pos] = False
    return {
        "items": ["ever", "weekly", "carb"],
        "m": CELLS,
        "cell_age": cell_age,
        "cell_sex": cell_sex,
        "truth": {t: cal.cell_mean(ty[t], tw, tc, CELLS) for t in ty},
        "truth_outside_panel": {t: cal.cell_mean(ty[t][keep], tw[keep], tc[keep], CELLS) for t in ty},
        "panel": {"w": tw[pos], "cells": tc[pos], "y": {t: ty[t][pos] for t in ty}, "units": units[pos], "positions_in_test": pos},
        "pool": {"w": pw, "cells": pc, "y": py, "units": rng.integers(0, 51, n_pool)},
        "test": {"w": tw, "cells": tc, "units": units, "y": ty},
    }


def answer_sets(ctx, signal, seed=11, noise=0.3):
    """A panel that knows the real answer with the given logit strength. Zero strength holds nothing about the person."""
    rng = np.random.default_rng(seed)

    def p(y):
        return cal.expit(0.4 + signal * (2 * y - 1) + rng.normal(0, noise, len(y)))

    return {"test": {t: p(ctx["panel"]["y"][t]) for t in ctx["items"]}, "calibration": {t: p(ctx["pool"]["y"][t]) for t in ctx["items"]}}


# ---------- allocation ----------


def test_targets_respect_caps_and_send_the_surplus_to_free_cells_by_share():
    shares = np.array([0.7, 0.2, 0.1])
    target = stage4.capped_targets(shares, 100, np.array([30, 200, 200]))
    assert target[0] == 30
    assert target[1:].tolist() == pytest.approx([70 * 2 / 3, 70 / 3])


def test_redistribution_repeats_until_no_cell_is_past_its_cap():
    target = stage4.capped_targets(np.array([0.6, 0.3, 0.1]), 100, np.array([10, 20, 500]))
    assert target.tolist() == pytest.approx([10, 20, 70])


def test_rounding_keeps_the_total_and_the_caps_and_breaks_ties_low():
    got = stage4.allocate(np.full(12, 1 / 12), 200, np.full(12, 100))
    assert got.sum() == 200 and got.max() == 17 and got.min() == 16
    assert got[:8].tolist() == [17] * 8
    capped = stage4.allocate(np.array([0.5, 0.25, 0.25]), 10, np.array([2, 4, 4]))
    assert capped.tolist() == [2, 4, 4]


def test_a_pool_smaller_than_the_sample_is_refused():
    with pytest.raises(ValueError):
        stage4.capped_targets(np.array([0.5, 0.5]), 10, np.array([2, 2]))


def test_neyman_favours_the_cell_with_more_spread():
    share = stage4.neyman_shares(np.array([0.5, 0.5]), np.array([0.5, 0.05]))
    assert share[0] > share[1] > 0
    assert share.sum() == pytest.approx(1.0)


def test_allocations_share_rows_in_a_draw_and_weights_add_to_the_cell_share():
    ctx = synthetic_ctx()
    orders = stage4.draw_orders(ctx["pool"]["cells"], CELLS, 2, 42)
    share = np.full(CELLS, 1 / CELLS)
    small = np.full(CELLS, 5)
    big = np.full(CELLS, 10)
    a, wa = stage4.stratified_sample(orders[0], small, ctx["pool"]["w"], ctx["pool"]["cells"], share)
    b, _ = stage4.stratified_sample(orders[0], big, ctx["pool"]["w"], ctx["pool"]["cells"], share)
    assert set(a.tolist()) < set(b.tolist())
    assert wa.sum() == pytest.approx(1.0)
    assert np.bincount(ctx["pool"]["cells"][a], weights=wa, minlength=CELLS) == pytest.approx(share)


def test_allocation_study_runs_and_a_panel_with_no_spread_differences_ties_with_proportional():
    ctx = synthetic_ctx()
    caps = np.bincount(ctx["pool"]["cells"], minlength=CELLS)
    share = caps / caps.sum()
    flat = {t: np.full(CELLS, 0.5) for t in stage4.ITEMS}
    allocations = stage4.build_allocations(share, flat, flat, 200, caps)
    assert allocations["panel_neyman"]["ever"].tolist() == allocations["proportional"]["ever"].tolist()
    store = stage4.allocation_study(ctx, allocations, share, 8, 42)
    doc = stage4.summarise_allocation(store, allocations, caps, 8)
    r = doc["estimators"]["R1"]["panel_excluded"]["cell_mae"]
    assert r["minus_proportional"]["panel_neyman"]["average"]["mean_diff"] == 0.0
    assert doc["reading"]["panel_helps_over_proportional"] is False
    assert set(doc["estimators"]) == {"direct", "shrink", "R1"}
    assert set(doc["estimators"]["R1"]) == {"panel_excluded", "whole_test", "pool_own"}


# ---------- flags ----------


def test_top_k_breaks_ties_low_and_skips_nan():
    assert stage4.top_k(np.array([1.0, np.nan, 1.0, 0.5]), 2) == {0, 2}


def test_overlap_of_identical_lists_is_full_and_random_mean_is_k_squared_over_n():
    v = np.arange(36.0)
    got = stage4.overlap_stats(v, v, 9, 4000, 42)
    assert got["observed"] == 9 and got["usable_units"] == 36
    assert got["random_mean"] == pytest.approx(2.25, abs=0.1)
    assert got["p_one_sided"] < 0.01


def test_spearman_handles_missing_values_and_no_spread():
    assert stage4.spearman([1, 2, np.nan, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert stage4.spearman([1, 1, 1], [1, 2, 3]) is None


def test_flag_study_shape_on_synthetic_answers():
    ctx = synthetic_ctx()
    answers = {"terra_C2": answer_sets(ctx, 0.5, 1), "terra_C1": answer_sets(ctx, 0.5, 2), "luna_C2": answer_sets(ctx, 0.2, 3)}
    positions = np.arange(100)
    stability = {t: np.clip(answers["terra_C2"]["test"][t][:100, None] + np.random.default_rng(4).normal(0, 0.05, (100, 4)), 0, 1) for t in ctx["items"]}
    draws = cal.make_draws(ctx["pool"]["w"], ctx["pool"]["units"], 200, "row", 5, [42, 200, 0], 200, 43)
    doc = stage4.flag_study(ctx, answers, stability, positions, {"bootstrap": 8, "permutations": 200, "seed": 42, "top_k": 9}, draws)
    assert set(doc["signals"]) == {"terra_minus_luna", "c1_minus_c2", "repeat_sd", "panel_level"}
    assert doc["signals"]["panel_level"]["names_wrong_cells"] is None
    assert doc["signals"]["terra_minus_luna"]["usable_units"] == 36


# ---------- the duel rule ----------


def test_folds_are_stratified_and_repeatable():
    cells = np.repeat(np.arange(12), [10, 25, 14, 30, 8, 22, 17, 19, 11, 16, 13, 15])
    a = duel.folds_by_cell(cells, 5, np.random.default_rng([42, 5, 0]))
    b = duel.folds_by_cell(cells, 5, np.random.default_rng([42, 5, 0]))
    assert a.tolist() == b.tolist()
    sizes = np.bincount(a, minlength=5)
    assert sizes.max() - sizes.min() <= 1
    for c in range(12):
        in_cell = np.bincount(a[cells == c], minlength=5)
        assert in_cell.max() - in_cell.min() <= 1


def test_log_loss_is_clipped_and_correct():
    assert duel.log_loss([0.5], [1])[0] == pytest.approx(np.log(2))
    assert np.isfinite(duel.log_loss([0.0, 1.0], [1, 0])).all()


def test_decide_uses_the_t_interval_of_five_folds():
    d = np.array([0.03, 0.02, 0.05, 0.04, 0.01])
    got = duel.decide(d)
    half = stats.t.ppf(0.975, 4) * d.std(ddof=1) / np.sqrt(5)
    assert got["interval"] == pytest.approx([d.mean() - half, d.mean() + half])
    assert got["keep"] is True and got["excludes_zero"] is True


def test_decide_never_keeps_on_an_interval_wholly_below_zero():
    got = duel.decide(np.array([-0.03, -0.02, -0.05, -0.04, -0.01]))
    assert got["keep"] is False and got["excludes_zero"] is True
    assert duel.decide(np.array([0.05, -0.05, 0.05, -0.05, 0.05]))["keep"] is False


def test_the_duel_keeps_a_panel_that_knows_answers_and_drops_one_that_does_not():
    ctx = synthetic_ctx()
    idx = np.random.default_rng(1).choice(632, 200, replace=False)
    pool = ctx["pool"]
    cells = pool["cells"][idx]
    w = pool["w"][idx]

    def run(signal):
        sets = answer_sets(ctx, signal)
        items = {t: (pool["y"][t][idx], sets["calibration"][t][idx]) for t in ctx["items"]}
        return duel.duel(items, cells, w, ctx["cell_age"], ctx["cell_sex"], [42, 5, 0])

    assert run(2.0)["pooled"]["keep"] is True
    assert run(0.0)["pooled"]["keep"] is False


def test_duel_study_and_rates_and_acceptance_on_synthetic_answers():
    ctx = synthetic_ctx()
    draws = cal.make_draws(ctx["pool"]["w"], ctx["pool"]["units"], 200, "row", 6, [42, 200, 0], 200, 43)
    slots = {"strong": answer_sets(ctx, 2.0, 1), "none": answer_sets(ctx, 0.0, 2)}
    raw = stage4.duel_study(ctx, slots, draws, [42, 5])
    doc = stage4.summarise_duel(raw, stage4.ITEMS, 200, 42)
    strong = doc["strong"]["pooled"]["panel_excluded"]
    none = doc["none"]["pooled"]["panel_excluded"]
    assert strong["keep_rate"] > none["keep_rate"]
    assert sum(strong["counts"].values()) == strong["draws"] == 6
    got = stage4.acceptance(raw, {"surrogate_max_keep": 0.12, "positive_min_margin": 0.30}, "strong", ["none"], 200, 42)
    assert got["passed"] is True and got["label"] == "decision_rule"
    failed = stage4.acceptance(raw, {"surrogate_max_keep": 0.12, "positive_min_margin": 0.30}, "none", ["strong"], 200, 42)
    assert failed["passed"] is False and failed["label"] == "health_check"


def test_rates_count_false_and_missed_keeps():
    keep = np.array([True, True, False, False])
    beats = np.array([True, False, True, False])
    got = stage4.rates(keep, beats, 50, 42)
    assert got["counts"] == {"kept_and_beats": 1, "kept_not_beats": 1, "dropped_and_beats": 1, "dropped_not_beats": 1}
    assert got["false_keep_rate"] == 0.5 and got["missed_keep_rate"] == 0.5
    assert got["false_keep_over_all_draws"] == 0.25
    none_kept = stage4.rates(np.zeros(4, dtype=bool), beats, 50, 42)
    assert none_kept["false_keep_rate"] is None


# ---------- the plan ----------


def test_prereg_states_the_rule_the_code_uses():
    doc = json.loads((paths.CONFIG / "prereg_stage4.json").read_text(encoding="utf-8"))
    assert doc["A3_duel"]["acceptance_stated_in_advance"]["surrogate_bar"].count("0.12") == 1
    assert "0.30" in doc["A3_duel"]["acceptance_stated_in_advance"]["positive_bar"]
    assert doc["A1_allocation"]["n"] == 200 and doc["A1_allocation"]["seed"] == 42
    assert doc["B_rules"]["action_table"]["drop_gap_pp"] == 5.0


def test_new_measure_sources_are_ascii():
    for rel in ("src/stage4_measures.py", "src/lotte_audit/stage4.py", "src/lotte_audit/duel.py", "tests/test_stage4_measures.py"):
        (paths.ROOT / rel).read_bytes().decode("ascii")
