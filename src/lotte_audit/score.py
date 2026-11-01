"""Score gate answers. Validates input, computes metrics, applies the pre-registered switch rule.

Answer files are CSVs with: code, p_zero_ever, p_zero_weekly, p_carb_top1. Files may hold any mix of
codes; the key tells which condition each code belongs to.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import baselines, data, metrics, paths, splits

CONDITIONS = ("C0", "C1", "C2")
FROZEN = paths.MANIFESTS / "frozen.json"
FROZEN_FILES = ("prereg.json", "allowlist_final.json", "persona_templates.json", "batch_prompt.json", "leak_patterns.json")


class AnswerValidationError(ValueError):
    pass


def config_hashes():
    # Line endings are normalised so a Windows checkout with autocrlf does not trip the guard.
    return {name: hashlib.sha256((paths.CONFIG / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for name in FROZEN_FILES}


def freeze():
    paths.MANIFESTS.mkdir(parents=True, exist_ok=True)
    FROZEN.write_text(json.dumps(config_hashes(), indent=2), encoding="utf-8")


def check_frozen():
    expected = json.loads(FROZEN.read_text(encoding="utf-8"))
    now = config_hashes()
    changed = [k for k in expected if expected[k] != now.get(k)]
    if changed:
        raise RuntimeError(f"pre-registered config changed since freeze: {changed}")


def load_key(path=None):
    return pd.read_csv(path or paths.GATE_KEY, dtype={"code": str})


def read_answers(answers_dir):
    files = sorted(Path(answers_dir).glob("*.csv"))
    if not files:
        raise AnswerValidationError(f"no answer CSVs in {answers_dir}")
    frames = []
    needed = ["code"] + [paths.ANSWER_COL[t] for t in paths.TARGETS]
    for f in files:
        d = pd.read_csv(f, dtype={"code": str}, encoding="utf-8")
        missing = [c for c in needed if c not in d.columns]
        if missing:
            raise AnswerValidationError(f"{f.name}: missing columns {missing}")
        frames.append(d[needed])
    return pd.concat(frames, ignore_index=True)


def validate(answers, key, conditions=CONDITIONS):
    """Every code of the given conditions present once, nothing unknown, every value a probability."""
    expected = set(key.loc[key.condition.isin(conditions), "code"])
    got = answers["code"].astype(str)
    dup = got[got.duplicated()].unique().tolist()
    if dup:
        raise AnswerValidationError(f"duplicate codes: {dup[:5]} ({len(dup)} total)")
    missing = expected - set(got)
    if missing:
        raise AnswerValidationError(f"missing codes: {len(missing)}, for example {sorted(missing)[:3]}")
    extra = set(got) - expected
    if extra:
        raise AnswerValidationError(f"unknown codes: {len(extra)}, for example {sorted(extra)[:3]}")
    for t in paths.TARGETS:
        col = paths.ANSWER_COL[t]
        v = pd.to_numeric(answers[col], errors="coerce")
        if v.isna().any():
            raise AnswerValidationError(f"{col}: non-numeric or empty values, {int(v.isna().sum())} rows")
        if ((v < 0) | (v > 1)).any():
            raise AnswerValidationError(f"{col}: values outside 0 to 1, {int(((v < 0) | (v > 1)).sum())} rows")


def _r(x, d=3):
    return None if x is None else round(float(x), d)


def real_diagnostics(y, w, ages, sexes, cells):
    return {
        "cell_means": metrics.cell_means(y, w, cells),
        "national": float(np.average(y, weights=w)),
        "age_slope": metrics.age_slope(y, w, ages),
        "gender_gap": metrics.gender_gap(y, w, sexes),
    }


def pattern_check(cond_item, prereg):
    """The pre-registered reproducing-pattern test for one condition and item."""
    rule = prereg["reproducing_pattern"]
    real_slope = cond_item["real_age_slope_pp_per_band"]
    slope = cond_item["age_slope_pp_per_band"]
    ratio = None if slope is None or not real_slope else slope / real_slope
    lo, hi = rule["age_slope_same_sign_and_ratio_between"]
    slope_ok = ratio is not None and lo <= ratio <= hi
    r = cond_item["cell_pearson_r"]
    r_ok = r is not None and r >= rule["cell_pearson_r_at_least"]
    ud = cond_item["underdispersion_ratio"]
    lo, hi = rule["underdispersion_ratio_between"]
    ud_ok = ud is not None and lo <= ud <= hi
    return {"age_slope_ratio": _r(ratio), "slope_ok": slope_ok, "r_ok": r_ok, "underdispersion_ok": ud_ok, "reproduces": bool(slope_ok and r_ok and ud_ok)}


def apply_switch_rule(result, prereg):
    """SWITCH only when C1 and C2 sit at or below the floor on all items and no pattern reproduces."""
    auc_all_at_or_below = True
    pattern_any = False
    detail = []
    for cond in ("C1", "C2"):
        for t in paths.TARGETS:
            item = result["conditions"][cond]["items"][t]
            below = item["auc"] is not None and item["auc"] <= item["floor_auc_same_respondents"]
            auc_all_at_or_below = auc_all_at_or_below and below
            pattern_any = pattern_any or item["pattern"]["reproduces"]
            detail.append({"condition": cond, "item": t, "auc": item["auc"], "floor": item["floor_auc_same_respondents"], "at_or_below_floor": bool(below), "reproduces": item["pattern"]["reproduces"]})
    return {
        "decision": "SWITCH" if (auc_all_at_or_below and not pattern_any) else "NO SWITCH",
        "all_auc_at_or_below_floor": bool(auc_all_at_or_below),
        "any_reproducing_pattern": bool(pattern_any),
        "detail": detail,
    }


def score(answers, key=None, df=None, baseline=None, prereg=None, check_freeze=True):
    if check_freeze:
        check_frozen()
    if df is None:
        df, _ = data.load_sav()
    key = key if key is not None else load_key()
    prereg = prereg or json.loads((paths.CONFIG / "prereg.json").read_text(encoding="utf-8"))
    baseline = baseline or json.loads((paths.RESULTS / "baselines.json").read_text(encoding="utf-8"))
    validate(answers, key)
    manifest = splits.load_manifest(df)
    mk = splits.masks(manifest)
    train, test = mk["train"], mk["test"]
    targets = data.derive_targets(df)
    cells = data.cell_id(df)
    w = df[paths.WEIGHT].to_numpy()
    ages = df[paths.AGE].to_numpy()
    sexes = df[paths.SEX].to_numpy()
    units = df[paths.PSU].to_numpy()
    merged = key.merge(answers, on="code", how="left", validate="one_to_one")
    panel_rows = sorted(set(key.loc[key.condition.isin(["C1", "C2"]), "row_index"]))
    if not test[np.array(panel_rows)].all():
        raise AnswerValidationError("a panel respondent is outside the test split")
    models = baselines.fit_reference_models(df, targets, train)
    result = {"conditions": {}, "panel_n": len(panel_rows)}
    # Real answers of the same 300, as a reference for what a perfect panel would score.
    panel_key = key.loc[key.condition == "C1"].set_index("row_index")
    panel_idx = np.array(panel_rows)
    panel_w = panel_key.loc[panel_rows, "panel_weight"].to_numpy()

    for cond in CONDITIONS:
        sub = merged.loc[merged.condition == cond]
        cond_out = {"items": {}, "n": int(len(sub))}
        for t in paths.TARGETS:
            col = paths.ANSWER_COL[t]
            p = pd.to_numeric(sub[col]).to_numpy()
            y = targets[t].to_numpy()
            truth = real_diagnostics(y[test], w[test], ages[test], sexes[test], cells[test])
            base = baseline["items"][t]
            item = {
                "constant_cell_mae": base["constant_cell_mae"],
                "real_age_slope_pp_per_band": _r(truth["age_slope"]),
                "real_gender_gap_pp": _r(truth["gender_gap"]),
                "ceiling_auc_test_split": base["ceiling_allowlist_logistic"]["auc"],
                "floor_auc_test_split": base["floor_age_sex"]["auc"],
                "floor_all_demographics_auc_test_split": base["floor_all_c1_demographics"]["auc"],
            }
            if cond == "C0":
                est = float(np.mean(p))
                estimate = {k: est for k in truth["cell_means"]}
                mae = metrics.constant_mae(est, truth["cell_means"])
                item.update(
                    {
                        "auc": None,
                        "auc_note": "n/a by design, C0 is not linked to respondents",
                        "panel_mean_pct": _r(100 * est, 2),
                        "repeat_sd_pct": _r(100 * float(np.std(p, ddof=1)), 2),
                        "bias_pp": _r(100 * (est - truth["national"]), 2),
                        "cell_mae": _r(mae, 2),
                        "underdispersion_ratio": 0.0,
                        "cell_pearson_r": None,
                        "age_slope_pp_per_band": 0.0,
                        "gender_gap_pp": 0.0,
                        "floor_auc_same_respondents": None,
                        "floor_all_demographics_auc_same_respondents": None,
                        "pattern": {"reproduces": False},
                    }
                )
            else:
                rows = sub["row_index"].to_numpy()
                wp = sub["panel_weight"].to_numpy()
                c = cells[rows]
                est_map = metrics.cell_means(p, wp, c)
                est_mean = float(np.average(p, weights=wp))
                mae = metrics.cell_mae(est_map, truth["cell_means"])
                auc = metrics.weighted_auc(y[rows], p, wp)
                (fm, fc), fcols = models[t]["floor"]
                floor_p = baselines.predict_logistic(fm, fc, df.iloc[rows], fcols)
                (dm, dc), dcols = models[t]["floor_demog"]
                demog_p = baselines.predict_logistic(dm, dc, df.iloc[rows], dcols)
                within, used = metrics.within_group_auc(y[rows], p, units[rows], wp)
                item.update(
                    {
                        "auc": _r(auc, 6),
                        "auc_ci95_unit_bootstrap": baselines.unit_bootstrap_auc(y[rows], p, wp, units[rows]),
                        "auc_sensitivity_psfwt_double_weighted": _r(metrics.weighted_auc(y[rows], p, w[rows])),
                        "auc_sensitivity_unweighted": _r(metrics.weighted_auc(y[rows], p, np.ones(len(rows)))),
                        "within_unit_auc": _r(within),
                        "within_unit_groups": used,
                        "panel_mean_pct": _r(100 * est_mean, 2),
                        "bias_pp": _r(100 * (est_mean - truth["national"]), 2),
                        "cell_mae": _r(mae, 2),
                        "panel_cells": len(est_map),
                        "underdispersion_ratio": _r(metrics.underdispersion(est_map, truth["cell_means"])),
                        "cell_pearson_r": _r(metrics.cell_pearson(est_map, truth["cell_means"])),
                        "age_slope_pp_per_band": _r(metrics.age_slope(p, wp, ages[rows])),
                        "gender_gap_pp": _r(metrics.gender_gap(p, wp, sexes[rows])),
                        "floor_auc_same_respondents": _r(metrics.weighted_auc(y[rows], floor_p, wp), 6),
                        "floor_all_demographics_auc_same_respondents": _r(metrics.weighted_auc(y[rows], demog_p, wp), 6),
                    }
                )
                item["pattern"] = pattern_check(item, prereg)
            item["beats_constant"] = bool(item["cell_mae"] < item["constant_cell_mae"])
            item["worth_n"] = metrics.worth_n(item["cell_mae"], item["constant_cell_mae"], {int(n): v for n, v in base["best_of_raw_shrunk"].items()})
            cond_out["items"][t] = item
        avg_mae = float(np.mean([cond_out["items"][t]["cell_mae"] for t in paths.TARGETS]))
        avg = baseline["average_over_items"]
        cond_out["average_cell_mae"] = _r(avg_mae, 2)
        cond_out["average_constant_cell_mae"] = avg["constant_cell_mae"]
        cond_out["worth_n"] = metrics.worth_n(avg_mae, avg["constant_cell_mae"], {int(n): v for n, v in avg["best_of_raw_shrunk"].items()})
        ok = pd.to_numeric(sub[paths.ANSWER_COL["weekly"]]).to_numpy() <= pd.to_numeric(sub[paths.ANSWER_COL["ever"]]).to_numpy() + 1e-9
        cond_out["weekly_exceeds_ever_rows"] = int((~ok).sum())
        result["conditions"][cond] = cond_out

    # What the same 300 people really answered, scored the same way. Sets the panel's sampling floor.
    ref = {}
    for t in paths.TARGETS:
        y = targets[t].to_numpy()
        truth = metrics.cell_means(y[test], w[test], cells[test])
        ref[t] = _r(metrics.cell_mae(metrics.cell_means(y[panel_idx], panel_w, cells[panel_idx]), truth), 2)
    ref["average"] = _r(float(np.mean([ref[t] for t in paths.TARGETS])), 2)
    result["same_300_real_answers_cell_mae"] = ref
    result["switch_rule"] = apply_switch_rule(result, prereg)
    result["config_sha256"] = config_hashes()
    return result


def gate_reference():
    """Aggregates on the 300 gate respondents, computed before any answer exists."""
    df, _ = data.load_sav()
    key = load_key()
    manifest = splits.load_manifest(df)
    mk = splits.masks(manifest)
    targets = data.derive_targets(df)
    cells = data.cell_id(df)
    w = df[paths.WEIGHT].to_numpy()
    units = df[paths.PSU].to_numpy()
    panel = key.loc[key.condition == "C1"].set_index("row_index").sort_index()
    rows = panel.index.to_numpy()
    wp = panel["panel_weight"].to_numpy()
    test = mk["test"]
    models = baselines.fit_reference_models(df, targets, mk["train"])
    out = {
        "panel_n": int(len(rows)),
        "all_in_test": bool(test[rows].all()),
        "units": int(len(set(units[rows]))),
        "cells_present": int(len(set(cells[rows]))),
        "min_cell_n": int(pd.Series(cells[rows]).value_counts().min()),
        "panel_weight_max_over_median": _r(float(wp.max() / np.median(wp)), 2),
        "items": {},
    }
    for t in paths.TARGETS:
        y = targets[t].to_numpy()
        truth = metrics.cell_means(y[test], w[test], cells[test])
        (fm, fc), fcols = models[t]["floor"]
        floor_p = baselines.predict_logistic(fm, fc, df.iloc[rows], fcols)
        (dm, dc), dcols = models[t]["floor_demog"]
        demog_p = baselines.predict_logistic(dm, dc, df.iloc[rows], dcols)
        out["items"][t] = {
            "positives": int(y[rows].sum()),
            "weighted_pct_panel": _r(100 * float(np.average(y[rows], weights=wp)), 2),
            "weighted_pct_test": _r(100 * float(np.average(y[test], weights=w[test])), 2),
            "floor_auc_same_respondents": _r(metrics.weighted_auc(y[rows], floor_p, wp), 3),
            "floor_auc_ci95_unit_bootstrap": baselines.unit_bootstrap_auc(y[rows], floor_p, wp, units[rows]),
            "floor_all_demographics_auc_same_respondents": _r(metrics.weighted_auc(y[rows], demog_p, wp), 3),
            "same_300_real_answers_cell_mae": _r(metrics.cell_mae(metrics.cell_means(y[rows], wp, cells[rows]), truth), 2),
        }
    out["same_300_real_answers_average_cell_mae"] = _r(float(np.mean([out["items"][t]["same_300_real_answers_cell_mae"] for t in paths.TARGETS])), 2)
    (paths.RESULTS / "gate_reference.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def to_markdown(r):
    lines = ["# Gate score", "", f"Decision: **{r['switch_rule']['decision']}**", "", f"Panel n: {r['panel_n']}. Same 300 real answers cell MAE: {r['same_300_real_answers_cell_mae']}", ""]
    lines += ["| cond | item | cell MAE | constant | beats constant | worth N | AUC | floor same 300 | floor all demog same 300 | ceiling test | bias pp | underdisp | gender gap panel | gender gap real | age slope panel | age slope real | pattern |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for cond in CONDITIONS:
        for t in paths.TARGETS:
            v = r["conditions"][cond]["items"][t]
            lines.append(
                "| "
                + " | ".join(
                    str(x)
                    for x in [
                        cond,
                        t,
                        v["cell_mae"],
                        v["constant_cell_mae"],
                        v["beats_constant"],
                        v["worth_n"]["label"],
                        _r(v["auc"]),
                        _r(v["floor_auc_same_respondents"]),
                        _r(v["floor_all_demographics_auc_same_respondents"]),
                        v["ceiling_auc_test_split"],
                        v["bias_pp"],
                        v["underdispersion_ratio"],
                        v["gender_gap_pp"],
                        v["real_gender_gap_pp"],
                        v["age_slope_pp_per_band"],
                        v["real_age_slope_pp_per_band"],
                        v["pattern"]["reproduces"],
                    ]
                )
                + " |"
            )
    lines += ["", "## Average over items", "", "| cond | average cell MAE | constant | worth N |", "|---|---|---|---|"]
    for cond in CONDITIONS:
        c = r["conditions"][cond]
        lines.append(f"| {cond} | {c['average_cell_mae']} | {c['average_constant_cell_mae']} | {c['worth_n']['label']} |")
    return "\n".join(lines) + "\n"


def write(result, out_dir=None, name="gate_score"):
    out_dir = Path(out_dir or paths.RESULTS)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{name}.md").write_text(to_markdown(result), encoding="utf-8")
