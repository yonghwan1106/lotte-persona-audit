"""Score the main stage: calibration study, person level, stereotypes, stability, trust map.

score_main works on arrays held in a context dict, so synthetic answers can run the whole path in tests.
Outputs are aggregates only. Nothing per respondent leaves this module.
"""
import numpy as np
import pandas as pd

from . import baselines, calibration as cal, data, metrics, paths, splits, verdict

CONDITIONS = ("C1", "C2")
AVERAGE = "average"
PRIMARY_MODEL = "gpt-6.1-terra"
PRIMARY_CONDITION = "C2"
PRIMARY_N = 200
ALPHA = 0.05


def label(model, cond):
    return f"{model}|{cond}"


def holm(pvalues):
    """Holm adjusted p values in the order given."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    adjusted = np.zeros(len(p))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(p) - rank) * p[i])
        adjusted[i] = min(1.0, running)
    return adjusted.tolist()


def bootstrap_p(diffs):
    d = np.asarray(diffs, dtype=float)
    r = len(d)
    return min(1.0, 2 * min((1 + np.sum(d <= 0)) / (r + 1), (1 + np.sum(d >= 0)) / (r + 1)))


def percentile_ci(values, digits=3):
    lo, hi = np.percentile(values, [2.5, 97.5])
    return [round(float(lo), digits), round(float(hi), digits)]


def build_context(df, key, baseline_doc):
    """Collect the arrays that scoring needs from the raw file and the key."""
    manifest = splits.load_manifest(df)
    mk = splits.masks(manifest)
    train, test = mk["train"], mk["test"]
    targets = data.derive_targets(df)
    cells_raw = data.cell_id(df)
    w = df[paths.WEIGHT].to_numpy()
    universe = sorted(set(cells_raw[test].tolist()))
    index = {c: i for i, c in enumerate(universe)}
    cells = np.array([index[c] for c in cells_raw])
    ages = df[paths.AGE].astype(int).to_numpy()
    sexes = df[paths.SEX].astype(int).to_numpy()
    units = df[paths.PSU].to_numpy()
    m = len(universe)
    y = {t: targets[t].to_numpy() for t in paths.TARGETS}

    panel = key.loc[(key.split == "test") & (key.condition == "C1")].sort_values("row_index")
    panel_rows = panel["row_index"].to_numpy()
    pool = key.loc[(key.split == "calibration") & (key.condition == "C1")].sort_values("row_index")
    pool_rows = pool["row_index"].to_numpy()
    if not test[panel_rows].all() or not mk["calibration"][pool_rows].all():
        raise RuntimeError("a respondent is outside its split")
    if set(units[panel_rows]) & set(units[pool_rows]):
        raise RuntimeError("a survey unit crosses splits")
    outside = test.copy()
    outside[panel_rows] = False

    models = baselines.fit_reference_models(df, targets, train)
    floor_p = {}
    for t in paths.TARGETS:
        (fm, fc), fcols = models[t]["floor"]
        floor_p[t] = baselines.predict_logistic(fm, fc, df.iloc[panel_rows], fcols)

    test_rows = np.flatnonzero(test)
    position = {r: i for i, r in enumerate(test_rows.tolist())}
    bands = sorted({c // 10 for c in universe})
    return {
        "items": list(paths.TARGETS),
        "m": m,
        "cell_age": np.array([bands.index(c // 10) for c in universe], dtype=float),
        "cell_sex": np.array([c % 10 - 1 for c in universe], dtype=float),
        "truth": {t: cal.cell_mean(y[t][test].astype(float), w[test], cells[test], m) for t in paths.TARGETS},
        "truth_outside_panel": {t: cal.cell_mean(y[t][outside].astype(float), w[outside], cells[outside], m) for t in paths.TARGETS},
        "constant": {t: float(np.average(y[t][train], weights=w[train])) for t in paths.TARGETS},
        "constant_expected_mae": {t: baseline_doc["items"][t]["constant_cell_mae"] for t in paths.TARGETS},
        "noise_floor_pp": baseline_doc["average_over_items"]["full_train_raw_cell_mae"],
        "noise_floor_by_item_pp": {t: baseline_doc["items"][t]["full_train_raw_cell_mae"] for t in paths.TARGETS},
        "panel": {
            "w": panel["analysis_weight"].to_numpy(),
            "cells": cells[panel_rows],
            "y": {t: y[t][panel_rows].astype(float) for t in paths.TARGETS},
            "units": units[panel_rows],
            "ages": ages[panel_rows],
            "sexes": sexes[panel_rows],
            "floor_p": floor_p,
            "positions_in_test": np.array([position[r] for r in panel_rows.tolist()]),
        },
        "pool": {
            "w": w[pool_rows],
            "cells": cells[pool_rows],
            "y": {t: y[t][pool_rows].astype(float) for t in paths.TARGETS},
            "units": units[pool_rows],
        },
        "test": {
            "w": w[test],
            "y": {t: y[t][test].astype(float) for t in paths.TARGETS},
            "units": units[test],
            "ages": ages[test],
            "sexes": sexes[test],
            "cells": cells[test],
        },
    }


# ---------- calibration study ----------


def one_draw(ctx, answers, idx, wts):
    """Cell MAE of every estimator for one sample. Returns ({key: {item: mae}}, same on the outside truth, fits)."""
    pool, panel, m = ctx["pool"], ctx["panel"], ctx["m"]
    cells_s = pool["cells"][idx]
    mae, mae_out, fits = {}, {}, {}

    def put(name, item, estimate):
        mae.setdefault(name, {})[item] = cal.cell_mae(estimate, ctx["truth"][item])
        mae_out.setdefault(name, {})[item] = cal.cell_mae(estimate, ctx["truth_outside_panel"][item])

    for item in ctx["items"]:
        y_s = pool["y"][item][idx]
        direct, shrunk = cal.direct_and_shrunk(y_s, wts, cells_s, m)
        put("E1", item, direct)
        put("E2", item, shrunk)
        put("R1", item, cal.age_sex_model_cells(y_s, wts, cells_s, ctx["cell_age"], ctx["cell_sex"]))
        for key, sets in answers.items():
            p_s = sets["calibration"][item][idx]
            p_test = sets["test"][item]
            d = cal.fit_offset(p_s, y_s, wts)
            put(f"{key}|E4", item, cal.offset_estimate(d, p_test, panel["w"], panel["cells"], m))
            a, b, status = cal.fit_recalibration(p_s, y_s, wts)
            put(f"{key}|E5", item, cal.recalibrated_estimate(a, b, p_test, panel["w"], panel["cells"], m))
            put(f"{key}|E6", item, cal.difference_estimate(p_s, y_s, wts, cells_s, p_test, panel["w"], panel["cells"], m))
            fits.setdefault(key, {})[item] = (d, a, b, status)
    return mae, mae_out, fits


def calibration_study(ctx, answers, ns, kinds, repeats, seed, pi_draws, pi_seed):
    """Run every draw. Returns raw per-draw arrays keyed by (n, kind)."""
    pool = ctx["pool"]
    out = {}
    for n in ns:
        for k_i, kind in enumerate(kinds):
            draws = cal.make_draws(pool["w"], pool["units"], n, kind, repeats, [seed, n, k_i], pi_draws, pi_seed)
            mae, mae_out, fits, realised = {}, {}, {}, []
            for idx, wts in draws:
                realised.append(len(idx))
                got, got_out, f = one_draw(ctx, answers, idx, wts)
                for store, source in ((mae, got), (mae_out, got_out)):
                    for name, by_item in source.items():
                        slot = store.setdefault(name, {})
                        for item, value in by_item.items():
                            slot.setdefault(item, []).append(value)
                for key, by_item in f.items():
                    slot = fits.setdefault(key, {})
                    for item, value in by_item.items():
                        slot.setdefault(item, []).append(value)
            out[(n, kind)] = {"mae": mae, "mae_outside": mae_out, "fits": fits, "realised_n": realised}
    return out


def with_average(by_item, items):
    arrays = {t: np.asarray(by_item[t], dtype=float) for t in items}
    arrays[AVERAGE] = np.mean([arrays[t] for t in items], axis=0)
    return arrays


def summarise_study(ctx, answers, study, fixed, fixed_outside):
    """Mean MAE and paired difference to E2 for every estimator, item, n, draw kind."""
    items = ctx["items"]
    summary = {}
    for (n, kind), run in study.items():
        block = {
            "realised_n_mean": round(float(np.mean(run["realised_n"])), 1),
            "realised_n_min": int(np.min(run["realised_n"])),
            "realised_n_max": int(np.max(run["realised_n"])),
            "estimators": {},
            "estimators_outside_panel_truth": {},
            "difference_to_R1": {},
            "fit_diagnostics": {},
        }
        for store_name, mae, fx in (("estimators", run["mae"], fixed), ("estimators_outside_panel_truth", run["mae_outside"], fixed_outside)):
            e2 = with_average(mae["E2"], items)
            r1 = with_average(mae["R1"], items)
            for name, by_item in mae.items():
                arrays = with_average(by_item, items)
                block[store_name][name] = {
                    t: {"cell_mae": round(float(arrays[t].mean()), 3), **({} if name == "E2" else cal.difference_summary(arrays[t], e2[t]))}
                    for t in arrays
                }
                if store_name == "estimators" and name.split("|")[-1] in ("E4", "E5", "E6"):
                    block["difference_to_R1"][name] = {t: cal.difference_summary(arrays[t], r1[t]) for t in arrays}
            for name, by_item in fx.items():
                values = {t: by_item[t] for t in items}
                values[AVERAGE] = float(np.mean([by_item[t] for t in items]))
                block[store_name][name] = {
                    t: {"cell_mae": round(float(values[t]), 3), **cal.difference_summary(np.full(len(e2[t]), values[t]), e2[t])}
                    for t in values
                }
        for key, by_item in run["fits"].items():
            block["fit_diagnostics"][key] = {}
            for t, rows in by_item.items():
                d = np.array([r[0] for r in rows])
                a = np.array([r[1] for r in rows])
                b = np.array([r[2] for r in rows])
                statuses = [r[3] for r in rows]
                block["fit_diagnostics"][key][t] = {
                    "offset_mean": round(float(d.mean()), 3),
                    "a_mean": round(float(a.mean()), 3),
                    "b_mean": round(float(b.mean()), 3),
                    "b_ci95": percentile_ci(b),
                    "e5_fallbacks": int(sum(s != "ok" for s in statuses)),
                }
        summary[f"{n}|{kind}"] = block
    return summary


def fixed_estimators(ctx, answers):
    """E0 and E3 do not depend on the draw. Returns them on both truths."""
    panel, m = ctx["panel"], ctx["m"]
    out, outside = {"E0": {}}, {"E0": {}}
    for item in ctx["items"]:
        constant = np.full(m, ctx["constant"][item])
        out["E0"][item] = cal.cell_mae(constant, ctx["truth"][item])
        outside["E0"][item] = cal.cell_mae(constant, ctx["truth_outside_panel"][item])
    for key, sets in answers.items():
        out[f"{key}|E3"], outside[f"{key}|E3"] = {}, {}
        for item in ctx["items"]:
            e3 = cal.panel_cells(sets["test"][item], panel["w"], panel["cells"], m)
            out[f"{key}|E3"][item] = cal.cell_mae(e3, ctx["truth"][item])
            outside[f"{key}|E3"][item] = cal.cell_mae(e3, ctx["truth_outside_panel"][item])
    return out, outside


def reference_values(ctx):
    pool, panel, m = ctx["pool"], ctx["panel"], ctx["m"]
    out = {"noise_floor_average_pp": ctx["noise_floor_pp"], "noise_floor_by_item_pp": ctx["noise_floor_by_item_pp"], "pool_all_rows_direct": {}, "pool_all_rows_shrunk": {}, "test_panel_real_answers": {}}
    for item in ctx["items"]:
        direct, shrunk = cal.direct_and_shrunk(pool["y"][item], pool["w"], pool["cells"], m)
        out["pool_all_rows_direct"][item] = round(cal.cell_mae(direct, ctx["truth"][item]), 3)
        out["pool_all_rows_shrunk"][item] = round(cal.cell_mae(shrunk, ctx["truth"][item]), 3)
        real = cal.cell_mean(panel["y"][item], panel["w"], panel["cells"], m)
        out["test_panel_real_answers"][item] = round(cal.cell_mae(real, ctx["truth"][item]), 3)
    for name in ("pool_all_rows_direct", "pool_all_rows_shrunk", "test_panel_real_answers"):
        out[name][AVERAGE] = round(float(np.mean([out[name][t] for t in ctx["items"]])), 3)
    return out


# ---------- person level ----------


def person_level(ctx, answers, reps, seed):
    panel = ctx["panel"]
    uniq, groups = cal.unit_table(panel["units"])
    w = panel["w"]
    out = {}
    for item_i, item in enumerate(ctx["items"]):
        y = panel["y"][item]
        floor = panel["floor_p"][item]
        floor_auc = metrics.weighted_auc(y, floor, w)
        floor_within, floor_used = metrics.within_group_auc(y, floor, panel["units"], w)
        rng = np.random.default_rng([seed, item_i])
        picks = rng.integers(0, len(uniq), size=(reps, len(uniq)))
        boots_floor = np.full(reps, np.nan)
        boots_panel = {key: np.full(reps, np.nan) for key in answers}
        for r in range(reps):
            idx = np.concatenate([groups[g] for g in picks[r]])
            f = metrics.weighted_auc(y[idx], floor[idx], w[idx])
            if f is None:
                continue
            boots_floor[r] = f
            for key, sets in answers.items():
                boots_panel[key][r] = metrics.weighted_auc(y[idx], sets["test"][item][idx], w[idx])
        block = {
            "positives": int(y.sum()),
            "floor_auc": round(float(floor_auc), 4),
            "floor_within_unit_auc": None if floor_within is None else round(floor_within, 4),
            "within_unit_usable_units": floor_used,
            "by_panel": {},
        }
        for key, sets in answers.items():
            p = sets["test"][item]
            auc = metrics.weighted_auc(y, p, w)
            within, used = metrics.within_group_auc(y, p, panel["units"], w)
            diffs = boots_panel[key] - boots_floor
            diffs = diffs[~np.isnan(diffs)]
            block["by_panel"][key] = {
                "auc": round(float(auc), 4),
                "auc_minus_floor": round(float(auc - floor_auc), 4),
                "diff_ci95": percentile_ci(diffs, 4),
                "resamples_used": int(len(diffs)),
                "p_two_sided": round(float(bootstrap_p(diffs)), 4),
                "within_unit_auc": None if within is None else round(within, 4),
                "within_unit_usable_units": used,
            }
        out[item] = block
    primary = label(PRIMARY_MODEL, PRIMARY_CONDITION)
    if all(primary in out[t]["by_panel"] for t in ctx["items"]):
        raw = [out[t]["by_panel"][primary]["p_two_sided"] for t in ctx["items"]]
        adjusted = holm(raw)
        for t, a in zip(ctx["items"], adjusted):
            out[t]["by_panel"][primary]["holm_p"] = round(a, 4)
            out[t]["by_panel"][primary]["holm_reject_at_0_05"] = bool(a < ALPHA)
    return out


# ---------- stereotypes ----------


def stereotypes(ctx, answers, reps, seed):
    test, panel, m = ctx["test"], ctx["panel"], ctx["m"]
    uniq, test_groups = cal.unit_table(test["units"])
    unit_of = {u: i for i, u in enumerate(uniq.tolist())}
    panel_groups = [[] for _ in uniq]
    for i, u in enumerate(panel["units"].tolist()):
        panel_groups[unit_of[u]].append(i)
    panel_groups = [np.array(g, dtype=int) for g in panel_groups]
    rng = np.random.default_rng([seed, 7])
    picks = rng.integers(0, len(uniq), size=(reps, len(uniq)))
    boot = {}
    for r in range(reps):
        i_test = np.concatenate([test_groups[g] for g in picks[r]])
        i_panel = np.concatenate([panel_groups[g] for g in picks[r]]) if len(picks[r]) else np.array([], dtype=int)
        for item in ctx["items"]:
            yt = test["y"][item][i_test]
            real_gap = metrics.gender_gap(yt, test["w"][i_test], test["sexes"][i_test])
            real_slope = metrics.age_slope(yt, test["w"][i_test], test["ages"][i_test])
            slot = boot.setdefault(item, {"real_gap": [], "real_slope": [], "panel": {}})
            slot["real_gap"].append(real_gap)
            slot["real_slope"].append(real_slope)
            for key, sets in answers.items():
                pp = sets["test"][item][i_panel]
                wp = panel["w"][i_panel]
                gap = metrics.gender_gap(pp, wp, panel["sexes"][i_panel])
                slope = metrics.age_slope(pp, wp, panel["ages"][i_panel])
                s = slot["panel"].setdefault(key, {"gap": [], "slope": []})
                s["gap"].append(gap)
                s["slope"].append(slope)
    out = {}
    for item in ctx["items"]:
        truth = ctx["truth"][item]
        real_national = float(np.average(test["y"][item], weights=test["w"]))
        real_gap = metrics.gender_gap(test["y"][item], test["w"], test["sexes"])
        real_slope = metrics.age_slope(test["y"][item], test["w"], test["ages"])
        rg = np.array(boot[item]["real_gap"], dtype=float)
        rs = np.array(boot[item]["real_slope"], dtype=float)
        block = {
            "real_national_pct": round(100 * real_national, 2),
            "real_gender_gap_pp": round(real_gap, 3),
            "real_gender_gap_ci95": percentile_ci(rg),
            "real_age_slope_pp_per_band": round(real_slope, 3),
            "real_age_slope_ci95": percentile_ci(rs),
            "by_panel": {},
        }
        truth_map = {i: float(v) for i, v in enumerate(truth)}
        for key, sets in answers.items():
            p = sets["test"][item]
            est = metrics.cell_means(p, panel["w"], panel["cells"], list(range(m)))
            gap = metrics.gender_gap(p, panel["w"], panel["sexes"])
            slope = metrics.age_slope(p, panel["w"], panel["ages"])
            pg = np.array(boot[item]["panel"][key]["gap"], dtype=float)
            ps = np.array(boot[item]["panel"][key]["slope"], dtype=float)
            block["by_panel"][key] = {
                "panel_mean_pct": round(100 * float(np.average(p, weights=panel["w"])), 2),
                "bias_pp": round(100 * (float(np.average(p, weights=panel["w"])) - real_national), 2),
                "gender_gap_pp": round(gap, 3),
                "gender_gap_ci95": percentile_ci(pg),
                "gap_minus_real_ci95": percentile_ci(pg - rg),
                "age_slope_pp_per_band": round(slope, 3),
                "age_slope_ci95": percentile_ci(ps),
                "slope_minus_real_ci95": percentile_ci(ps - rs),
                "underdispersion_ratio": round(metrics.underdispersion(est, truth_map), 3),
                "cell_pearson_r": round(metrics.cell_pearson(est, truth_map), 3),
            }
        out[item] = block
    return out


# ---------- stability ----------


def rank_correlation(a, b):
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def stability(answers_by_repeat, items):
    """answers_by_repeat[item] has shape (respondents, answers). Compares all pairs of answers."""
    if answers_by_repeat is None:
        return None
    out = {}
    for item in items:
        a = np.asarray(answers_by_repeat[item], dtype=float)
        k = a.shape[1]
        mads, rhos = [], []
        for i in range(k):
            for j in range(i + 1, k):
                mads.append(float(np.mean(np.abs(a[:, i] - a[:, j]))))
                rhos.append(rank_correlation(a[:, i], a[:, j]))
        valid = [r for r in rhos if r is not None]
        out[item] = {
            "respondents": int(a.shape[0]),
            "answers_each": int(k),
            "pairs": len(mads),
            "mean_abs_diff_pp": round(100 * float(np.mean(mads)), 3),
            "max_pair_mean_abs_diff_pp": round(100 * float(np.max(mads)), 3),
            "rank_correlation_mean": None if not valid else round(float(np.mean(valid)), 4),
            "rank_correlation_min": None if not valid else round(float(np.min(valid)), 4),
            "within_person_sd_pp": round(100 * float(np.sqrt(np.mean(a.var(axis=1, ddof=1)))), 3),
            "between_person_sd_pp": round(100 * float(a.mean(axis=1).std(ddof=1)), 3),
        }
    return out


# ---------- trust map ----------


def trust_map(ctx, answers, summary, stereo):
    out = []
    row = summary[f"{PRIMARY_N}|row"]["estimators"]
    cluster = summary[f"{PRIMARY_N}|cluster"]["estimators"]
    for key in answers:
        model, cond = key.split("|")
        for item in ctx["items"]:
            comp_row = {e: row[f"{key}|{e}"][item] for e in verdict.CALIBRATED_ESTIMATORS}
            comp_cluster = {e: cluster[f"{key}|{e}"][item] for e in verdict.CALIBRATED_ESTIMATORS}
            s = stereo[item]
            p = s["by_panel"][key]
            v = verdict.item_verdict(comp_row, comp_cluster, p["age_slope_pp_per_band"], s["real_age_slope_ci95"], p["cell_pearson_r"], p["underdispersion_ratio"])
            out.append({"item": item, "model": model, "condition": cond, **v})
    return out


# ---------- everything ----------


def score_main(ctx, answers, stability_answers, plan):
    ns = plan["n"]
    kinds = plan["kinds"]
    fixed, fixed_outside = fixed_estimators(ctx, answers)
    study = calibration_study(ctx, answers, ns, kinds, plan["repeats"], plan["seed"], plan["pi_draws"], plan["pi_seed"])
    summary = summarise_study(ctx, answers, study, fixed, fixed_outside)
    stereo = stereotypes(ctx, answers, plan["bootstrap"], plan["seed"])
    result = {
        "scored": sorted(answers),
        "reference": reference_values(ctx),
        "calibration": summary,
        "person_level": person_level(ctx, answers, plan["bootstrap"], plan["seed"]),
        "stereotypes": stereo,
        "stability": stability(stability_answers, ctx["items"]),
        "trust_map": trust_map(ctx, answers, summary, stereo),
        "raw_panel_number_as_market_number": False,
    }
    return result


# ---------- markdown ----------


def fmt_diff(v):
    return f"{v['cell_mae']:.2f} ({v['mean_diff']:+.2f} [{v['ci95'][0]:+.2f},{v['ci95'][1]:+.2f}])"


def fmt_ci(ci):
    return f"[{ci[0]:+.2f},{ci[1]:+.2f}]"


def calibration_tables(result, items):
    lines = []
    keys = sorted(k for k in result["scored"])
    order = sorted(result["calibration"], key=lambda s: (int(s.split("|")[0]), s.split("|")[1] != "row"))
    lines += ["| item | n | draw | realised n | E0 | E1 | E2 | R1 no panel, reference |", "|---|---|---|---|---|---|---|---|"]
    for t in [*items, AVERAGE]:
        for block_key in order:
            n, kind = block_key.split("|")
            b = result["calibration"][block_key]
            e = b["estimators"]
            lines.append(f"| {t} | {n} | {kind} | {b['realised_n_mean']} | {fmt_diff(e['E0'][t])} | {fmt_diff(e['E1'][t])} | {e['E2'][t]['cell_mae']:.2f} | {fmt_diff(e['R1'][t])} |")
    lines += ["", "| item | n | draw | model | cond | E3 raw, not a market number | E4 | E5 (on C1 this is E7) | E6 |", "|---|---|---|---|---|---|---|---|---|"]
    for t in [*items, AVERAGE]:
        for block_key in order:
            n, kind = block_key.split("|")
            e = result["calibration"][block_key]["estimators"]
            for key in keys:
                model, cond = key.split("|")
                cells = [fmt_diff(e[f"{key}|{name}"][t]) for name in ("E3", "E4", "E5", "E6")]
                lines.append(f"| {t} | {n} | {kind} | {model} | {cond} | " + " | ".join(cells) + " |")
    return lines


def to_markdown(result, items):
    lines = ["# Main stage score", "", "All E columns: cell MAE in pp (paired mean difference to E2 [percentile 95 percent interval across 200 draws]). Negative means better than E2. E3 is the raw panel and is never a market number.", ""]
    r = result["reference"]
    lines += [f"Noise floor, all train rows against the test truth: average {r['noise_floor_average_pp']} pp, by item {r['noise_floor_by_item_pp']}.", f"All 632 of the pool, direct: {r['pool_all_rows_direct']}", f"All 632 of the pool, shrunk: {r['pool_all_rows_shrunk']}", f"Real answers of the 1000 test panel: {r['test_panel_real_answers']}", f"Scored: {result['scored']}", ""]
    primary = label(PRIMARY_MODEL, PRIMARY_CONDITION)
    block = f"{PRIMARY_N}|row"
    if block in result["calibration"] and f"{primary}|E4" in result["calibration"][block]["estimators"]:
        e = result["calibration"][block]["estimators"]
        c = result["calibration"][f"{PRIMARY_N}|cluster"]["estimators"]
        o = result["calibration"][block]["estimators_outside_panel_truth"]
        lines += ["## Primary: Terra C2, n=200 against E2", "", "| item | E2 row | E4 row | E5 row | E6 row | E2 cluster | E4 cluster | E5 cluster | E6 cluster |", "|---|---|---|---|---|---|---|---|---|"]
        for t in [*items, AVERAGE]:
            lines.append(f"| {t} | {e['E2'][t]['cell_mae']:.2f} | " + " | ".join(fmt_diff(e[f"{primary}|{n}"][t]) for n in ("E4", "E5", "E6")) + f" | {c['E2'][t]['cell_mae']:.2f} | " + " | ".join(fmt_diff(c[f"{primary}|{n}"][t]) for n in ("E4", "E5", "E6")) + " |")
        lines += ["", "### Sensitivity, not in the rule: truth from test respondents outside the panel, row draws. This truth is smaller and noisier, so E2 moves too", "", "| item | E2 | E4 | E5 | E6 |", "|---|---|---|---|---|"]
        for t in [*items, AVERAGE]:
            lines.append(f"| {t} | {o['E2'][t]['cell_mae']:.2f} | " + " | ".join(fmt_diff(o[f"{primary}|{n}"][t]) for n in ("E4", "E5", "E6")) + " |")
        lines.append("")
    lines += ["## Reference, not in the rule: calibrated panel minus R1 at n=200", "", "R1 uses the same n real respondents and no panel: logistic on age band order and sex. Negative means the panel adds something beyond that.", "", "| item | draw | model | cond | R1 | E4 minus R1 | E5 minus R1 | E6 minus R1 |", "|---|---|---|---|---|---|---|---|"]
    for t in [*items, AVERAGE]:
        for kind in ("row", "cluster"):
            b = result["calibration"].get(f"{PRIMARY_N}|{kind}")
            if b is None:
                continue
            for key in sorted(result["scored"]):
                model, cond = key.split("|")
                parts = [b["difference_to_R1"][f"{key}|{n}"][t] for n in ("E4", "E5", "E6")]
                lines.append(f"| {t} | {kind} | {model} | {cond} | {b['estimators']['R1'][t]['cell_mae']:.2f} | " + " | ".join(f"{v['mean_diff']:+.2f} {fmt_ci(v['ci95'])}" for v in parts) + " |")
    lines += ["", "## Calibration study", ""] + calibration_tables(result, items) + [""]
    lines += ["## E5 fit, n=200 row draws", "", "| model | cond | item | offset mean | a mean | b mean | b 95 percent | fallbacks |", "|---|---|---|---|---|---|---|---|"]
    diag = result["calibration"][block]["fit_diagnostics"] if block in result["calibration"] else {}
    for key in sorted(diag):
        model, cond = key.split("|")
        for t, v in diag[key].items():
            lines.append(f"| {model} | {cond} | {t} | {v['offset_mean']} | {v['a_mean']} | {v['b_mean']} | {v['b_ci95']} | {v['e5_fallbacks']} |")
    lines += ["", "## Person level on the test panel", "", "| item | positives | model | cond | AUC | floor | diff | diff 95 percent | p | Holm p | Holm reject | within-unit AUC | floor within-unit | usable units |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in items:
        b = result["person_level"][t]
        for key in sorted(b["by_panel"]):
            v = b["by_panel"][key]
            model, cond = key.split("|")
            lines.append(f"| {t} | {b['positives']} | {model} | {cond} | {v['auc']} | {b['floor_auc']} | {v['auc_minus_floor']:+.4f} | {v['diff_ci95']} | {v['p_two_sided']} | {v.get('holm_p', '')} | {v.get('holm_reject_at_0_05', '')} | {v['within_unit_auc']} | {b['floor_within_unit_auc']} | {v['within_unit_usable_units']} |")
    lines += ["", "## Stereotypes and level", "", "| item | model | cond | gender gap panel | gender gap real | panel minus real | age slope panel | age slope real | panel minus real | bias pp | underdisp | cell r |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in items:
        s = result["stereotypes"][t]
        for key in sorted(s["by_panel"]):
            v = s["by_panel"][key]
            model, cond = key.split("|")
            lines.append(f"| {t} | {model} | {cond} | {v['gender_gap_pp']:+.2f} {fmt_ci(v['gender_gap_ci95'])} | {s['real_gender_gap_pp']:+.2f} {fmt_ci(s['real_gender_gap_ci95'])} | {fmt_ci(v['gap_minus_real_ci95'])} | {v['age_slope_pp_per_band']:+.2f} {fmt_ci(v['age_slope_ci95'])} | {s['real_age_slope_pp_per_band']:+.2f} {fmt_ci(s['real_age_slope_ci95'])} | {fmt_ci(v['slope_minus_real_ci95'])} | {v['bias_pp']:+.2f} | {v['underdispersion_ratio']} | {v['cell_pearson_r']} |")
    lines += ["", "## Stability, Terra C2, 3 extra repeats", ""]
    if result["stability"] is None:
        lines.append("Not complete.")
    else:
        lines += ["| item | respondents | answers each | pairs | mean abs diff pp | worst pair pp | rank corr mean | rank corr min | within-person SD pp | between-person SD pp |", "|---|---|---|---|---|---|---|---|---|---|"]
        for t in items:
            v = result["stability"][t]
            lines.append(f"| {t} | {v['respondents']} | {v['answers_each']} | {v['pairs']} | {v['mean_abs_diff_pp']} | {v['max_pair_mean_abs_diff_pp']} | {v['rank_correlation_mean']} | {v['rank_correlation_min']} | {v['within_person_sd_pp']} | {v['between_person_sd_pp']} |")
    lines += ["", "## Trust map, frozen rule", "", "A raw panel number is never shown as a market number.", "", "| item | model | cond | verdict | winning estimators | age slope ok | cell r ok | underdisp ok | level trusted |", "|---|---|---|---|---|---|---|---|---|"]
    for v in result["trust_map"]:
        c = v["direction_checks"]
        lines.append(f"| {v['item']} | {v['model']} | {v['condition']} | {v['verdict']} | {','.join(v['winning_estimators']) or '-'} | {c['age_slope_ok']} | {c['cell_r_ok']} | {c['underdispersion_ok']} | {v['level_trusted']} |")
    return "\n".join(lines) + "\n"
