"""Rule v3 on stored answers and on controls. No API call anywhere in this file. Aggregates only reach results/verdict_v3.

  python src/verdict_v3_run.py acceptance   controls first: real answers in the 4 slots, the stand-in panel, seed sensitivity
  python src/verdict_v3_run.py apply        v1, v2, v3 side by side on the LLM answers. Runs only after acceptance has been written
  python src/verdict_v3_run.py ceiling      can a panel or an estimator holding the truth meet the v2 first branch and the frozen ranking rule?

The order is the point: the acceptance result exists on disk before any v3 label for an LLM answer does.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import main_run  # noqa: E402
import stage3_run  # noqa: E402
from lotte_audit import data, main_score, metrics, option_ranking as rank, paths, splits, verdict_study, verdict_v2, verdict_v3  # noqa: E402

RESULTS = paths.RESULTS / "verdict_v3"
ACCEPT_FILE = RESULTS / "acceptance.json"
OUT_JSON = RESULTS / "verdict_v3.json"
OUT_MD = RESULTS / "verdict_v3.md"
CEILING_FILE = RESULTS / "ceiling.json"
ALT_PLANS = {"alt_seed_99": {"seed": 99, "pi_seed": 4321}, "alt_seed_20261102": {"seed": 20261102, "pi_seed": 777}}
ITEMS = ("ever", "weekly", "carb")


def setup():
    main_key = main_run.load_key()
    prereg = json.loads(stage3_run.PREREG.read_text(encoding="utf-8"))
    plan = prereg["part1_verdict"]["plan"]
    df, _ = data.load_sav()
    baseline_doc = json.loads((paths.RESULTS / "baselines.json").read_text(encoding="utf-8"))
    ctx = main_score.build_context(df, main_key, baseline_doc)
    targets = data.derive_targets(df)
    train = splits.masks(splits.load_manifest(df))["train"]
    test_rows = main_key.loc[(main_key.split == "test") & (main_key.condition == "C1")].sort_values("row_index")["row_index"].to_numpy()
    pool_rows = main_key.loc[(main_key.split == "calibration") & (main_key.condition == "C1")].sort_values("row_index")["row_index"].to_numpy()
    return {"df": df, "ctx": ctx, "plan": plan, "targets": targets, "train": train, "test_rows": test_rows, "pool_rows": pool_rows, "main_key": main_key}


def real_answer_slots(s):
    """Each respondent's real answer as the panel's answer, in each of the 4 model and condition slots. No panel is this good; it is the ceiling.

    Nothing about a slot changes these answers, so the 4 slots give the same numbers by construction.
    """
    ctx, targets = s["ctx"], s["targets"]
    sets = {
        "test": {t: ctx["panel"]["y"][t].copy() for t in ctx["items"]},
        "calibration": {t: targets[t].to_numpy().astype(float)[s["pool_rows"]] for t in ctx["items"]},
    }
    return {slot: sets for slot in verdict_v3.ACCEPTANCE["slots"]}


def distorted_real_slots(s, rng_seed=5):
    """Sensitivity: real answers pushed through each slot's stand-in shift and noise, so the slots differ. Same shifts as the stand-in panel."""
    from lotte_audit import calibration as cal

    ctx, targets = s["ctx"], s["targets"]
    rng = np.random.default_rng(rng_seed)
    out = {}
    for slot, (shift, noise) in zip(verdict_v3.ACCEPTANCE["slots"], ((1.2, 0.3), (1.2, 0.3), (0.8, 0.5), (0.8, 0.5))):
        sets = {"test": {}, "calibration": {}}
        for t in ctx["items"]:
            y_test = ctx["panel"]["y"][t]
            y_pool = targets[t].to_numpy().astype(float)[s["pool_rows"]]
            # A strong signal of the real answer, shifted and noised the way the stand-in slots are.
            sets["test"][t] = cal.expit(3.0 * (2 * y_test - 1) + shift + rng.normal(0, noise, len(y_test)))
            sets["calibration"][t] = cal.expit(3.0 * (2 * y_pool - 1) + shift + rng.normal(0, noise, len(y_pool)))
        out[slot] = sets
    return out


def surrogate_slots(s):
    return verdict_study.surrogate_answers(s["df"], s["targets"], s["train"], s["test_rows"], s["pool_rows"])


def study(s, answers, plan):
    doc = verdict_study.study_answers(s["ctx"], answers, plan)
    doc["rows"] = verdict_v3.apply_rows(doc["rows"])
    doc["counts_v3"] = verdict_v3.count_labels(doc["rows"])
    return doc


def slim(rows):
    """The fields a reader needs per row. Aggregates only."""
    out = []
    for r in rows:
        i = r["v2_inputs"]
        out.append({
            "item": r["item"],
            "model": r["model"],
            "condition": r["condition"],
            "v1": r["v1"]["verdict"],
            "v2": r["v2"]["verdict"],
            "v3": r["v3"]["verdict"],
            "v3_estimators_beating_r1": r["v3"]["estimators_beating_r1"],
            "gender_gap_use_banned": r["v3"]["gender_gap_use_banned"],
            "real_slope_includes_zero": r["v3"]["real_slope_interval_includes_zero"],
            "direction_checks": r["v3"]["direction_checks"],
            "row_vs_r1": i["vs_r1_row"],
            "cluster_vs_r1": i["vs_r1_cluster"],
            "panel_age_slope": i["panel_age_slope"],
            "real_age_slope_ci95": i["real_age_slope_ci95"],
            "cell_pearson_r": i["cell_pearson_r"],
            "underdispersion_ratio": i["underdispersion_ratio"],
            "gap_minus_real_ci95": i["gap_minus_real_ci95"],
        })
    return out


def panel_mass(ctx):
    """Share of the test truth's psfwt that belongs to the panel's own respondents, overall and per cell."""
    w = ctx["test"]["w"]
    cells = ctx["test"]["cells"]
    pos = ctx["panel"]["positions_in_test"]
    in_panel = np.zeros(len(w), dtype=bool)
    in_panel[pos] = True
    per_cell = [float(w[in_panel & (cells == c)].sum() / w[cells == c].sum()) for c in np.unique(cells)]
    return {"panel_share_of_test_psfwt": round(float(w[in_panel].sum() / w.sum()), 4), "cell_min": round(min(per_cell), 4), "cell_max": round(max(per_cell), 4), "panel_rows": int(in_panel.sum()), "test_rows": int(len(w)), "outside_rows": int((~in_panel).sum())}


def cmd_acceptance(_args):
    s = setup()
    plan = s["plan"]
    real = study(s, real_answer_slots(s), plan)
    surrogate = study(s, surrogate_slots(s), plan)
    verdict = verdict_v3.acceptance(real["rows"], surrogate["rows"])
    stored = json.loads((paths.RESULTS / "stage3" / "verdict_v2.json").read_text(encoding="utf-8"))
    stored_labels = [(r["item"], r["model"], r["condition"], r["v2"]["verdict"]) for r in stored["surrogate"]["rows"]]
    surrogate_reproduced = stored_labels == [(r["item"], r["model"], r["condition"], r["v2"]["verdict"]) for r in surrogate["rows"]]
    sensitivity = {}
    for name, change in ALT_PLANS.items():
        alt = {**plan, **change}
        real_alt = study(s, real_answer_slots(s), alt)
        sur_alt = study(s, surrogate_slots(s), alt)
        check = verdict_v3.acceptance(real_alt["rows"], sur_alt["rows"])
        sensitivity[name] = {"plan": alt, "real_answers_calibrated": check["real_answers_per_slot"][verdict_v3.ACCEPTANCE["slots"][0]]["calibrated"], "surrogate_rows_calibrated": check["surrogate_rows_calibrated"], "passed": check["passed"], "real_v3_e4": {r["item"]: {"row": r["row_vs_r1"]["E4"], "cluster": r["cluster_vs_r1"]["E4"]} for r in slim(real_alt["rows"])[:3]}}
    distorted = study(s, distorted_real_slots(s), plan)
    doc = {
        "written_after_answers": "Rule v3 and this bar were written after the stage 2 answers, v2 and an outside real answer check were all seen. Not pre-registered.",
        "rule_version": verdict_v3.RULE_VERSION,
        "acceptance": verdict,
        "plan": plan,
        "real_answers": {"note": "Each respondent's real answer stands in as the panel's answer in every slot. The 4 slots are identical by construction, so they are one result shown 4 times. Not a claim about any LLM.", "rows": slim(real["rows"]), "counts_v1": real["counts_v1"], "counts_v2": real["counts_v2"], "counts_v3": real["counts_v3"]},
        "surrogate": {"note": "Train split age and sex logistic plus a shift and noise, rng seed 1. It holds no LLM answer and no information beyond age and sex.", "rows": slim(surrogate["rows"]), "counts_v1": surrogate["counts_v1"], "counts_v2": surrogate["counts_v2"], "counts_v3": surrogate["counts_v3"], "v2_labels_reproduce_stored": surrogate_reproduced},
        "seed_sensitivity": sensitivity,
        "distorted_real_answers_sensitivity": {"note": "Real answers at logit strength 3 with each slot's stand-in shift and noise, so the slots differ. Not part of the bar.", "rows": slim(distorted["rows"]), "counts_v3": distorted["counts_v3"]},
        "panel_mass": panel_mass(s["ctx"]),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    ACCEPT_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"acceptance": verdict, "seed_sensitivity": {k: {x: v[x] for x in ("real_answers_calibrated", "surrogate_rows_calibrated", "passed")} for k, v in sensitivity.items()}, "distorted_counts": distorted["counts_v3"], "surrogate_v2_reproduced": surrogate_reproduced, "panel_mass": doc["panel_mass"]}, ensure_ascii=False, indent=1))


def llm_answers(s):
    cfg_main, template = main_run.load_config()
    personas = main_run.load_personas()
    answers = {}
    for stage in cfg_main["run_order"]:
        got = main_run.load_answer_arrays(stage["model"], stage["condition"], s["main_key"], personas, template)
        if got is None:
            raise SystemExit(f"stage 2 answers missing for {stage}")
        answers[main_score.label(stage["model"], stage["condition"])] = got
    return answers


def table(rows, gap_col=True):
    head = "| item | model | cond | v1 | v2 | v3 | v3 estimators | " + verdict_v3.GENDER_GAP_BAN + " | E4-R1 row | E4-R1 cluster mean |"
    lines = [head, "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        e4r, e4c = r["row_vs_r1"]["E4"], r["cluster_vs_r1"]["E4"]
        lines.append(f"| {r['item']} | {r['model']} | {r['condition']} | {r['v1']} | {r['v2']} | {r['v3']} | {','.join(r['v3_estimators_beating_r1']) or '-'} | {r['gender_gap_use_banned']} | {e4r['mean_diff']:+.2f} [{e4r['ci95'][0]:+.2f},{e4r['ci95'][1]:+.2f}] | {e4c['mean_diff']:+.2f} |")
    return lines


def to_markdown(doc):
    a = doc["acceptance"]
    lines = [
        "# Trust map v1, v2, v3 side by side",
        "",
        "**v3 was written after the answers were seen. It is not pre-registered.** v1 and v2 are unchanged. A raw panel number is never a market number under any label.",
        "",
        f"## Acceptance: {'PASSED' if a['passed'] else 'FAILED'}",
        "",
        f"Bar: the real answer control must obtain {verdict_v3.CALIBRATED} on at least {a['bar']['real_answers_min_items_per_slot']} of {a['bar']['items_per_slot']} items in each of the 4 slots, and the non-LLM stand-in panel on at most {a['bar']['surrogate_max_of_12']} of 12.",
        "",
        f"Real answer control per slot: {json.dumps(a['real_answers_per_slot'], ensure_ascii=False)}. The 4 slots hold the same answers, so this is one result shown 4 times.",
        f"Stand-in panel rows with {verdict_v3.CALIBRATED}: {a['surrogate_rows_calibrated'] or 'none'}.",
        "",
        doc["reading"],
        "",
        "## LLM answers, stage 2",
        "",
        f"Counts: v1 {doc['llm']['counts_v1']}, v2 {doc['llm']['counts_v2']}, v3 {doc['llm']['counts_v3']}. {verdict_v3.GENDER_GAP_BAN}: {doc['llm']['gender_ban_count']} of 12 at the stage 2 seed, {doc['llm']['gender_ban_by_seed']} across seeds.",
        "",
        *table(doc["llm"]["rows"]),
        "",
        "## Real answer control",
        "",
        doc["real_answers"]["note"],
        "",
        f"Counts: v1 {doc['real_answers']['counts_v1']}, v2 {doc['real_answers']['counts_v2']}, v3 {doc['real_answers']['counts_v3']}.",
        "",
        *table(doc["real_answers"]["rows"][:3]),
        "",
        "## Non-LLM stand-in panel",
        "",
        doc["surrogate"]["note"],
        "",
        f"Counts: v1 {doc['surrogate']['counts_v1']}, v2 {doc['surrogate']['counts_v2']}, v3 {doc['surrogate']['counts_v3']}.",
        "",
        *table(doc["surrogate"]["rows"]),
        "",
        "## Seed sensitivity",
        "",
        "```",
        json.dumps({k: {x: v[x] for x in ("real_answers_calibrated", "surrogate_rows_calibrated", "passed")} for k, v in doc["seed_sensitivity"].items()}, ensure_ascii=False, indent=1),
        "```",
        "",
        "LLM labels across seeds:",
        "",
        "```",
        json.dumps(doc["llm"]["labels_by_seed"], ensure_ascii=False, indent=1),
        "```",
        "",
        f"Gender flag rows that change with the seed: {doc['llm']['gender_flag_rows_that_move'] or 'none'}.",
        "",
        "## Limits",
        "",
        "- Intervals are across 200 draws with the pool and the test panel held fixed. No correction across 12 combinations and 3 estimators.",
        f"- The panel holds {doc['panel_mass']['panel_share_of_test_psfwt']} of the test split's psfwt. All R1 comparisons here use the truth from the other {doc['panel_mass']['outside_rows']} test rows only.",
        "- The first branch now takes a row interval and a cluster mean. The cluster interval still includes zero for the real answer control, so the branch is weaker than v2's on purpose.",
    ]
    return "\n".join(lines) + "\n"


def cmd_apply(_args):
    if not ACCEPT_FILE.exists():
        raise SystemExit("run acceptance first: its result must exist before any v3 label for an LLM answer")
    accepted = json.loads(ACCEPT_FILE.read_text(encoding="utf-8"))
    s = setup()
    plan = s["plan"]
    answers = llm_answers(s)
    llm = study(s, answers, plan)
    rows = slim(llm["rows"])
    stored = json.loads((paths.RESULTS / "stage3" / "verdict_v2.json").read_text(encoding="utf-8"))["answers"]["rows"]
    mismatch = [r["item"] for r, x in zip(rows, stored) if r["v2"] != x["v2"]["verdict"]]
    labels_by_seed = {"stage2_seed": {f"{r['model']}|{r['condition']}|{r['item']}": r["v3"] for r in rows}}
    gender_by_seed = {"stage2_seed": {f"{r['model']}|{r['condition']}|{r['item']}": r["gender_gap_use_banned"] for r in rows}}
    for name, change in ALT_PLANS.items():
        alt = slim(study(s, answers, {**plan, **change})["rows"])
        labels_by_seed[name] = {f"{r['model']}|{r['condition']}|{r['item']}": r["v3"] for r in alt}
        gender_by_seed[name] = {f"{r['model']}|{r['condition']}|{r['item']}": r["gender_gap_use_banned"] for r in alt}
    moved = sorted(k for k in gender_by_seed["stage2_seed"] if len({gender_by_seed[n][k] for n in gender_by_seed}) > 1)
    passed = accepted["acceptance"]["passed"]
    reading = (
        f"The bar was met. This shows the first branch can fire for a panel holding the real answers and not for a stand-in panel on age and sex at these seeds. The rule was still written after the answers, so a label here is a reading of data already seen."
        if passed
        else "The bar was NOT met. **These labels must not be used as product labels.** The rule is not tuned further."
    )
    doc = {
        "written_after_answers": accepted["written_after_answers"],
        "rule_version": verdict_v3.RULE_VERSION,
        "product_labels_allowed": False,
        "product_labels_note": "Written after the answers. Even with the bar met, no v3 label is a validated product label." if passed else "Acceptance failed. The labels must not be used as product labels.",
        "acceptance": accepted["acceptance"],
        "reading": reading,
        "llm": {"rows": rows, "counts_v1": llm["counts_v1"], "counts_v2": llm["counts_v2"], "counts_v3": llm["counts_v3"], "gender_ban_count": sum(r["gender_gap_use_banned"] for r in rows), "gender_ban_by_seed": {n: sum(v.values()) for n, v in gender_by_seed.items()}, "gender_flag_rows_that_move": moved, "labels_by_seed": labels_by_seed, "v2_labels_mismatch_stored": mismatch},
        "real_answers": accepted["real_answers"],
        "surrogate": accepted["surrogate"],
        "seed_sensitivity": accepted["seed_sensitivity"],
        "distorted_real_answers_sensitivity": accepted["distorted_real_answers_sensitivity"],
        "panel_mass": accepted["panel_mass"],
    }
    OUT_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    text = to_markdown(doc)
    OUT_MD.write_text(text, encoding="utf-8")
    print(text)


def cmd_ceiling(_args):
    """v2 on the real answer control is in acceptance.json. This adds the frozen ranking rule: an estimate equal to the truth against KREI 2024 and direct draws."""
    prereg = json.loads(stage3_run.PREREG.read_text(encoding="utf-8"))
    plan = prereg["part2_ranking"]["plan"]
    df, _ = data.load_sav()
    ctx = stage3_run.build_ranking_context(df, stage3_run.load_2024(), main_run.load_key(), stage3_run.load_key())
    truth, pool = ctx["truth"], ctx["pool"]
    cats = rank.OPTION_SETS[rank.PRIMARY_SET]
    truth_m = rank.one_hot(truth["options"])
    uniq = np.unique(truth["units"])
    index = {u: i for i, u in enumerate(uniq.tolist())}
    table_truth = rank.UnitTable(truth_m, truth["w"], truth["ages"], np.array([index[u] for u in truth["units"].tolist()]), len(uniq))
    direct, _ = rank.direct_draws(pool, "row", plan["draws"], [plan["seed"], 200, 0], plan["pi_draws"], plan["pi_seed"])
    rng = np.random.default_rng([plan["seed"], 3])
    picks = rng.integers(0, len(uniq), size=(plan["bootstrap"], len(uniq)))
    keys = [f"true_gap|{n}|accuracy" for n, _, _ in rank.GAP_BANDS]
    store = {"krei_2024": [], "direct_row": []}
    for r in range(plan["bootstrap"]):
        counts = np.bincount(picks[r], minlength=len(uniq)).astype(float)
        t = table_truth.shares(counts, "overall")
        ts = rank.collapse(t, cats)
        perfect = rank.metrics_one(ts, ts, cats)
        krei = rank.metrics_one(rank.collapse(ctx["krei_2024"]["overall"], cats), ts, cats)
        dr = rank.metrics_one(rank.collapse(direct["overall"][r % plan["draws"]], cats), ts, cats)
        store["krei_2024"].append([perfect[k] - krei[k] for k in keys])
        store["direct_row"].append([perfect[k] - dr[k] for k in keys])
    bands = {}
    for other, values in store.items():
        arr = np.array(values, dtype=float)
        bands[other] = {}
        for j, key in enumerate(keys):
            ok = arr[:, j][np.isfinite(arr[:, j])]
            lo, hi = np.percentile(ok, [2.5, 97.5])
            bands[other][key.split("|")[1]] = {"mean_diff": round(float(ok.mean()), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)], "beats": bool(lo > 0)}
    accepted = json.loads(ACCEPT_FILE.read_text(encoding="utf-8")) if ACCEPT_FILE.exists() else None
    doc = {
        "what": "Estimate equal to the truth in each resample, against the comparators of the frozen ranking rule on the primary option set, overall. beats follows option_ranking.operating_rule: interval lower limit above zero.",
        "ranking_perfect_estimator": bands,
        "reading": "An estimate equal to the truth cannot have its lower limit above zero in every band, so the frozen rule's beats_ flags cannot tell a panel apart. Use the paired differences of the whole pair accuracy instead.",
        "any_band_all_beaten": {other: all(v["beats"] for v in b.values()) for other, b in bands.items()},
        "v2_on_real_answers": None if not accepted else {"labels": {r["item"]: r["v2"] for r in accepted["real_answers"]["rows"][:3]}, "counts_v2": accepted["real_answers"]["counts_v2"], "note": "Real answers in the panel slot. v2 gives no calibrated label to any item, and carb gets real only because the real slope interval includes zero."},
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    CEILING_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in (("acceptance", cmd_acceptance), ("apply", cmd_apply), ("ceiling", cmd_ceiling)):
        sub.add_parser(name).set_defaults(func=fn)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
