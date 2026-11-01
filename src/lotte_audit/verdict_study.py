"""Inputs and output of the v1 and v2 trust maps side by side. No API calls. Aggregates only.

Works on a main_score context, so stored stage 2 answers, a stand-in panel and synthetic answers all take the same path.
Draws are the stage 2 draws: main_score.calibration_study with the same n, kinds and seeds.
"""
import numpy as np

from . import baselines, calibration as cal, main_score, metrics, verdict, verdict_v2

PRIMARY_N = 200
KINDS = ("row", "cluster")
ESTIMATORS = verdict.CALIBRATED_ESTIMATORS


def outside_mask(ctx):
    mask = np.ones(len(ctx["test"]["w"]), dtype=bool)
    mask[ctx["panel"]["positions_in_test"]] = False
    return mask


def outside_diagnostics(ctx, answers, reps, seed):
    """Stereotype inputs of v2, with the real side taken only from test respondents outside the panel.

    Survey unit bootstrap over the test split units, same seed scheme as main_score.stereotypes. Each resample gives
    the panel value, the real value on outside rows in those units, and their difference.
    """
    test, panel, m = ctx["test"], ctx["panel"], ctx["m"]
    keep = outside_mask(ctx)
    o = {"w": test["w"][keep], "units": test["units"][keep], "ages": test["ages"][keep], "sexes": test["sexes"][keep], "y": {t: test["y"][t][keep] for t in ctx["items"]}}
    uniq = np.unique(test["units"])
    pos = {u: i for i, u in enumerate(uniq.tolist())}
    outside_groups = [[] for _ in uniq]
    for i, u in enumerate(o["units"].tolist()):
        outside_groups[pos[u]].append(i)
    panel_groups = [[] for _ in uniq]
    for i, u in enumerate(panel["units"].tolist()):
        panel_groups[pos[u]].append(i)
    outside_groups = [np.array(g, dtype=int) for g in outside_groups]
    panel_groups = [np.array(g, dtype=int) for g in panel_groups]
    rng = np.random.default_rng([seed, 7])
    picks = rng.integers(0, len(uniq), size=(reps, len(uniq)))
    boot = {t: {"real_gap": [], "real_slope": [], "panel": {k: {"gap": []} for k in answers}} for t in ctx["items"]}
    for r in range(reps):
        i_o = np.concatenate([outside_groups[g] for g in picks[r]])
        i_p = np.concatenate([panel_groups[g] for g in picks[r]])
        for t in ctx["items"]:
            yo = o["y"][t][i_o]
            boot[t]["real_gap"].append(metrics.gender_gap(yo, o["w"][i_o], o["sexes"][i_o]))
            boot[t]["real_slope"].append(metrics.age_slope(yo, o["w"][i_o], o["ages"][i_o]))
            for key, sets in answers.items():
                boot[t]["panel"][key]["gap"].append(metrics.gender_gap(sets["test"][t][i_p], panel["w"][i_p], panel["sexes"][i_p]))
    out = {}
    for t in ctx["items"]:
        truth_map = {i: float(v) for i, v in enumerate(ctx["truth_outside_panel"][t])}
        rg = np.array(boot[t]["real_gap"], dtype=float)
        block = {
            "real_gender_gap_pp": round(metrics.gender_gap(o["y"][t], o["w"], o["sexes"]), 3),
            "real_gender_gap_ci95": main_score.percentile_ci(rg),
            "real_age_slope_pp_per_band": round(metrics.age_slope(o["y"][t], o["w"], o["ages"]), 3),
            "real_age_slope_ci95": main_score.percentile_ci(np.array(boot[t]["real_slope"], dtype=float)),
            "by_panel": {},
        }
        for key, sets in answers.items():
            p = sets["test"][t]
            est = metrics.cell_means(p, panel["w"], panel["cells"], list(range(m)))
            pg = np.array(boot[t]["panel"][key]["gap"], dtype=float)
            block["by_panel"][key] = {
                "gender_gap_pp": round(metrics.gender_gap(p, panel["w"], panel["sexes"]), 3),
                "gap_minus_real_ci95": main_score.percentile_ci(pg - rg),
                "age_slope_pp_per_band": round(metrics.age_slope(p, panel["w"], panel["ages"]), 3),
                "underdispersion_ratio": round(metrics.underdispersion(est, truth_map), 3),
                "cell_pearson_r": round(metrics.cell_pearson(est, truth_map), 3),
            }
        out[t] = block
    return out


def comparisons(study, answers, items):
    """Paired differences at n=200: to R1 and to E2, on the whole test truth and on the truth outside the panel."""
    out = {}
    for kind in KINDS:
        run = study[(PRIMARY_N, kind)]
        block = {}
        for key in answers:
            for e in ESTIMATORS:
                name = f"{key}|{e}"
                block[name] = {}
                for t in items:
                    block[name][t] = {
                        "vs_r1_outside": cal.difference_summary(run["mae_outside"][name][t], run["mae_outside"]["R1"][t]),
                        "vs_r1_whole": cal.difference_summary(run["mae"][name][t], run["mae"]["R1"][t]),
                        "vs_e2_whole": cal.difference_summary(run["mae"][name][t], run["mae"]["E2"][t]),
                    }
        out[kind] = block
    return out


def trust_maps(ctx, answers, comps, stereo_whole, diag_outside):
    """One row per item, model, condition: v1 unchanged next to v2 on the outside truth, plus a whole-truth v2 sensitivity."""
    rows = []
    for key in answers:
        model, cond = key.split("|")
        for t in ctx["items"]:
            pick = lambda kind, field: {e: comps[kind][f"{key}|{e}"][t][field] for e in ESTIMATORS}  # noqa: E731
            sw = stereo_whole[t]
            pw = sw["by_panel"][key]
            v1_out = verdict.item_verdict(pick("row", "vs_e2_whole"), pick("cluster", "vs_e2_whole"), pw["age_slope_pp_per_band"], sw["real_age_slope_ci95"], pw["cell_pearson_r"], pw["underdispersion_ratio"])
            so = diag_outside[t]
            po = so["by_panel"][key]
            v2_out = verdict_v2.item_verdict(pick("row", "vs_r1_outside"), pick("cluster", "vs_r1_outside"), pick("row", "vs_e2_whole"), pick("cluster", "vs_e2_whole"), po["age_slope_pp_per_band"], so["real_age_slope_ci95"], po["cell_pearson_r"], po["underdispersion_ratio"], po["gap_minus_real_ci95"])
            whole = verdict_v2.item_verdict(pick("row", "vs_r1_whole"), pick("cluster", "vs_r1_whole"), pick("row", "vs_e2_whole"), pick("cluster", "vs_e2_whole"), pw["age_slope_pp_per_band"], sw["real_age_slope_ci95"], pw["cell_pearson_r"], pw["underdispersion_ratio"], pw["gap_minus_real_ci95"])
            rows.append(
                {
                    "item": t,
                    "model": model,
                    "condition": cond,
                    "v1": verdict_v2.v1_view(v1_out),
                    "v2": v2_out,
                    "v2_inputs": {
                        "vs_r1_row": pick("row", "vs_r1_outside"),
                        "vs_r1_cluster": pick("cluster", "vs_r1_outside"),
                        "panel_age_slope": po["age_slope_pp_per_band"],
                        "real_age_slope_ci95": so["real_age_slope_ci95"],
                        "cell_pearson_r": po["cell_pearson_r"],
                        "underdispersion_ratio": po["underdispersion_ratio"],
                        "panel_gender_gap_pp": po["gender_gap_pp"],
                        "real_gender_gap_pp": so["real_gender_gap_pp"],
                        "gap_minus_real_ci95": po["gap_minus_real_ci95"],
                    },
                    "sensitivity_v2_on_whole_test_truth": {k: whole[k] for k in ("verdict", "estimators_beating_r1", "gender_gap_use_banned")},
                }
            )
    return rows


def count_labels(rows, version):
    out = {}
    for row in rows:
        label = row[version]["verdict"]
        out[label] = out.get(label, 0) + 1
    return out


def study_answers(ctx, answers, plan):
    """Run the n=200 study and both diagnostics for one answer set. Returns the side-by-side rows and the raw comparisons."""
    study = main_score.calibration_study(ctx, answers, [PRIMARY_N], list(KINDS), plan["repeats"], plan["seed"], plan["pi_draws"], plan["pi_seed"])
    comps = comparisons(study, answers, ctx["items"])
    stereo_whole = main_score.stereotypes(ctx, answers, plan["bootstrap"], plan["seed"])
    diag = outside_diagnostics(ctx, answers, plan["bootstrap"], plan["seed"])
    rows = trust_maps(ctx, answers, comps, stereo_whole, diag)
    return {
        "rows": rows,
        "counts_v1": count_labels(rows, "v1"),
        "counts_v2": count_labels(rows, "v2"),
        "gender_gap_ban_count": sum(r["v2"]["gender_gap_use_banned"] for r in rows),
        "labels_changed_if_v2_read_whole_test_truth": sum(r["v2"]["verdict"] != r["sensitivity_v2_on_whole_test_truth"]["verdict"] for r in rows),
    }


# ---------- stand-in panels. No LLM. They use real data from this file only, never an API. ----------


def surrogate_answers(df, targets, train_mask, test_rows, pool_rows):
    """The stage 2 stand-in panel, unchanged: train split age and sex logistic plus a shift and noise, rng seed 1."""
    models = baselines.fit_reference_models(df, targets, train_mask)
    rng = np.random.default_rng(1)

    def fake(shift, noise):
        out = {"test": {}, "calibration": {}}
        for t in targets.columns:
            (fm, fc), fcols = models[t]["floor"]
            for name, rows in (("test", test_rows), ("calibration", pool_rows)):
                base_p = baselines.predict_logistic(fm, fc, df.iloc[rows], fcols)
                out[name][t] = cal.expit(cal.logit(base_p) + shift + rng.normal(0, noise, len(rows)))
        return out

    return {"gpt-6.1-terra|C2": fake(1.2, 0.3), "gpt-6.1-terra|C1": fake(1.2, 0.3), "gpt-6-luna|C2": fake(0.8, 0.5), "gpt-6-luna|C1": fake(0.8, 0.5)}


def known_signal_answers(df, targets, train_mask, test_rows, pool_rows, strengths):
    """Positive control for the rule. The stand-in panel is told part of each real answer, so it holds signal beyond age and sex.

    Same base as the surrogate, plus strength*(2y-1) on the logit. Answers no one could have in practice; it only shows
    whether the first branch of v2 can fire at all, and how much person-level signal that takes.
    """
    models = baselines.fit_reference_models(df, targets, train_mask)
    rng = np.random.default_rng([1, 2])
    out = {}
    for s in strengths:
        sets = {"test": {}, "calibration": {}}
        for t in targets.columns:
            (fm, fc), fcols = models[t]["floor"]
            y = targets[t].to_numpy().astype(float)
            for name, rows in (("test", test_rows), ("calibration", pool_rows)):
                base_p = baselines.predict_logistic(fm, fc, df.iloc[rows], fcols)
                sets[name][t] = cal.expit(cal.logit(base_p) + 1.2 + s * (2 * y[rows] - 1) + rng.normal(0, 0.3, len(rows)))
        out[f"control_s{s}|C2"] = sets
    return out


# ---------- markdown ----------


def _ci(ci):
    return f"[{ci[0]:+.2f},{ci[1]:+.2f}]"


def side_by_side_table(rows):
    lines = ["| item | model | cond | v1 label | v1 beats_e2 | v2 label | v2 estimators beating R1 | " + verdict_v2.GENDER_GAP_BAN + " | slope ok | cell r ok | underdisp ok |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c = r["v2"]["direction_checks"]
        lines.append(f"| {r['item']} | {r['model']} | {r['condition']} | {r['v1']['verdict']} | {r['v1']['beats_e2']} | {r['v2']['verdict']} | {','.join(r['v2']['estimators_beating_r1']) or '-'} | {r['v2']['gender_gap_use_banned']} | {c['age_slope_ok']} | {c['cell_r_ok']} | {c['underdispersion_ok']} |")
    return lines


def inputs_table(rows):
    lines = ["| item | model | cond | E4-R1 row | E5-R1 row | E6-R1 row | E4-R1 cluster | E5-R1 cluster | E6-R1 cluster | panel slope | real slope CI | cell r | underdisp | gender gap panel | gender gap real | panel minus real |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        i = r["v2_inputs"]
        parts = [f"{i[k][e]['mean_diff']:+.2f} {_ci(i[k][e]['ci95'])}" for k in ("vs_r1_row", "vs_r1_cluster") for e in ESTIMATORS]
        lines.append(f"| {r['item']} | {r['model']} | {r['condition']} | " + " | ".join(parts) + f" | {i['panel_age_slope']:+.2f} | {_ci(i['real_age_slope_ci95'])} | {i['cell_pearson_r']} | {i['underdispersion_ratio']} | {i['panel_gender_gap_pp']:+.2f} | {i['real_gender_gap_pp']:+.2f} | {_ci(i['gap_minus_real_ci95'])} |")
    return lines


def to_markdown(doc):
    lines = [
        "# Trust map v1 and v2 side by side",
        "",
        "v1 is src/lotte_audit/verdict.py, unchanged. Its level_trusted field is shown as beats_e2: it only ever meant the estimator beat the shrunk cell mean E2.",
        "",
        "**v2 is not pre-registered with respect to the stage 2 answers.** It was written after they were seen, because v1 gave all 12 combinations one label and a non-LLM stand-in panel took 11 of 12. No correction across the 12 combinations and 3 estimators. Intervals are across 200 draws with the pool and the test panel held fixed; they do not carry the sampling uncertainty of those.",
        "",
        "v2 reads R1 and all real-side quantities on the truth from test respondents outside the 1000 panel, which is smaller and noisier than the whole test truth. A raw panel number is never a market number under any label.",
        "",
        "## Stage 2 answers",
        "",
        f"v1 counts: {doc['answers']['counts_v1']}. v2 counts: {doc['answers']['counts_v2']}. {verdict_v2.GENDER_GAP_BAN}: {doc['answers']['gender_gap_ban_count']} of {len(doc['answers']['rows'])}. Stored stage 2 v1 labels reproduced: {doc['v1_reproduced_from_main_score']}.",
        "",
        *side_by_side_table(doc["answers"]["rows"]),
        "",
        "### v2 inputs, truth outside the panel. Negative E-R1 means the estimator is better than R1",
        "",
        *inputs_table(doc["answers"]["rows"]),
        "",
        f"Sensitivity: labels that would differ if v2 read the whole test truth instead: {doc['answers']['labels_changed_if_v2_read_whole_test_truth']}.",
        "",
        "## Non-LLM stand-in panel, the stage 2 test",
        "",
        "Train split age and sex logistic plus a shift and noise, rng seed 1. It holds no LLM answer and no information beyond age and sex.",
        "",
        f"v1 counts: {doc['surrogate']['counts_v1']}. v2 counts: {doc['surrogate']['counts_v2']}. Stage 2 recorded 11 of 12 and 1 of 12 under v1.",
        "",
        *side_by_side_table(doc["surrogate"]["rows"]),
        "",
        "## Positive control: stand-in panels told part of each real answer",
        "",
        "Shows whether the first branch of v2 can fire at all. Not a claim about any LLM. AUC is on the 1000 test panel; Terra C2 for comparison is in results/main/main_score.md.",
        "",
        "| strength | item | AUC | v1 label | v2 label | v2 estimators beating R1 | E4-R1 row | E4-R1 cluster |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in doc["positive_control"]["rows"]:
        i = r["v2_inputs"]
        lines.append(f"| {r['model']} | {r['item']} | {doc['positive_control']['auc'][r['model']][r['item']]} | {r['v1']['verdict']} | {r['v2']['verdict']} | {','.join(r['v2']['estimators_beating_r1']) or '-'} | {i['vs_r1_row']['E4']['mean_diff']:+.2f} {_ci(i['vs_r1_row']['E4']['ci95'])} | {i['vs_r1_cluster']['E4']['mean_diff']:+.2f} {_ci(i['vs_r1_cluster']['E4']['ci95'])} |")
    return "\n".join(lines) + "\n"
