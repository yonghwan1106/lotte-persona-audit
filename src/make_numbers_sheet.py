"""results/numbers_sheet.json: every number a deliverable may cite, read from result files by this script. No number is typed here.

  python src/make_numbers_sheet.py                    build the sheet from the result files
  python src/make_numbers_sheet.py --record-tests     run pytest first and record its count in results/fix_stage/pytest_summary.json

Each entry has key, value, unit, source (a tracked file), stage and caveat. No API call and no row level file is read. Aggregates only.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lotte_audit import paths  # noqa: E402

OUT = paths.RESULTS / "numbers_sheet.json"
CAVEATS = json.loads((paths.CONFIG / "numbers_sheet_caveats.json").read_text(encoding="utf-8"))
PANELS = ("gpt-6.1-terra|C2", "gpt-6.1-terra|C1", "gpt-6-luna|C2", "gpt-6-luna|C1")
ITEMS = ("ever", "weekly", "carb", "average")
SHORT = {"gpt-6.1-terra": "terra", "gpt-6-luna": "luna", "gpt-6.1-sol": "sol"}


def rel(path):
    return str(Path(path).relative_to(paths.ROOT)).replace("\\", "/")


def load(relative):
    return json.loads((paths.ROOT / relative).read_text(encoding="utf-8"))


def slot(key):
    model, cond = key.split("|")
    return f"{SHORT.get(model, model)}_{cond}"


class Sheet:
    def __init__(self):
        self.rows = []
        self.keys = set()

    def add(self, key, value, unit, source, stage, caveat):
        if key in self.keys:
            raise ValueError(f"duplicate key {key}")
        if caveat not in CAVEATS:
            raise KeyError(caveat)
        if value is None:
            return
        self.keys.add(key)
        self.rows.append({"key": key, "value": value, "unit": unit, "source": source, "stage": stage, "caveat": CAVEATS[caveat]})

    def diff(self, key, block, unit, source, stage, caveat):
        """A difference block: mean and interval as two entries."""
        self.add(f"{key}.mean_diff", block.get("mean_diff"), unit, source, stage, caveat)
        self.add(f"{key}.ci95", block.get("ci95"), f"{unit}, percentile 95", source, stage, caveat)


def gate(s):
    for model in ("gpt-6.1-terra", "gpt-6-luna"):
        src = f"results/gate/gate_score_{model}.json"
        doc = load(src)
        short = SHORT[model]
        s.add(f"gate.{short}.decision", doc["switch_rule"]["decision"], "label", src, "gate", "gate")
        s.add(f"gate.{short}.same_300_real_answers_cell_mae_average", doc["same_300_real_answers_cell_mae"]["average"], "pp", src, "gate", "real_answers_1p53")
        for cond, c in doc["conditions"].items():
            s.add(f"gate.{short}.{cond}.n", c["n"], "calls", src, "gate", "gate")
            s.add(f"gate.{short}.{cond}.average_cell_mae", c["average_cell_mae"], "pp", src, "gate", "gate")
            s.add(f"gate.{short}.{cond}.average_constant_cell_mae", c["average_constant_cell_mae"], "pp", src, "gate", "gate")
            s.add(f"gate.{short}.{cond}.worth_n_label", c["worth_n"]["label"], "label", src, "gate", "gate")
        for row in doc["switch_rule"]["detail"]:
            base = f"gate.{short}.{row['condition']}.{row['item']}"
            s.add(f"{base}.auc", row["auc"], "AUC", src, "gate", "gate_auc")
            s.add(f"{base}.floor_auc", row["floor"], "AUC", src, "gate", "gate_auc")


def stage2(s):
    src = "results/main/main_score.json"
    doc = load(src)
    ref = doc["reference"]
    s.add("stage2.noise_floor.average", ref["noise_floor_average_pp"], "pp", src, "stage 2", "noise_floor")
    for item, v in ref["noise_floor_by_item_pp"].items():
        s.add(f"stage2.noise_floor.{item}", v, "pp", src, "stage 2", "noise_floor")
    for name in ("pool_all_rows_direct", "pool_all_rows_shrunk", "test_panel_real_answers"):
        for item, v in ref[name].items():
            s.add(f"stage2.reference.{name}.{item}", v, "pp cell MAE", src, "stage 2", "real_answers_1p53" if name == "test_panel_real_answers" else "stage2_vs_e2")
    for block, cal in doc["calibration"].items():
        n, kind = block.split("|")
        head = f"stage2.n{n}.{kind}"
        s.add(f"{head}.realised_n_mean", cal["realised_n_mean"], "respondents", src, "stage 2", "stage2_vs_e2")
        for name, by_item in cal["estimators"].items():
            parts = name.split("|")
            label = name if len(parts) == 1 else f"{slot(parts[0] + '|' + parts[1])}.{parts[2]}"
            caveat = "stage2_raw_e3" if name.endswith("E3") else "stage2_vs_e2"
            for item in ITEMS:
                if item not in by_item:
                    continue
                v = by_item[item]
                if isinstance(v, dict):
                    s.add(f"{head}.{label}.{item}.cell_mae", v.get("cell_mae"), "pp", src, "stage 2", caveat)
                    if "mean_diff" in v:
                        s.diff(f"{head}.{label}.{item}.minus_E2", v, "pp", src, "stage 2", caveat)
                else:
                    s.add(f"{head}.{label}.{item}.cell_mae", v, "pp", src, "stage 2", caveat)
        for name, by_item in cal["difference_to_R1"].items():
            parts = name.split("|")
            label = f"{slot(parts[0] + '|' + parts[1])}.{parts[2]}"
            for item in ITEMS:
                if item in by_item:
                    s.diff(f"{head}.{label}.{item}.minus_R1", by_item[item], "pp", src, "stage 2", "stage2_vs_r1")
    for item, block in doc["person_level"].items():
        s.add(f"stage2.person.{item}.floor_auc", block["floor_auc"], "AUC", src, "stage 2", "person_level")
        for key, p in block["by_panel"].items():
            base = f"stage2.person.{item}.{slot(key)}"
            s.add(f"{base}.auc", p["auc"], "AUC", src, "stage 2", "person_level")
            s.add(f"{base}.auc_minus_floor", p["auc_minus_floor"], "AUC", src, "stage 2", "person_level")
            s.add(f"{base}.diff_ci95", p["diff_ci95"], "AUC, percentile 95", src, "stage 2", "person_level")
            s.add(f"{base}.holm_p", p.get("holm_p"), "p", src, "stage 2", "person_level")
    for item, block in doc["stereotypes"].items():
        s.add(f"stage2.stereotype.{item}.real_national_pct", block["real_national_pct"], "pct", src, "stage 2", "stereotype")
        s.add(f"stage2.stereotype.{item}.real_gender_gap_pp", block["real_gender_gap_pp"], "pp", src, "stage 2", "stereotype")
        s.add(f"stage2.stereotype.{item}.real_gender_gap_ci95", block["real_gender_gap_ci95"], "pp, percentile 95", src, "stage 2", "stereotype")
        s.add(f"stage2.stereotype.{item}.real_age_slope_ci95", block["real_age_slope_ci95"], "pp per band, percentile 95", src, "stage 2", "stereotype")
        for key, p in block["by_panel"].items():
            base = f"stage2.stereotype.{item}.{slot(key)}"
            for field, unit in (("bias_pp", "pp"), ("gender_gap_pp", "pp"), ("gap_minus_real_ci95", "pp, percentile 95"), ("age_slope_pp_per_band", "pp per band"), ("underdispersion_ratio", "ratio"), ("cell_pearson_r", "r")):
                s.add(f"{base}.{field}", p[field], unit, src, "stage 2", "stereotype")
    for item, block in doc["stability"].items():
        for field, unit in (("respondents", "respondents"), ("mean_abs_diff_pp", "pp"), ("rank_correlation_mean", "correlation"), ("within_person_sd_pp", "pp"), ("between_person_sd_pp", "pp")):
            s.add(f"stage2.stability.{item}.{field}", block[field], unit, src, "stage 2", "stability")


def verdicts(s):
    src = "results/verdict_v3/verdict_v3.json"
    doc = load(src)
    for name, block in (("llm", doc["llm"]), ("real_answers", doc["real_answers"]), ("surrogate", doc["surrogate"])):
        for version in ("v1", "v2", "v3"):
            for label, count in block[f"counts_{version}"].items():
                s.add(f"verdict.{name}.{version}.count.{label}", count, "of 12", src, "verdict study", "verdict_counts")
    for r in doc["llm"]["rows"]:
        s.add(f"verdict.llm.{slot(r['model'] + '|' + r['condition'])}.{r['item']}.labels", {"v1": r["v1"], "v2": r["v2"], "v3": r["v3"]}, "labels", src, "verdict study", "verdict_counts")
    a = doc["acceptance"]
    s.add("verdict.v3.acceptance_passed", a["passed"], "bool", src, "verdict study", "v3_acceptance")
    s.add("verdict.v3.acceptance.real_answers_calibrated_items_per_slot", len(a["real_answers_per_slot"][PANELS[0]]["calibrated"]), "of 3", src, "verdict study", "v3_acceptance")
    s.add("verdict.v3.acceptance.surrogate_calibrated_rows", len(a["surrogate_rows_calibrated"]), "of 12", src, "verdict study", "v3_acceptance")
    s.add("verdict.v3.product_labels_allowed", doc["product_labels_allowed"], "bool", src, "verdict study", "v3_acceptance")
    for seed, count in doc["llm"]["gender_ban_by_seed"].items():
        s.add(f"verdict.gender_flag.count.{seed}", count, "of 12", src, "verdict study", "gender_flag")
    s.add("verdict.gender_flag.rows_that_move", doc["llm"]["gender_flag_rows_that_move"], "rows", src, "verdict study", "gender_flag")
    m = doc["panel_mass"]
    s.add("stage2.panel_share_of_test_psfwt", round(100 * m["panel_share_of_test_psfwt"], 2), "pct", src, "verdict study", "panel_mass")
    s.add("stage2.panel_share_of_test_psfwt.cell_min", round(100 * m["cell_min"], 2), "pct", src, "verdict study", "panel_mass")
    s.add("stage2.panel_share_of_test_psfwt.cell_max", round(100 * m["cell_max"], 2), "pct", src, "verdict study", "panel_mass")
    s.add("stage2.outside_truth_rows", m["outside_rows"], "rows", src, "verdict study", "panel_mass")
    for r in doc["real_answers"]["rows"][:3]:
        s.diff(f"verdict.real_answers.{r['item']}.E4_minus_R1.row", r["row_vs_r1"]["E4"], "pp", src, "verdict study", "v3_acceptance")
        s.add(f"verdict.real_answers.{r['item']}.E4_minus_R1.cluster.mean_diff", r["cluster_vs_r1"]["E4"]["mean_diff"], "pp", src, "verdict study", "v3_acceptance")
    src = "results/stage3/verdict_v2.json"
    doc = load(src)
    for r in doc["answers"]["rows"]:
        base = f"verdict.llm.{slot(r['model'] + '|' + r['condition'])}.{r['item']}"
        for e in ("E4", "E5", "E6"):
            s.diff(f"{base}.{e}_minus_R1_outside.row", r["v2_inputs"]["vs_r1_row"][e], "pp", src, "stage 3", "stage2_vs_r1")
            s.diff(f"{base}.{e}_minus_R1_outside.cluster", r["v2_inputs"]["vs_r1_cluster"][e], "pp", src, "stage 3", "stage2_vs_r1")
    src = "results/verdict_v3/ceiling.json"
    doc = load(src)
    for other, bands in doc["ranking_perfect_estimator"].items():
        for band, v in bands.items():
            s.diff(f"ranking.ceiling.perfect_minus_{other}.{band}", v, "pair accuracy", src, "verdict study", "ranking_ceiling")
            s.add(f"ranking.ceiling.perfect_minus_{other}.{band}.beats", v["beats"], "bool", src, "verdict study", "ranking_ceiling")


def ranking(s):
    src = "results/stage3/option_ranking.json"
    doc = load(src)
    for set_name, block in doc["sets"].items():
        overall = block["groups"]["overall"]
        for name, est in overall["estimators"].items():
            for metric in ("spearman", "pair_accuracy", "top3_overlap", "share_mae_pp"):
                base = f"ranking.{set_name}.{name}.{metric}"
                s.add(f"{base}.value", est[metric]["value"], metric, src, "stage 3", "ranking")
                s.add(f"{base}.ci95", est[metric].get("ci95"), f"{metric}, percentile 95", src, "stage 3", "ranking")
        for name, est in overall["direct"].items():
            for metric in ("spearman", "pair_accuracy", "top3_overlap", "share_mae_pp"):
                base = f"ranking.{set_name}.{name}.{metric}"
                s.add(f"{base}.value", est[metric]["mean"], metric, src, "stage 3", "ranking")
                s.add(f"{base}.ci95", est[metric]["draw_ci95"], f"{metric}, draw percentile 95", src, "stage 3", "ranking")
        for name, d in overall["differences"].items():
            for metric in ("spearman", "pair_accuracy", "top3_overlap", "share_mae_pp"):
                s.diff(f"ranking.{set_name}.{name}.{metric}", d[metric], metric, src, "stage 3", "ranking")
    primary = doc["sets"]["merged_coffee_15"]["groups"]["overall"]
    for band in ("under_1pp", "1_to_3pp", "3_to_5pp", "5pp_and_over"):
        for prefix in ("true_gap", "estimated_gap"):
            for name in ("panel_C2", "panel_C1"):
                e = primary["estimators"][name]
                s.add(f"ranking.bands.{name}.{prefix}.{band}.accuracy", e[f"{prefix}|{band}|accuracy"]["value"], "pair accuracy", src, "stage 3", "ranking_band")
                s.add(f"ranking.bands.{name}.{prefix}.{band}.ci95", e[f"{prefix}|{band}|accuracy"].get("ci95"), "pair accuracy, percentile 95", src, "stage 3", "ranking_band")
                s.add(f"ranking.bands.{name}.{prefix}.{band}.n_pairs", e[f"{prefix}|{band}|n_pairs"]["value"], "pairs", src, "stage 3", "ranking_band")
        for name in ("krei_2024", "gate_300_real_reference", "train_reference"):
            s.add(f"ranking.bands.{name}.true_gap.{band}.accuracy", primary["estimators"][name][f"true_gap|{band}|accuracy"]["value"], "pair accuracy", src, "stage 3", "ranking_band")
        for name in ("direct_row", "direct_cluster"):
            s.add(f"ranking.bands.{name}.true_gap.{band}.accuracy", primary["direct"][name][f"true_gap|{band}|accuracy"]["mean"], "pair accuracy", src, "stage 3", "ranking_band")
    for r in doc["operating_rule"]:
        s.add(f"ranking.rule.{r['panel']}.{r['gap_kind']}.{r['band']}.above_chance", r["above_chance"], "bool", src, "stage 3", "ranking_ceiling")
    for option, share in doc["truth_shares_pct"]["overall"].items():
        s.add(f"ranking.truth_share_pct.option_{option}", share, "pct", src, "stage 3", "ranking")


def demo(s):
    src = "results/fix_stage/demo6/diagnostics.json"
    doc = load(src)
    for model, d in doc["by_model"].items():
        short = SHORT[model]
        s.add(f"demo.{short}.n_personas", d["n_personas"], "personas", src, "demo", "demo")
        s.add(f"demo.{short}.noise_A_minus_A_para.mean", d["noise"]["mean"], "pp, panel internal", src, "demo", "demo")
        s.add(f"demo.{short}.noise_A_minus_A_para.ci95", d["noise"]["ci95"], "pp, percentile 95", src, "demo", "demo")
        s.add(f"demo.{short}.noise_upper", d["noise_upper"], "pp, panel internal", src, "demo", "demo")
        s.add(f"demo.{short}.rank", d["rank"], "cards", src, "demo", "demo")
        for key, g in d["gaps"].items():
            name = key.replace("|", "_minus_")
            s.add(f"demo.{short}.gap.{name}.mean", g["mean"], "pp, panel internal", src, "demo", "demo")
            s.add(f"demo.{short}.gap.{name}.ci95", g["ci95"], "pp, percentile 95", src, "demo", "demo")
            s.add(f"demo.{short}.gap.{name}.distinguishable", g["distinguishable"], "bool", src, "demo", "demo")
        for card, g in d["negative"].items():
            s.add(f"demo.{short}.negative.{card}.mean", g["mean"], "pp, panel internal", src, "demo", "demo")
            s.add(f"demo.{short}.negative.{card}.ci95", g["ci95"], "pp, percentile 95", src, "demo", "demo")
            s.add(f"demo.{short}.negative.{card}.separated", g["separated"], "bool", src, "demo", "demo")
        s.add(f"demo.{short}.brand.mean", d["brand"]["mean"], "pp, panel internal", src, "demo", "demo")
        s.add(f"demo.{short}.brand.ci95", d["brand"]["ci95"], "pp, percentile 95", src, "demo", "demo")
        s.add(f"demo.{short}.brand.exceeds_noise", d["brand"]["exceeds_noise"], "bool", src, "demo", "demo")
    src = "results/fix_stage/demo6/verdict.json"
    doc = load(src)
    for r in doc["rows"]:
        if r["segment"] == "all":
            s.add(f"demo.{SHORT[r['model']]}.{r['card']}.label", r["label"], "label", src, "demo", "demo_labels")
    src = "results/fix_stage/demo6/allocation.json"
    doc = load(src)
    for name in ("overall", "target", "rest", "six_cells_even", "twelve_cells_even", "first_card_each"):
        block = doc.get(name)
        if block:
            s.add(f"demo.allocation.{name}.n", block["n"], "respondents", src, "demo", "demo")
            s.add(f"demo.allocation.{name}.margin_pp", block["margin_pp"], "pp", src, "demo", "demo")


def per_call(s, base, block, calls_field, price, per, src, stage):
    calls = block[calls_field]
    if not calls:
        return
    usd = (block["input_tokens"] * price["input"] + block["output_tokens"] * price["output"]) / 1_000_000
    one = usd / calls
    s.add(f"{base}.input_tokens_per_call", round(block["input_tokens"] / calls, 1), "tokens", src, stage, "cost_list")
    s.add(f"{base}.output_tokens_per_call", round(block["output_tokens"] / calls, 1), "tokens", src, stage, "cost_list")
    s.add(f"{base}.per_respondent_usd", round(one * per, 6), "USD", src, stage, "cost_list")
    s.add(f"{base}.per_300_panel_usd", round(one * per * 300, 4), "USD", src, stage, "cost_list")


def costs(s):
    prices = load("config/agent_run.json")
    table = {m["id"]: m["usd_per_1m"] for m in prices["models"].values()}
    src = "results/gate_run_summary.json"
    doc = load(src)
    for model, block in doc["models"].items():
        for cond in ("C1", "C2"):
            per_call(s, f"cost.gate_prompt.{SHORT[model]}.{cond}", block["by_condition"][cond], "calls_billed", table[model], 1, src, "gate")
    src = "results/stage3/stage3_run_summary.json"
    doc = load(src)
    for model, block in doc["models"].items():
        for cond in ("C1", "C2"):
            per_call(s, f"cost.ranking_prompt.{SHORT[model]}.{cond}", block["by_condition"][cond], "calls_billed", table[model], 1, src, "stage 3")
    src = "results/agent/run_summary.json"
    doc = load(src)
    for model, block in doc["panel"]["models"].items():
        per_call(s, f"cost.concept_prompt.{SHORT[model]}.six_cards", block["by_condition"]["C1"], "calls_billed", table[model], 6, src, "agent stage")


def spend(s):
    gate_doc = load("results/gate_run_summary.json")
    main_doc = load("results/main/main_run_summary.json")
    stage3_doc = load("results/stage3/stage3_run_summary.json")
    agent_doc = load("results/agent/run_summary.json")
    fix_doc = load("results/fix_stage/run_summary.json")
    wf7 = load("results/fix_stage/wf7_attack_record.json")
    s.add("spend.gate", gate_doc["gate_total_usd"], "USD", "results/gate_run_summary.json", "gate", "spend")
    s.add("spend.stage2", main_doc["stage_total_usd"], "USD", "results/main/main_run_summary.json", "stage 2", "spend")
    s.add("spend.stage3", stage3_doc["stage_total_usd"], "USD", "results/stage3/stage3_run_summary.json", "stage 3", "spend")
    s.add("spend.agent_stage", agent_doc["stage_spent_usd"], "USD", "results/agent/run_summary.json", "agent stage", "spend")
    s.add("spend.agent_stage.panel", agent_doc["panel"]["panel_total_usd"], "USD", "results/agent/run_summary.json", "agent stage", "spend")
    s.add("spend.wf7_attacks", wf7["spend_usd"]["total"], "USD", "results/fix_stage/wf7_attack_record.json", "wf7 attacks", "spend_attack")
    s.add("spend.wf7_attacks.live", wf7["spend_usd"]["live_from_log"], "USD", "results/fix_stage/wf7_attack_record.json", "wf7 attacks", "spend_attack")
    s.add("spend.wf7_attacks.probe", wf7["spend_usd"]["probe_as_recorded"], "USD", "results/fix_stage/wf7_attack_record.json", "wf7 attacks", "spend_attack")
    s.add("spend.fix_stage", fix_doc["stage_spent_usd"], "USD", "results/fix_stage/run_summary.json", "fix stage", "spend")
    s.add("spend.fix_stage.budget", fix_doc["budget_usd"], "USD", "results/fix_stage/run_summary.json", "fix stage", "spend")
    s.add("spend.fix_stage.panel_calls", fix_doc["panel"]["models"] and sum(m["attempts"] for m in fix_doc["panel"]["models"].values()) or 0, "calls", "results/fix_stage/run_summary.json", "fix stage", "spend")
    stage4_doc = load("results/stage4/run_summary.json")
    s.add("spend.stage4", stage4_doc["stage_spent_usd"], "USD", "results/stage4/run_summary.json", "stage 4", "spend")
    s.add("spend.stage4.budget", stage4_doc["budget_usd"], "USD", "results/stage4/run_summary.json", "stage 4", "spend")
    s.add("spend.stage4.panel_calls", stage4_doc["panel"]["models"] and sum(m["attempts"] for m in stage4_doc["panel"]["models"].values()) or 0, "calls", "results/stage4/run_summary.json", "stage 4", "spend")
    total = gate_doc["gate_total_usd"] + main_doc["stage_total_usd"] + stage3_doc["stage_total_usd"] + agent_doc["stage_spent_usd"] + wf7["spend_usd"]["total"] + fix_doc["stage_spent_usd"] + stage4_doc["stage_spent_usd"]
    s.add("spend.all_stages_including_attacks", round(total, 6), "USD, sum of the entries above", "results/numbers_sheet.json", "all", "spend")


def scenarios(s):
    for name, src in (("agent_stage_final", "results/agent/scenarios/results.json"), ("agent_stage_first_batch", "results/agent/scenarios/first_batch/results.json"), ("fix_stage", "results/fix_stage/scenarios/results.json")):
        path = paths.ROOT / src
        if not path.exists():
            continue
        doc = load(src)
        rows = doc["results"]
        s.add(f"scenarios.{name}.runs", len(rows), "runs", src, "scenarios", "scenarios")
        s.add(f"scenarios.{name}.passed", sum(bool(r["passed"]) for r in rows), "runs", src, "scenarios", "scenarios")
        s.add(f"scenarios.{name}.kinds", len({(r["scenario"], r["mode"]) for r in rows}), "scenario and mode pairs", src, "scenarios", "scenarios")
        s.add(f"scenarios.{name}.cost_usd", round(sum(r["cost_usd"] for r in rows), 6), "USD", src, "scenarios", "scenarios")
    doc = load("results/fix_stage/scenarios/results.json")
    for d in doc["summary"]:
        s.add(f"scenarios.fix_stage.by_kind.{d['scenario']}.{d['mode']}", {"runs": d["runs"], "passed": d["passed"]}, "runs", "results/fix_stage/scenarios/results.json", "fix stage", "scenarios")


def attacks(s):
    src = "results/fix_stage/wf7_attack_record.json"
    wf7 = load(src)
    s.add("attacks.wf7.live_runs", wf7["live_runs"], "runs", src, "wf7 attacks", "attacks")
    s.add("attacks.wf7.offline_guard_variants_accepted", wf7["offline_guard_variants"]["accepted"], "of 21", src, "wf7 attacks", "attacks")
    s.add("attacks.wf7.probe.kept_minus_clean_t2b_pp", wf7["probe"]["kept_minus_clean_t2b_pp"], "pp, panel internal", src, "wf7 attacks", "probe")
    s.add("attacks.wf7.probe.ci95", wf7["probe"]["ci95"], "pp, percentile 95", src, "wf7 attacks", "probe")
    s.add("attacks.wf7.probe.n_personas", wf7["probe"]["n_personas"], "personas", src, "wf7 attacks", "probe")
    src = "results/fix_stage/attack_replay_live.json"
    doc = load(src)
    s.add("attacks.replay.live.total", doc["total"], "attacks", src, "fix stage", "attacks")
    s.add("attacks.replay.live.still_passing", doc["still_passing"], "attack ids", src, "fix stage", "attacks")
    s.add("attacks.replay.live.cost_usd", doc["cost_usd"], "USD", src, "fix stage", "attacks")
    for r in doc["rows"]:
        s.add(f"attacks.replay.live.{r['id']}.still_passes", r["still_passes"], "bool", src, "fix stage", "attacks")
    src = "results/fix_stage/attack_replay_offline.json"
    doc = load(src)
    s.add("attacks.replay.offline.guard_variants_total", doc["guard_variants"]["total"], "variants", src, "fix stage", "attacks")
    s.add("attacks.replay.offline.guard_variants_accepted", doc["guard_variants"]["accepted"], "variants", src, "fix stage", "attacks")
    s.add("attacks.replay.offline.note_variants_total", doc["note_variants"]["total"], "variants", src, "fix stage", "attacks")
    s.add("attacks.replay.offline.note_variants_kept", doc["note_variants"]["kept"], "variants", src, "fix stage", "attacks")
    s.add("attacks.replay.offline.leading_variants_total", doc["leading_variants"]["total"], "sentences", src, "fix stage", "attacks")
    s.add("attacks.replay.offline.leading_variants_flagged", doc["leading_variants"]["flagged"], "sentences", src, "fix stage", "attacks")
    s.add("attacks.replay.offline.guard_false_positives", doc["guard_false_positives"]["rejected"], "of ordinary sentences", src, "fix stage", "attacks")
    s.add("attacks.replay.offline.plan_hash_covers_card_text", doc["plan_hash_covers_card_text"], "bool", src, "fix stage", "attacks")


def stage4_allocation(s):
    src = "results/stage4/allocation.json"
    doc = load(src)
    for name in ("equal", "proportional", "panel_neyman", "reference_neyman"):
        s.add(f"stage4.allocation.n_per_cell.{name}", doc["allocations"][name], "respondents per cell", src, "stage 4", "stage4_allocation")
    s.add("stage4.allocation.caps", doc["caps"], "pool rows per cell", src, "stage 4", "stage4_allocation")
    s.add("stage4.allocation.reading.panel_helps_over_proportional", doc["reading"]["panel_helps_over_proportional"], "bool", src, "stage 4", "stage4_allocation")
    s.add("stage4.allocation.reading.panel_adds_over_reference", doc["reading"]["panel_adds_over_reference"], "bool", src, "stage 4", "stage4_allocation")
    for est, by_truth in doc["estimators"].items():
        for truth, by_metric in by_truth.items():
            for metric, block in by_metric.items():
                base = f"stage4.allocation.{est}.{truth}.{metric}"
                for alloc, by_item in block["mean"].items():
                    for item, value in by_item.items():
                        s.add(f"{base}.{alloc}.{item}.mean", value, "pp", src, "stage 4", "stage4_allocation")
                for alloc, by_item in block["minus_proportional"].items():
                    for item, diff in by_item.items():
                        s.diff(f"{base}.{alloc}_minus_proportional.{item}", diff, "pp", src, "stage 4", "stage4_allocation")
                for item, diff in block["panel_minus_reference"].items():
                    s.diff(f"{base}.panel_minus_reference.{item}", diff, "pp", src, "stage 4", "stage4_allocation")


def stage4_flags(s):
    src = "results/stage4/flags.json"
    doc = load(src)
    for item, block in doc["error"].items():
        s.add(f"stage4.flags.error.{item}.mean_pp", block["mean_pp"], "pp", src, "stage 4", "stage4_flags")
        s.add(f"stage4.flags.error.{item}.max_pp", block["max_pp"], "pp", src, "stage 4", "stage4_flags")
    for name, d in doc["signals"].items():
        base = f"stage4.flags.{name}"
        s.add(f"{base}.usable_units", d["usable_units"], "units", src, "stage 4", "stage4_flags")
        s.add(f"{base}.spearman", d["spearman"], "Spearman", src, "stage 4", "stage4_flags")
        s.add(f"{base}.spearman_ci95", d["spearman_ci"]["ci95"], "Spearman, percentile 95", src, "stage 4", "stage4_flags")
        s.add(f"{base}.within_item_spearman", d["within_item_spearman"], "Spearman", src, "stage 4", "stage4_flags")
        s.add(f"{base}.within_item_ci95", d["within_item_ci"]["ci95"], "Spearman, percentile 95", src, "stage 4", "stage4_flags")
        o = d["overlap_top9"]
        s.add(f"{base}.overlap_top9.observed", o["observed"], "of 9", src, "stage 4", "stage4_flags")
        s.add(f"{base}.overlap_top9.random_mean", o["random_mean"], "of 9", src, "stage 4", "stage4_flags")
        s.add(f"{base}.overlap_top9.p_one_sided", o["p_one_sided"], "p", src, "stage 4", "stage4_flags")
        s.add(f"{base}.names_wrong_cells", d["names_wrong_cells"], "bool", src, "stage 4", "stage4_flags")
        if "minus_level_ci" in d:
            s.add(f"{base}.minus_level_ci95", d["minus_level_ci"]["ci95"], "Spearman, percentile 95", src, "stage 4", "stage4_flags")
        s.add(f"{base}.whole_test_truth.spearman", d["whole_test_truth"]["spearman"], "Spearman", src, "stage 4", "stage4_flags")


def stage4_duel(s):
    src = "results/stage4/duel_validity.json"
    doc = load(src)
    a = doc["acceptance"]
    s.add("stage4.duel.acceptance.passed", a["passed"], "bool", src, "stage 4", "stage4_duel")
    s.add("stage4.duel.acceptance.label", a["label"], "label", src, "stage 4", "stage4_duel_label")
    s.add("stage4.duel.acceptance.positive_keep_rate", a["positive_keep_rate"], "share of 200 draws", src, "stage 4", "stage4_duel")
    s.add("stage4.duel.acceptance.margin", a["margin"], "share of 200 draws", src, "stage 4", "stage4_duel")
    s.add("stage4.duel.acceptance.margin_ci95", a["margin_ci95"], "share, percentile 95", src, "stage 4", "stage4_duel")
    for slot_name, rate in a["surrogate_keep_rates"].items():
        s.add(f"stage4.duel.acceptance.{slot_name}.keep_rate", rate, "share of 200 draws", src, "stage 4", "stage4_duel")
    for kind in ("row", "cluster"):
        for panel, blocks in doc[kind].items():
            for unit, b in blocks.items():
                base = f"stage4.duel.{kind}.{panel}.{unit}"
                s.add(f"{base}.mean_improvement", b["mean_improvement"], "log loss, R1 minus panel", src, "stage 4", "stage4_duel")
                for truth in ("panel_excluded", "whole_test"):
                    r = b[truth]
                    for field in ("keep_rate", "beats_rate", "false_keep_rate", "false_keep_over_not_beating", "false_keep_over_all_draws", "missed_keep_rate", "missed_keep_over_all_draws"):
                        s.add(f"{base}.{truth}.{field}", r[field], "share", src, "stage 4", "stage4_duel")
                    s.add(f"{base}.{truth}.keep_rate_ci95", r["keep_rate_ci95"], "share, percentile 95", src, "stage 4", "stage4_duel")
                    for field, value in r["counts"].items():
                        s.add(f"{base}.{truth}.count.{field}", value, "draws", src, "stage 4", "stage4_duel")
    src = "results/stage4/duel_seed_sensitivity.json"
    doc = load(src)
    for name, run in doc["runs"].items():
        s.add(f"stage4.duel.seed.{name}.acceptance_passed", run["acceptance_passed"], "bool", src, "stage 4", "stage4_duel_seed")
        for panel, rate in run["keep_rate"].items():
            s.add(f"stage4.duel.seed.{name}.{panel}.keep_rate", rate, "share of 200 draws", src, "stage 4", "stage4_duel_seed")


def stage4_product(s):
    src = "results/stage4/detectable.json"
    doc = load(src)
    s.add("stage4.detectable.between_mde_pp", doc["between_mde_pp"], "pp", src, "stage 4", "stage4_detectable")
    s.add("stage4.detectable.n_arm", doc["n_arm"], "respondents", src, "stage 4", "stage4_detectable")
    for rho, value in doc["within_mde_pp"].items():
        s.add(f"stage4.detectable.within_mde_pp.rho_{rho}", value, "pp", src, "stage 4", "stage4_detectable")
    for row in doc["needed"]:
        base = f"stage4.detectable.needed.gap_{row['gap_pp']}pp"
        s.add(f"{base}.between_per_arm", row["between_per_arm"], "respondents", src, "stage 4", "stage4_detectable")
        s.add(f"{base}.between_total", row["between_total"], "respondents", src, "stage 4", "stage4_detectable")
        for rho, value in row["within"].items():
            s.add(f"{base}.within.rho_{rho}", value, "respondents", src, "stage 4", "stage4_detectable")
    src = "results/stage4/demo7/action.json"
    doc = load(src)
    for row in doc["action"]["rows"]:
        s.add(f"stage4.demo7.action.{row['card']}", row["label"], "label", src, "stage 4", "stage4_action")
    s.add("stage4.demo7.action.drop_gap_pp", doc["action"]["drop_gap_pp"], "pp, panel internal", src, "stage 4", "stage4_action")
    src = "results/stage4/demo7/real_results.json"
    doc = load(src)
    s.add("stage4.ingest.source_label", doc["source_label"], "label", src, "stage 4", "stage4_ingest")
    s.add("stage4.ingest.is_real_concept_survey", doc["is_real_concept_survey"], "bool", src, "stage 4", "stage4_ingest")
    s.add("stage4.ingest.concept_duel", doc["concept_duel"], "label", src, "stage 4", "stage4_ingest")
    s.add("stage4.ingest.n_respondents", doc["n_respondents"], "respondents", src, "stage 4", "stage4_ingest")
    s.add("stage4.ingest.decision", doc["decision"], "label", src, "stage 4", "stage4_ingest")
    s.add("stage4.ingest.pooled.mean_improvement", doc["anchors"]["pooled"]["mean_improvement"], "log loss, R1 minus panel", src, "stage 4", "stage4_ingest")
    s.add("stage4.ingest.pooled.interval", doc["anchors"]["pooled"]["interval"], "log loss, t interval over 5 folds", src, "stage 4", "stage4_ingest")
    for card in ("A", "B", "C"):
        src = f"results/explore/demo7/{card}.json"
        doc = load(src)
        for section, items in doc["sections"].items():
            s.add(f"stage4.explore.{card}.{section}.kept", len(items), "sentences", src, "stage 4", "stage4_explore")
        s.add(f"stage4.explore.{card}.reasons_read", doc["source"]["reasons_read"], "sentences", src, "stage 4", "stage4_explore")
        s.add(f"stage4.explore.{card}.cost_usd", doc["source"]["cost_usd"], "USD", src, "stage 4", "stage4_explore")
        s.add(f"stage4.explore.{card}.echo_check_passed", doc["echo_check"]["passed"], "bool", src, "stage 4", "stage4_explore")


def stage4_post_hoc(s):
    src = "results/stage4/duel_post_hoc.json"
    doc = load(src)
    for name, block in doc["row"].items():
        base = f"stage4.posthoc.row.{name}"
        caveat = "stage4_posthoc_floor" if name == "floor_no_llm" else "stage4_posthoc"
        r = block["pooled"]["panel_excluded"]
        s.add(f"{base}.keep_rate", r["keep_rate"], "share of 200 draws", src, "stage 4, post hoc", caveat)
        s.add(f"{base}.keep_rate_ci95", r["keep_rate_ci95"], "share, percentile 95", src, "stage 4, post hoc", caveat)
        s.add(f"{base}.beats_rate", r["beats_rate"], "share of 200 draws", src, "stage 4, post hoc", caveat)
        for field, value in r["counts"].items():
            s.add(f"{base}.count.{field}", value, "draws", src, "stage 4, post hoc", caveat)
    for name, keep in doc["frozen_draw0_keep"].items():
        s.add(f"stage4.posthoc.draw0_keep_at_frozen_fold_seed.{name}", keep, "bool", src, "stage 4, post hoc", "stage4_posthoc")
    for kind, block in doc["unit_intact"].items():
        s.add(f"stage4.posthoc.unit_intact.{kind}.fold_seeds", len(block["fold_seeds"]), "fold seeds", src, "stage 4, post hoc", "stage4_posthoc")
        s.add(f"stage4.posthoc.unit_intact.{kind}.draws_counted_out", block["draws_counted_out"], "draws", src, "stage 4, post hoc", "stage4_posthoc")
        for name, r in block["keep_rate"].items():
            caveat = "stage4_posthoc_floor" if name == "floor_no_llm" else "stage4_posthoc"
            s.add(f"stage4.posthoc.unit_intact.{kind}.{name}.keep_rate_mean", r["mean"], "share of draws, mean over fold seeds", src, "stage 4, post hoc", caveat)
            s.add(f"stage4.posthoc.unit_intact.{kind}.{name}.keep_rate_range", [r["min"], r["max"]], "share of draws, over fold seeds", src, "stage 4, post hoc", caveat)
    for name, d0 in doc["same_sample"]["draw0"].items():
        base = f"stage4.posthoc.same_sample.draw0.{name}"
        s.add(f"{base}.fold_seeds", d0["fold_seeds"], "fold seeds", src, "stage 4, post hoc", "stage4_posthoc")
        s.add(f"{base}.pooled_keep_share", d0["pooled_keep_share"], "share of fold seeds", src, "stage 4, post hoc", "stage4_posthoc")
        s.add(f"{base}.mean_improvement_range", d0["mean_improvement_range"], "log loss, R1 minus panel", src, "stage 4, post hoc", "stage4_posthoc")
        for item, share in d0["item_keep_share"].items():
            s.add(f"{base}.{item}.keep_share", share, "share of fold seeds", src, "stage 4, post hoc", "stage4_posthoc")
    for name, f in doc["same_sample"]["all_draws"].items():
        base = f"stage4.posthoc.same_sample.all_draws.{name}"
        s.add(f"{base}.fold_seeds_per_draw", f["fold_seeds_per_draw"], "fold seeds", src, "stage 4, post hoc", "stage4_posthoc")
        for field in ("mean_keep", "share_draws_always_keep", "share_draws_never_keep", "share_draws_decision_changes", "share_draws_between_25_75"):
            s.add(f"{base}.{field}", f[field], "share of 200 draws", src, "stage 4, post hoc", "stage4_posthoc")


def stage4_demo8(s):
    src = "config/panel_value_policy.json"
    doc = load(src)
    s.add("stage4.policy.default", doc["default"], "label", src, "stage 4, post hoc", "stage4_policy")
    s.add("stage4.policy.duel_role", doc["duel_role"], "label", src, "stage 4, post hoc", "stage4_policy")
    s.add("stage4.policy.post_hoc", doc["post_hoc"], "bool", src, "stage 4, post hoc", "stage4_policy")
    s.add("stage4.policy.frozen_label_in_records", doc["frozen_label"], "label", src, "stage 4, post hoc", "stage4_duel_label")
    src = "results/stage3/option_ranking.json"
    panel = load(src)["sets"]["merged_coffee_15"]["groups"]["overall"]["estimators"]["panel_C1"]
    for band in ("1_to_3pp", "3_to_5pp"):
        value, n = panel[f"estimated_gap|{band}|accuracy"]["value"], panel[f"estimated_gap|{band}|n_pairs"]["value"]
        s.add(f"stage4.pair_accuracy.{band}.pairs_right", round(value * n), "pairs", src, "stage 4", "stage4_pair")
        s.add(f"stage4.pair_accuracy.{band}.pairs", n, "pairs", src, "stage 4", "stage4_pair")
    src = "results/stage4/demo8/action.json"
    doc = load(src)
    for row in doc["action"]["rows"]:
        s.add(f"stage4.demo8.action.{row['card']}", row["label"], "label", src, "stage 4", "stage4_action")
    s.add("stage4.demo8.action.drop_gap_pp", doc["action"]["drop_gap_pp"], "pp, panel internal", src, "stage 4", "stage4_action")
    for row in doc["action"]["threshold_sensitivity"]:
        s.add(f"stage4.demo8.threshold.{row['limit_pp']:g}pp.drop_proposed", row["drop_proposed"], "cards", src, "stage 4", "stage4_action")
    src = "results/stage4/demo8/real_results.json"
    doc = load(src)
    base = "stage4.demo8.ingest"
    s.add(f"{base}.source_label", doc["source_label"], "label", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.panel_model", doc["panel"]["model"], "label", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.panel_condition", doc["panel"]["condition"], "label", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.is_real_concept_survey", doc["is_real_concept_survey"], "bool", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.concept_duel", doc["concept_duel"], "label", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.n_respondents", doc["n_respondents"], "respondents", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.report_status", doc["report_status"], "label", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.panel_values_in_report", doc["panel_values_in_report"], "bool", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.duel_outcome", doc["duel_outcome"], "label", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.fold_kind", doc["fold_kind"], "label", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.counts_toward_run", doc["health_check"]["counts_toward_run"], "bool", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.pooled.mean_improvement", doc["anchors"]["pooled"]["mean_improvement"], "log loss, R1 minus panel", src, "stage 4", "stage4_ingest")
    s.add(f"{base}.pooled.interval", doc["anchors"]["pooled"]["interval"], "log loss, t interval over 5 folds", src, "stage 4", "stage4_ingest")
    for card in ("A", "B", "C"):
        src = f"results/explore/demo8/{card}.json"
        doc = load(src)
        for section, items in doc["sections"].items():
            s.add(f"stage4.explore8.{card}.{section}.kept", len(items), "sentences", src, "stage 4", "stage4_explore")
        s.add(f"stage4.explore8.{card}.calls_this_card", doc["source"]["calls_this_card"], "calls", src, "stage 4", "stage4_explore")
        s.add(f"stage4.explore8.{card}.echo_check_passed", doc["echo_check"]["passed"], "bool", src, "stage 4", "stage4_explore")
    src = "results/stage4/explore_filter_scenarios.json"
    doc = load(src)
    s.add("stage4.explore_filter.total", doc["total"], "scenario by section", src, "stage 4", "stage4_filter")
    s.add("stage4.explore_filter.passed", doc["passed"], "scenario by section", src, "stage 4", "stage4_filter")
    for tag, src in (("first_batch", "results/stage4/scenarios/results.json"), ("rerun_of_crashed", "results/stage4/scenarios/results_rerun7.json")):
        rows = load(src)["results"]
        s.add(f"stage4.scenarios.{tag}.runs", len(rows), "runs", src, "stage 4", "stage4_scenarios")
        s.add(f"stage4.scenarios.{tag}.passed", sum(bool(r["passed"]) for r in rows), "runs", src, "stage 4", "stage4_scenarios")
        s.add(f"stage4.scenarios.{tag}.cost_usd", round(sum(r["cost_usd"] for r in rows), 6), "USD", src, "stage 4", "spend")


def call_order(s):
    src = "results/fix_stage/call_order.json"
    doc = load(src)
    for row in doc["stages"]:
        base = f"order.{row['stage'].replace(' ', '_')}"
        s.add(f"{base}.freeze_commit_date", row["freeze_commit"]["committer_date"], "time", src, row["stage"], "order")
        s.add(f"{base}.first_answer_utc", row["first_answer_utc"], "time", src, row["stage"], "order")
        s.add(f"{base}.seconds_from_freeze_to_first_answer", row["seconds_from_freeze_to_first_answer"], "seconds", src, row["stage"], "order")


def tests(s):
    src = "results/fix_stage/pytest_summary.json"
    doc = load(src)
    s.add("tests.passed", doc["passed"], "tests", src, "fix stage", "tests")
    s.add("tests.failed", doc["failed"], "tests", src, "fix stage", "tests")
    s.add("tests.skipped", doc["skipped"], "tests", src, "fix stage", "tests")


def record_tests():
    """Run the whole test suite with this interpreter and keep the last line. numbers_sheet.json itself is checked by a test, so build it first."""
    out = subprocess.run([sys.executable, "-m", "pytest", str(paths.ROOT / "tests"), "-q", "--no-header", "-p", "no:cacheprovider"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [line for line in out.stdout.splitlines() if line.strip()][-1]
    counts = {name: int(m.group(1)) if (m := re.search(rf"(\d+) {name}", tail)) else 0 for name in ("passed", "failed", "skipped")}
    doc = {"last_line": tail, **counts}
    (paths.RESULTS / "fix_stage" / "pytest_summary.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(tail)
    return doc


def build():
    s = Sheet()
    for fn in (gate, stage2, verdicts, ranking, demo, costs, spend, scenarios, attacks, call_order, tests, stage4_allocation, stage4_flags, stage4_duel, stage4_product, stage4_post_hoc, stage4_demo8):
        fn(s)
    return {
        "note": "Every number a deliverable may cite, generated by src/make_numbers_sheet.py from the source files named per entry. Cite the caveat with the number. A number absent here has no source in the repo.",
        "entries": len(s.rows),
        "rows": s.rows,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--record-tests", action="store_true")
    args = parser.parse_args()
    if args.record_tests:
        record_tests()
    doc = build()
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"entries": doc["entries"], "file": rel(OUT)}))


if __name__ == "__main__":
    main()
