"""Stage 4 measures on stored answers. No API call anywhere in this file. Aggregates only reach results/stage4.

  python src/stage4_measures.py freeze       hash the plan and the measure code into manifests/frozen_stage4.json, then commit
  python src/stage4_measures.py check        frozen and committed, no computing
  python src/stage4_measures.py allocation   A1: does the panel help spend 200 people
  python src/stage4_measures.py flags        A2: can in-run signals name wrong cells before real data
  python src/stage4_measures.py duel         A3: the duel with no outside truth

Each compute command refuses when a frozen file changed or is uncommitted.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyreadstat

sys.path.insert(0, str(Path(__file__).resolve().parent))

import main_run  # noqa: E402
from lotte_audit import calibration as cal  # noqa: E402
from lotte_audit import data, main_score, paths, splits, stage4, verdict_study  # noqa: E402

PREREG = paths.CONFIG / "prereg_stage4.json"
FROZEN = paths.MANIFESTS / "frozen_stage4.json"
RESULTS = paths.RESULTS / "stage4"
FROZEN_FILES = (
    "config/prereg_stage4.json",
    "src/stage4_measures.py",
    "src/lotte_audit/stage4.py",
    "src/lotte_audit/duel.py",
    "src/lotte_audit/calibration.py",
    "src/lotte_audit/verdict_study.py",
    "src/lotte_audit/main_score.py",
)
TERRA, LUNA = "gpt-6.1-terra", "gpt-6-luna"
A1_PLAN = {"n": 200, "draws": 200, "seed": 42}
DRAWS = {"repeats": 200, "seed": 42, "pi_draws": 20000, "pi_seed": 43, "n": 200}
A2_PLAN = {"bootstrap": 2000, "permutations": 20000, "seed": 42, "top_k": 9}
A3_PLAN = {"resamples": 2000, "seed": 42, "fold_seed": [42, 5]}
BAR = {"surrogate_max_keep": 0.12, "positive_min_margin": 0.30}
POSITIVE = "control_s1.0"
STRENGTHS = (0.25, 0.5, 1.0, 2.0)
SURROGATES = ("surrogate_terra_slot", "surrogate_luna_slot")


def current_hashes():
    return {"files": {name: main_run.file_hash(name) for name in FROZEN_FILES}}


def check_frozen():
    expected = json.loads(FROZEN.read_text(encoding="utf-8"))
    now = current_hashes()
    changed = [k for k in expected["files"] if expected["files"][k] != now["files"].get(k)]
    if changed:
        raise SystemExit(f"frozen files changed since freeze: {changed}")


def require_committed():
    names = [*FROZEN_FILES, "manifests/frozen_stage4.json"]
    for name in names:
        if subprocess.run(["git", "-C", str(paths.ROOT), "ls-files", "--error-unmatch", name], capture_output=True).returncode != 0:
            raise SystemExit(f"{name} is not committed")
    if subprocess.run(["git", "-C", str(paths.ROOT), "diff", "--quiet", "HEAD", "--", *names]).returncode != 0:
        raise SystemExit("frozen files have uncommitted changes")


def guard():
    check_frozen()
    require_committed()


def setup():
    main_key = main_run.load_key()
    df, _ = data.load_sav()
    baseline_doc = json.loads((paths.RESULTS / "baselines.json").read_text(encoding="utf-8"))
    ctx = main_score.build_context(df, main_key, baseline_doc)
    targets = data.derive_targets(df)
    train = splits.masks(splits.load_manifest(df))["train"]
    test_rows = main_key.loc[(main_key.split == "test") & (main_key.condition == "C1")].sort_values("row_index")["row_index"].to_numpy()
    pool_rows = main_key.loc[(main_key.split == "calibration") & (main_key.condition == "C1")].sort_values("row_index")["row_index"].to_numpy()
    return {"df": df, "ctx": ctx, "targets": targets, "train": train, "test_rows": test_rows, "pool_rows": pool_rows, "main_key": main_key}


def stored(s, model, condition):
    cfg, template = main_run.load_config()
    personas = main_run.load_personas()
    got = main_run.load_answer_arrays(model, condition, s["main_key"], personas, template)
    if got is None:
        raise SystemExit(f"stage 2 answers missing for {model} {condition}")
    return got


def stage2_draws(s, kind_index, kind):
    pool = s["ctx"]["pool"]
    return cal.make_draws(pool["w"], pool["units"], DRAWS["n"], kind, DRAWS["repeats"], [DRAWS["seed"], DRAWS["n"], kind_index], DRAWS["pi_draws"], DRAWS["pi_seed"])


def write(name, doc, text=None):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    if text is not None:
        (RESULTS / f"{name}.md").write_text(text, encoding="utf-8")


# ---------- A1 ----------


def universe_cells(s, values_df):
    """Cell index 0..m-1 of the context for an age and sex frame."""
    raw = (values_df[paths.AGE].astype(int) * 10 + values_df[paths.SEX].astype(int)).to_numpy()
    ids = sorted(set(data.cell_id(s["df"])[splits.masks(splits.load_manifest(s["df"]))["test"]].tolist()))
    index = {c: i for i, c in enumerate(ids)}
    return np.array([index[c] for c in raw])


def reference_p(s):
    """p_h per item for the reference Neyman: a2024 where the item exists there, the train split otherwise."""
    ctx, df, targets, train = s["ctx"], s["df"], s["targets"], s["train"]
    m = ctx["m"]
    cells = universe_cells(s, df)
    w = df[paths.WEIGHT].to_numpy()
    out = {t: cal.cell_mean(targets[t].to_numpy()[train].astype(float), w[train], cells[train], m) for t in stage4.ITEMS}
    sources = {t: "train split" for t in stage4.ITEMS}
    _, meta = pyreadstat.read_sav(str(paths.SAV_2024), metadataonly=True)
    if "A19_1" in meta.column_names:
        raise SystemExit("a2024 now holds A19_1, which the plan says it does not")
    d24, _ = pyreadstat.read_sav(str(paths.SAV_2024), usecols=["A15_1", paths.WEIGHT, paths.AGE, paths.SEX])
    cells24 = universe_cells(s, d24)
    out["carb"] = cal.cell_mean(d24["A15_1"].isin([7, 8]).astype(float).to_numpy(), d24[paths.WEIGHT].to_numpy(), cells24, m)
    sources["carb"] = "a2024 A15_1 in {7,8}"
    return out, sources


def fmt_diff(v):
    return f"{v['mean_diff']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]"


def allocation_md(doc):
    lines = ["# A1 allocation: does the panel help spend 200 people", "", "Stored answers only. The calibration pool stands in for the population. Intervals are across 200 draws with the pool and the test panel fixed. Not comparable digit for digit with stage 2, whose row draws and weights differ. Plan: config/prereg_stage4.json.", ""]
    lines += ["## Allocations (n per cell)", "", "| allocation | " + " | ".join(doc["cell_names"]) + " |", "|---|" + "---|" * len(doc["cell_names"])]
    a = doc["allocations"]
    for name in stage4.CANON_ALLOCATIONS:
        lines.append(f"| {name} | " + " | ".join(str(x) for x in a[name]) + " |")
    lines.append("| pool rows (cap) | " + " | ".join(str(x) for x in doc["caps"]) + " |")
    lines += ["", f"Reference p sources: {doc['reference_sources']}.", ""]
    lines += ["## Reading fixed in advance", "", f"- Panel helps over proportional: {doc['reading']['panel_helps_over_proportional']} (R1, panel excluded truth, 3 item cell MAE, panel Neyman minus proportional {fmt_diff(doc['reading']['panel_minus_proportional_r1_average'])}).", f"- Panel adds over the reference: {doc['reading']['panel_adds_over_reference']} (same metric, panel Neyman minus reference Neyman {fmt_diff(doc['reading']['panel_minus_reference_r1_average'])}).", ""]
    for est in ("R1", "shrink", "direct"):
        for truth in ("panel_excluded", "whole_test", "pool_own"):
            for metric in ("cell_mae", "national_error"):
                b = doc["estimators"][est][truth][metric]
                lines += [f"## {est}, {truth}, {metric} (pp)", "", "| allocation | item | mean | minus proportional |", "|---|---|---|---|"]
                for name in [*stage4.CANON_ALLOCATIONS, *stage4.BY_ITEM_ALLOCATIONS]:
                    for t in (*stage4.ITEMS, stage4.AVERAGE):
                        diff = "-" if name == "proportional" else fmt_diff(b["minus_proportional"][name][t])
                        lines.append(f"| {name} | {t} | {b['mean'][name][t]} | {diff} |")
                lines += ["", "Panel Neyman minus reference Neyman: " + ", ".join(f"{t} {fmt_diff(b['panel_minus_reference'][t])}" for t in (*stage4.ITEMS, stage4.AVERAGE)), ""]
    return "\n".join(lines) + "\n"


def cmd_allocation(_args):
    guard()
    s = setup()
    ctx = s["ctx"]
    m = ctx["m"]
    train = s["train"]
    cells_all = universe_cells(s, s["df"])
    w = s["df"][paths.WEIGHT].to_numpy()
    totals = np.bincount(cells_all[train], weights=w[train], minlength=m)
    cell_share = totals / totals.sum()
    terra_c2 = stored(s, TERRA, "C2")
    panel_p = {t: cal.panel_cells(terra_c2["test"][t], ctx["panel"]["w"], ctx["panel"]["cells"], m) for t in stage4.ITEMS}
    ref_p, sources = reference_p(s)
    caps = np.bincount(ctx["pool"]["cells"], minlength=m)
    allocations = stage4.build_allocations(cell_share, panel_p, ref_p, A1_PLAN["n"], caps)
    store = stage4.allocation_study(ctx, allocations, cell_share, A1_PLAN["draws"], A1_PLAN["seed"])
    doc = stage4.summarise_allocation(store, allocations, caps, A1_PLAN["draws"])
    ids = sorted(set(data.cell_id(s["df"])[splits.masks(splits.load_manifest(s["df"]))["test"]].tolist()))
    doc = {"plan": A1_PLAN, "cell_names": [str(c) for c in ids], "cell_share": [round(float(x), 4) for x in cell_share], "reference_sources": sources, **doc}
    write("allocation", doc, allocation_md(doc))
    print(json.dumps({"reading": doc["reading"], "allocations": {k: doc["allocations"][k] for k in stage4.CANON_ALLOCATIONS}, "caps": doc["caps"]}, ensure_ascii=False, indent=1))


# ---------- A2 ----------


def flags_md(doc):
    lines = ["# A2 flags: can in-run signals name wrong cells before real data", "", "36 item by cell units, Terra C2. Error: absolute cell error of E4 from 200 real draws, averaged, against the panel excluded truth. Stored answers only. No correction across signals. Plan: config/prereg_stage4.json.", "", "panel_level is a comparator added by the worker: it needs no second model.", "", "| signal | usable units | Spearman | interval | within item Spearman | interval | overlap top 9 | random mean | random 95 | p one sided | minus level interval | names wrong cells |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, d in doc["signals"].items():
        o = d["overlap_top9"]
        minus = d.get("minus_level_ci", {}).get("ci95", "-")
        lines.append(f"| {n} | {d['usable_units']} | {d['spearman']} | {d['spearman_ci']['ci95']} | {d['within_item_spearman']} | {d['within_item_ci']['ci95']} | {o['observed']} | {o['random_mean']} | {o['random_95']} | {o['p_one_sided']} | {minus} | {d['names_wrong_cells']} |")
    lines += ["", "Whole test truth sensitivity: " + ", ".join(f"{n} Spearman {d['whole_test_truth']['spearman']} overlap {d['whole_test_truth']['overlap_top9']['observed']}" for n, d in doc["signals"].items()), "", f"Error by item: {doc['error']}"]
    return "\n".join(lines) + "\n"


def cmd_flags(_args):
    guard()
    s = setup()
    ctx = s["ctx"]
    cfg, template = main_run.load_config()
    personas = main_run.load_personas()
    stability, missing = main_run.load_stability(cfg, s["main_key"], personas, template)
    if missing or stability is None:
        raise SystemExit(f"stability answers missing: {missing}")
    key = s["main_key"]
    stab_rows = key.loc[(key.stability == 1) & (key.condition == cfg["stability"]["condition"])].sort_values("row_index")["row_index"].to_numpy()
    position = {r: i for i, r in enumerate(s["test_rows"].tolist())}
    stab_positions = np.array([position[r] for r in stab_rows.tolist()])
    answers = {"terra_C2": stored(s, TERRA, "C2"), "terra_C1": stored(s, TERRA, "C1"), "luna_C2": stored(s, LUNA, "C2")}
    draws = stage2_draws(s, 0, "row")
    doc = stage4.flag_study(ctx, answers, stability, stab_positions, A2_PLAN, draws)
    doc = {"plan": A2_PLAN, "panel_scored": "gpt-6.1-terra C2", "stability_respondents": int(len(stab_positions)), **doc}
    write("flags", doc, flags_md(doc))
    print(flags_md(doc))


# ---------- A3 ----------


def duel_slots(s):
    terra = stored(s, TERRA, "C2")
    luna = stored(s, LUNA, "C1")
    surrogate = verdict_study.surrogate_answers(s["df"], s["targets"], s["train"], s["test_rows"], s["pool_rows"])
    known = verdict_study.known_signal_answers(s["df"], s["targets"], s["train"], s["test_rows"], s["pool_rows"], list(STRENGTHS))
    slots = {"terra_C2": terra, "luna_C1": luna}
    for strength in STRENGTHS:
        slots[f"control_s{strength}"] = known[f"control_s{strength}|C2"]
    slots["surrogate_terra_slot"] = surrogate["gpt-6.1-terra|C2"]
    slots["surrogate_luna_slot"] = surrogate["gpt-6-luna|C1"]
    return slots


def duel_md(doc):
    a = doc["acceptance"]
    lines = ["# A3 duel validity: the duel with no outside truth", "", "Inside a real sample of 200: 5 fold cross validation stratified by cell, calibrated panel E4 against age and sex logistic R1, out of fold log loss. Keep only if the interval of the mean fold improvement lies wholly above zero. Stored answers only. Plan: config/prereg_stage4.json.", "", f"## Acceptance stated in advance: {'PASSED' if a['passed'] else 'FAILED'}", "", f"Positive control {a['positive_control']} keep rate {a['positive_keep_rate']}. Surrogate keep rates {a['surrogate_keep_rates']}. Margin over the higher surrogate {a['margin']} {a['margin_ci95']}. Surrogate bar met: {a['surrogate_bar_met']}. Positive bar met: {a['positive_bar_met']}.", "", doc["reading"], ""]
    for kind in ("row", "cluster"):
        lines += [f"## {kind} draws, pooled decision, panel excluded truth" + (" (sensitivity, not read by the acceptance)" if kind == "cluster" else ""), "", "| panel | keep rate | interval | beats R1 on truth | kept and beats | kept, not beats | dropped and beats | dropped, not beats | false keep rate | false keep over not beating | missed keep rate | mean improvement |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, blocks in doc[kind].items():
            r = blocks["pooled"]["panel_excluded"]
            c = r["counts"]
            lines.append(f"| {name} | {r['keep_rate']} | {r['keep_rate_ci95']} | {r['beats_rate']} | {c['kept_and_beats']} | {c['kept_not_beats']} | {c['dropped_and_beats']} | {c['dropped_not_beats']} | {r['false_keep_rate']} | {r['false_keep_over_not_beating']} | {r['missed_keep_rate']} | {blocks['pooled']['mean_improvement']} |")
        lines += ["", f"### {kind} draws, per item keep rate on the same rule", "", "| panel | ever | weekly | carb |", "|---|---|---|---|"]
        for name, blocks in doc[kind].items():
            lines.append(f"| {name} | " + " | ".join(str(blocks[t]["panel_excluded"]["keep_rate"]) for t in stage4.ITEMS) + " |")
        lines += ["", f"### {kind} draws, whole test truth sensitivity, pooled", "", "| panel | beats R1 | false keep rate | missed keep rate |", "|---|---|---|---|"]
        for name, blocks in doc[kind].items():
            r = blocks["pooled"]["whole_test"]
            lines.append(f"| {name} | {r['beats_rate']} | {r['false_keep_rate']} | {r['missed_keep_rate']} |")
        lines.append("")
    lines += ["## Limits", "", "- Anchor items with KREI answers. No concept question has met a real survey.", "- 5 fold intervals share training rows, so their nominal coverage is not exact. The keep rates above are the measured behaviour.", "- The surrogate's age and sex model was fit on the train split, far more rows than 200, so it can beat R1 on truth without any LLM.", "- Folds do not keep survey units whole, as the plan asked."]
    return "\n".join(lines) + "\n"


def cmd_duel(_args):
    guard()
    s = setup()
    ctx = s["ctx"]
    slots = duel_slots(s)
    doc = {"plan": A3_PLAN, "bar": BAR}
    raw_row = None
    for kind_index, kind in enumerate(("row", "cluster")):
        draws = stage2_draws(s, kind_index, kind)
        raw = stage4.duel_study(ctx, slots, draws, A3_PLAN["fold_seed"])
        doc[kind] = stage4.summarise_duel(raw, stage4.ITEMS, A3_PLAN["resamples"], A3_PLAN["seed"])
        if kind == "row":
            raw_row = raw
    doc["acceptance"] = stage4.acceptance(raw_row, BAR, POSITIVE, SURROGATES, A3_PLAN["resamples"], A3_PLAN["seed"])
    a = doc["acceptance"]
    doc["reading"] = "The acceptance passed. The duel may be called a decision rule for the anchor items under row draws from this pool. No concept question has met a real survey." if a["passed"] else "The acceptance failed. The duel is labelled a health check, not a verdict, in the report and in ingest output. No tuning follows."
    write("duel_validity", doc, duel_md(doc))
    print(duel_md(doc))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze").set_defaults(func=lambda _a: (FROZEN.write_text(json.dumps(current_hashes(), indent=2), encoding="utf-8"), print(json.dumps(current_hashes(), indent=2))))
    sub.add_parser("check").set_defaults(func=lambda _a: (guard(), print(json.dumps({"frozen": "ok", "committed": "ok"}))))
    for name, fn in (("allocation", cmd_allocation), ("flags", cmd_flags), ("duel", cmd_duel)):
        sub.add_parser(name).set_defaults(func=fn)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
