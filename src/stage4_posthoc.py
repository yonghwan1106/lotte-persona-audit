"""Post hoc checks of the duel, written after the frozen stage 4 result was seen. Stored answers only, no API, aggregates only.

It changes no rule, no label and no frozen file. Nothing here was planned before the frozen result. It writes results/stage4/duel_post_hoc.json:

  row                frozen draws and frozen fold seeds: Terra C1 and the no-LLM floor, keep and beats, with Terra C2 as a cross check of the frozen file
  unit_intact        keep rates when folds keep survey units whole, row and cluster draws, mean over fold seeds
  same_sample        the same respondents with only the fold seed changed: draw 0 over 500 fold seeds, and the share of the 200 draws whose decision changes over 30

  python src/stage4_posthoc.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stage4_measures as sm  # noqa: E402
from lotte_audit import baselines, duel, duel_units, stage4  # noqa: E402

OUT = sm.RESULTS / "duel_post_hoc.json"
FLOOR = "floor_no_llm"
UNIT_FOLD_SEEDS = (42, 99, 123, 7, 2026)
UNIT_SLOTS = ("terra_C2", "terra_C1", "luna_C1", "surrogate_terra_slot", FLOOR, "control_s1.0", "control_s0.25")
SAME_SAMPLE_SLOTS = ("terra_C2", "terra_C1", "surrogate_terra_slot")
DRAW0_SEEDS = 500
DRAW0_BASE = 10000
FLIP_SEEDS = 30
FLIP_BASE = 9000


def floor_answers(s):
    """The train split age and sex logistic with no shift and no noise. The base of the surrogate panels, with no LLM in it."""
    models = baselines.fit_reference_models(s["df"], s["targets"], s["train"])
    out = {"test": {}, "calibration": {}}
    for t in s["targets"].columns:
        (fm, fc), fcols = models[t]["floor"]
        for name, rows in (("test", s["test_rows"]), ("calibration", s["pool_rows"])):
            out[name][t] = baselines.predict_logistic(fm, fc, s["df"].iloc[rows], fcols)
    return out


def r1_losses(ctx, idx, wts, fold):
    pool = ctx["pool"]
    cells = pool["cells"][idx]
    return {t: duel.r1_fold_losses(pool["y"][t][idx], wts, cells, ctx["cell_age"], ctx["cell_sex"], fold) for t in stage4.ITEMS}


def pooled_decision(ctx, sets, idx, wts, fold, r1):
    """(pooled decision, per item decisions) of one panel on one draw and one fold column."""
    pool = ctx["pool"]
    imp = {t: r1[t] - duel.panel_fold_losses(pool["y"][t][idx], wts, sets["calibration"][t][idx], fold) for t in stage4.ITEMS}
    return duel.decide(np.mean([imp[t] for t in stage4.ITEMS], axis=0)), {t: duel.decide(imp[t]) for t in stage4.ITEMS}


def unit_intact_rates(ctx, slots, draws):
    """Keep rate of each panel per fold seed, mean and range. A draw with fewer units than folds is counted out and the count is stated."""
    pool = ctx["pool"]
    by_seed = {name: [] for name in slots}
    skipped = 0
    for fs in UNIT_FOLD_SEEDS:
        kept = {name: [] for name in slots}
        for r, (idx, wts) in enumerate(draws):
            fold = duel_units.folds_by_unit(pool["units"][idx], duel.FOLDS, np.random.default_rng([fs, duel.FOLDS, r]))
            if len(np.unique(fold)) < duel.FOLDS:
                skipped += 1
                continue
            r1 = r1_losses(ctx, idx, wts, fold)
            for name, sets in slots.items():
                kept[name].append(pooled_decision(ctx, sets, idx, wts, fold, r1)[0]["keep"])
        for name in slots:
            by_seed[name].append(float(np.mean(kept[name])))
    return {
        "fold_seeds": list(UNIT_FOLD_SEEDS),
        "draws_counted_out": skipped,
        "keep_rate": {name: {"mean": round(float(np.mean(v)), 4), "min": round(min(v), 4), "max": round(max(v), 4)} for name, v in by_seed.items()},
    }


def draw_zero(ctx, sets, draw):
    idx, wts = draw
    cells = ctx["pool"]["cells"][idx]
    keep, means = [], []
    items = {t: [] for t in stage4.ITEMS}
    for j in range(DRAW0_SEEDS):
        fold = duel.folds_by_cell(cells, duel.FOLDS, np.random.default_rng([DRAW0_BASE + j, duel.FOLDS, 0]))
        pooled, per_item = pooled_decision(ctx, sets, idx, wts, fold, r1_losses(ctx, idx, wts, fold))
        keep.append(pooled["keep"])
        means.append(pooled["mean_improvement"])
        for t in stage4.ITEMS:
            items[t].append(per_item[t]["keep"])
    return {"fold_seeds": DRAW0_SEEDS, "pooled_keep_share": round(float(np.mean(keep)), 4), "item_keep_share": {t: round(float(np.mean(v)), 4) for t, v in items.items()}, "mean_improvement_range": [round(float(np.min(means)), 4), round(float(np.max(means)), 4)]}


def flips(ctx, slots, draws):
    """Per draw, the share of fold seeds that keep. A draw with a share strictly between 0 and 1 changes its decision with the fold seed alone."""
    pool = ctx["pool"]
    shares = {name: [] for name in slots}
    for r, (idx, wts) in enumerate(draws):
        cells = pool["cells"][idx]
        kept = {name: 0 for name in slots}
        for j in range(FLIP_SEEDS):
            fold = duel.folds_by_cell(cells, duel.FOLDS, np.random.default_rng([FLIP_BASE + j, duel.FOLDS, r]))
            r1 = r1_losses(ctx, idx, wts, fold)
            for name, sets in slots.items():
                kept[name] += int(pooled_decision(ctx, sets, idx, wts, fold, r1)[0]["keep"])
        for name in slots:
            shares[name].append(kept[name] / FLIP_SEEDS)
    out = {}
    for name, values in shares.items():
        v = np.array(values)
        out[name] = {"draws": len(v), "fold_seeds_per_draw": FLIP_SEEDS, "mean_keep": round(float(v.mean()), 4), "share_draws_always_keep": round(float((v == 1).mean()), 4), "share_draws_never_keep": round(float((v == 0).mean()), 4), "share_draws_decision_changes": round(float(((v > 0) & (v < 1)).mean()), 4), "share_draws_between_25_75": round(float(((v >= 0.25) & (v <= 0.75)).mean()), 4)}
    return out


def save(doc):
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    t0 = time.time()
    sm.guard()
    s = sm.setup()
    ctx = s["ctx"]
    frozen = json.loads((sm.RESULTS / "duel_validity.json").read_text(encoding="utf-8"))
    slots = {k: v for k, v in sm.duel_slots(s).items()}
    slots["terra_C1"] = sm.stored(s, sm.TERRA, "C1")
    slots[FLOOR] = floor_answers(s)
    row_draws = sm.stage2_draws(s, 0, "row")
    doc = {
        "written_after_seeing_the_frozen_result": True,
        "note": "Post hoc. These do not replace the frozen acceptance or its label. Same rule, same draws, stored answers. Reported as they came.",
        "frozen_label_kept_in_records": frozen["acceptance"]["label"],
    }
    # Frozen draws and frozen fold seeds, for the two panels the plan had no slot for. Terra C2 is the cross check against the frozen file.
    named = {k: slots[k] for k in ("terra_C2", "terra_C1", FLOOR)}
    raw = stage4.duel_study(ctx, named, row_draws, sm.A3_PLAN["fold_seed"])
    summary = stage4.summarise_duel(raw, stage4.ITEMS, sm.A3_PLAN["resamples"], sm.A3_PLAN["seed"])
    if summary["terra_C2"]["pooled"]["panel_excluded"] != frozen["row"]["terra_C2"]["pooled"]["panel_excluded"]:
        raise SystemExit("Terra C2 does not reproduce the frozen file, so nothing here can be read")
    doc["cross_check_terra_C2_equals_frozen"] = True
    doc["row"] = {name: {**summary[name], "draw0_keep": bool(raw[name]["pooled"]["keep"][0])} for name in ("terra_C1", FLOOR)}
    doc["frozen_draw0_keep"] = {name: bool(raw[name]["pooled"]["keep"][0]) for name in named}
    save(doc)
    print(json.dumps({"step": "row", "seconds": round(time.time() - t0)}), flush=True)
    picked = {k: slots[k] for k in UNIT_SLOTS}
    cluster_draws = sm.stage2_draws(s, 1, "cluster")
    doc["unit_intact"] = {"row": unit_intact_rates(ctx, picked, row_draws)}
    save(doc)
    print(json.dumps({"step": "unit row", "seconds": round(time.time() - t0)}), flush=True)
    doc["unit_intact"]["cluster"] = unit_intact_rates(ctx, picked, cluster_draws)
    save(doc)
    print(json.dumps({"step": "unit cluster", "seconds": round(time.time() - t0)}), flush=True)
    same = {k: slots[k] for k in SAME_SAMPLE_SLOTS}
    doc["same_sample"] = {"draw0": {name: draw_zero(ctx, sets, row_draws[0]) for name, sets in same.items()}}
    save(doc)
    print(json.dumps({"step": "draw 0", "seconds": round(time.time() - t0)}), flush=True)
    doc["same_sample"]["all_draws"] = flips(ctx, same, row_draws)
    save(doc)
    print(json.dumps({"step": "flips", "seconds": round(time.time() - t0)}), flush=True)
    print(json.dumps({k: doc[k] for k in ("frozen_draw0_keep", "unit_intact", "same_sample")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
