"""Copy aggregates from results/ and config/ into web/data. No API call. Run from anywhere.

  python web/scripts/build_data.py              write web/data from this checkout, then check it
  python web/scripts/build_data.py --ref public write web/data from the files of that branch, then check it
  python web/scripts/build_data.py --check      check web/data and web/.next only, write nothing

What leaves results/ is chosen field by field below. Nothing is read from runs/ or data/ for output.
The check reads the respondent codes and persona sentences in the ignored runs/ folder to prove that none of them
reached web/data or the build, and prints only counts.
"""
import argparse
import csv
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
REPO = WEB.parent
OUT = WEB / "data"
RESULTS = REPO / "results"
AGENT_DEMO = RESULTS / "agent" / "demo5"
FINAL_DEMO = RESULTS / "stage4" / "demo8"
STAGE4 = RESULTS / "stage4"
EXPLORE = RESULTS / "explore" / "demo8"
# Terra's gate run, from the first to the last answered call in the ignored call log. Not in the numbers sheet: the
# summary file's wall_clock_s for Terra also holds the failed attempts from before the account was funded. check() compares
# this value with the log when the log is present.
GATE_TERRA_SECONDS_FROM_CALL_LOG = 208.4
HUMAN = STAGE4 / "human2"
FIX = RESULTS / "fix_stage"
USED = {}
REF = None


def read_bytes(path):
    """A source file from the working tree, or from the branch named by --ref. Its hash goes into provenance."""
    if REF:
        rel = path.relative_to(REPO).as_posix()
        data = subprocess.run(["git", "-C", str(REPO), "show", f"{REF}:{rel}"], capture_output=True, check=True).stdout
    else:
        data = path.read_bytes()
    USED[path] = hashlib.sha256(data).hexdigest()
    return data


def read_text(path):
    return read_bytes(path).decode("utf-8")


def read_json(path):
    return json.loads(read_text(path))


def read_jsonl(path):
    return [json.loads(line) for line in read_text(path).splitlines() if line.strip()]


def write(name, doc):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def build_numbers():
    sheet = read_json(RESULTS / "numbers_sheet.json")
    caveats, index, rows = [], {}, {}
    for row in sheet["rows"]:
        caveat = row["caveat"]
        if caveat not in index:
            index[caveat] = len(caveats)
            caveats.append(caveat)
        if row["key"] in rows:
            raise SystemExit("duplicate key in the numbers sheet")
        rows[row["key"]] = {"value": row["value"], "unit": row["unit"], "source": row["source"], "stage": row["stage"], "caveat": index[caveat]}
    if len(rows) != sheet["entries"]:
        raise SystemExit("row count differs from the sheet's own count")
    return {"note": sheet["note"], "entries": sheet["entries"], "caveats": caveats, "rows": rows}


def plan_summary(plan):
    keep = ("cards", "models", "n_personas", "c0", "pilot", "calls_by_model", "calls_total", "expected_by_model", "expected_usd", "cost_cap_usd", "worst_case_every_call_at_output_cap_usd", "estimated_minutes", "formula", "plan_hash")
    return {k: plan[k] for k in keep}


def compact_step(row, t0):
    """One transcript row with only the fields the replay shows. The pilot's value and the local report path stay out."""
    step = {"seconds": round(row["t"] - t0, 1), "event": row["event"]}
    event = row["event"]
    tool = row.get("tool")
    if tool:
        step["tool"] = tool
    if event == "user_message":
        step["text"] = row["text"]
    elif event == "intake_check":
        step["detail"] = {k: row[k] for k in ("tripwire", "classes", "by", "ask_human")}
    elif event == "tool_call":
        args = row.get("args") or {}
        if tool == "validate_card":
            step["detail"] = {"card_id": args.get("card_id")}
        elif tool == "plan_run":
            step["detail"] = args
        elif tool == "run_panel":
            step["detail"] = {"plan_hash": args.get("plan_hash")}
        elif tool == "explore_card":
            step["detail"] = args
    elif event == "tool_output":
        out = row["output"]
        if tool == "validate_card":
            step["detail"] = {k: out[k] for k in ("status", "card_id", "role", "removed", "excluded", "leading_kept")}
        elif tool == "plan_run":
            step["detail"] = {"status": out["status"], "needs_human_approval": out["needs_human_approval"], "plan": plan_summary(out["plan"])}
        elif tool == "run_panel":
            step["detail"] = {
                "status": out["status"],
                "complete": out["complete"],
                "pilot_passed": out["pilot"]["passed"],
                "pilot_n": out["pilot"]["n"],
                "stages": out["stages"],
                "spent_this_run_usd": out["spent_this_run_usd"],
                "codes_failed": out["codes_failed"],
            }
        elif tool == "diagnose_run":
            step["detail"] = out["summary"]
        elif tool == "decide_verdict":
            step["detail"] = {"status": out["status"], "sentences": len(out["sentences"])}
        elif tool == "allocate_real_sample":
            step["detail"] = {"status": out["status"], "target_segment": out["target_segment"]}
        elif tool == "build_questionnaire":
            step["detail"] = {"status": out["status"], "items": out["items"]}
        elif tool == "write_ledger":
            step["detail"] = {"status": out["status"], "manifest_sha256": out["manifest_sha256"]}
        elif tool == "explore_card":
            # Counts only. The sentences come from the explore files, read in build_stage4.
            step["detail"] = {k: out[k] for k in ("status", "card", "kept", "dropped_by_code", "echo_check_passed")}
    elif event == "approval_requested":
        step["detail"] = {"plan_hash": row["args"]["plan_hash"]}
    elif event in ("approval_recorded", "approval_granted"):
        step["detail"] = {"approver": row["approver"]}
    elif event == "narrator_output":
        step["detail"] = {"accepted": row["accepted"], "reasons": row["reasons"], "sentences": [s["text"] for s in row["sentences"]]}
    elif event == "final":
        step["detail"] = {k: row[k] for k in ("status", "claimed_status", "status_corrected_by_code", "refused_classes", "by", "note", "note_dropped")}
    return step


def build_demo():
    # The verdict and the questionnaire are byte for byte the same in the first demo run and in demo8, the run the page
    # replays. The allocation differs only in the sentence that says what each card is for, which is checked here.
    same = {}
    for name in ("verdict.json", "questionnaire.json"):
        same[name] = read_bytes(AGENT_DEMO / name) == read_bytes(FINAL_DEMO / name)
        if not same[name]:
            raise SystemExit(f"{name} differs between demo5 and demo8")
    verdict = read_json(FINAL_DEMO / "verdict.json")
    allocation = read_json(FINAL_DEMO / "allocation.json")
    first_allocation = read_json(AGENT_DEMO / "allocation.json")
    moved = sorted(k for k in set(allocation) | set(first_allocation) if allocation.get(k) != first_allocation.get(k))
    if moved != ["cards"] or [c["card"] for c in allocation["cards"]] != [c["card"] for c in first_allocation["cards"]]:
        raise SystemExit(f"allocation differs beyond the card sentence: {moved}")
    allocation_note = {"same_numbers_as_results_agent_demo5": True, "only_field_changed": moved}
    questionnaire = read_json(FINAL_DEMO / "questionnaire.json")
    manifest = read_json(FINAL_DEMO / "manifest.json")
    transcript = read_jsonl(FINAL_DEMO / "transcript.jsonl")
    diagnostics = read_json(FINAL_DEMO / "diagnostics.json")
    report = read_text(FINAL_DEMO / "report.md")

    if "internal" in json.dumps(diagnostics["by_model"]) or "t2b" in json.dumps(diagnostics["by_model"]):
        raise SystemExit("demo8 diagnostics hold an absolute value")
    verdict_keys = ("card", "model", "segment", "n", "base_label_v2", "base_by_item", "run_status", "label", "flags", "absolute_shown", "order_allowed")
    rows = [{k: r[k] for k in verdict_keys} for r in verdict["rows"]]

    card_text = {i["id"].split("_", 1)[1]: i["card_text"] for i in questionnaire["items"] if i["kind"] == "concept"}
    cards = []
    for row in transcript:
        if row["event"] == "tool_output" and row.get("tool") == "validate_card":
            out = row["output"]
            cards.append(
                {
                    "id": out["card_id"],
                    "role": out["role"],
                    "attributes": out["attributes"],
                    "price_band": out["price_band"],
                    "alternatives": out["alternatives"],
                    "target_segment": out["target_segment"],
                    "anchor_items": out["anchor_items"],
                    "paraphrase_of": out["paraphrase_of"],
                    "brand_of": out["brand_of"],
                    "text": card_text.get(out["card_id"]),
                }
            )
    t0 = transcript[0]["t"]
    approved = next(r for r in transcript if r["event"] == "approval_recorded")
    at = re.search(r"Approved by: (.+?) at (\S+), plan", report)
    cost = re.search(r"^Cost: (\{.*\})$", report, re.M)
    return {
        "run_id": manifest["run_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "plan_hash": manifest["plan_hash"],
        "rule_version": manifest["rule_version"],
        "models": manifest["models"],
        "versions": manifest["versions"],
        "same_bytes_as_results_agent_demo5": same,
        "allocation_compared_with_demo5": allocation_note,
        "approval": {"approver": approved["approver"], "at": at.group(2) if at else None},
        "cost_of_this_rerun": json.loads(cost.group(1)) if cost else None,
        "cards": cards,
        "steps": [compact_step(r, t0) for r in transcript],
        "verdict": {"rows": rows, "sentences": verdict["sentences"], "any_order_allowed": verdict["any_order_allowed"], "raw_panel_number_as_market_number": verdict["raw_panel_number_as_market_number"], "header": verdict["header"]},
        "allocation": allocation,
        "questionnaire": {
            "intro": questionnaire["intro"],
            "anchor_note": questionnaire["anchor_note"],
            "fieldwork_rules": questionnaire["fieldwork_rules"],
            "benchmark_note": questionnaire["benchmark_note"],
            "sent": questionnaire["sent"],
            "items": [{"id": i["id"], "kind": i["kind"]} for i in questionnaire["items"]],
        },
    }


def build_stage4():
    """The action table, the exploration sample, the ingest record and the rule's bar. Chosen field by field."""
    action_doc = read_json(FINAL_DEMO / "action.json")
    action, detectable = action_doc["action"], action_doc["detectable"]
    sheet = {r["key"]: r["value"] for r in read_json(RESULTS / "numbers_sheet.json")["rows"]}
    for row in action["rows"]:
        if sheet[f"stage4.demo8.action.{row['card']}"] != row["label"]:
            raise SystemExit("action table differs from the numbers sheet")

    cards = {}
    marking = None
    for card in ("A", "B", "C"):
        doc = read_json(EXPLORE / f"{card}.json")
        if doc["status"] != "done" or not doc["echo_check"]["passed"]:
            raise SystemExit(f"exploration of card {card} did not pass its echo check")
        for name, sentences in doc["sections"].items():
            for text in sentences:
                if not text.startswith("\uac00\uc124: ") or re.search(r"\d", text):
                    raise SystemExit(f"exploration sentence out of form in card {card}, section {name}")
        marking = doc["marking"]
        cards[card] = {
            "sections": doc["sections"],
            "reasons_read": doc["source"]["reasons_read"],
            "model_of_reasons": doc["source"]["model_of_reasons"],
            "calls_this_card": doc["source"]["calls_this_card"],
            "dropped_by_code": doc["dropped_by_code"],
            "echo": {k: doc["echo_check"][k] for k in ("sentences_checked", "personas_compared", "reasons_compared", "persona_echo", "reason_echo", "passed")},
        }

    real = read_json(FINAL_DEMO / "real_results.json")
    # Per item results stay out: the same respondents flip with the fold seed, so a per item keep is not quoted.
    real_keys = ("source_label", "is_real_concept_survey", "panel", "n_respondents", "anchors_used", "concepts_used", "folds", "fold_kind", "metric", "duel_outcome", "health_check", "panel_values_in_report", "panel_values_may_enter", "report_status", "policy", "concept_duel", "duel_grade", "seed_runs", "seed_runs_failed", "approver", "approver_note", "lines")
    duel = read_json(STAGE4 / "duel_validity.json")
    sensitivity = read_json(STAGE4 / "duel_seed_sensitivity.json")
    allocation = read_json(STAGE4 / "allocation.json")
    ledger = read_jsonl(STAGE4 / "ledger.jsonl")
    ingest_rows = [r for r in ledger if r.get("kind") == "real_results" and r.get("run_id") == FINAL_DEMO.name]
    if len(ingest_rows) != 1:
        raise SystemExit("expected one real_results row of the final demo in the stage 4 ledger")
    policy = read_json(REPO / "config" / "panel_value_policy.json")
    flags = read_json(STAGE4 / "flags.json")["signals"]
    gate = read_json(RESULTS / "gate_run_summary.json")
    luna, terra = gate["models"]["gpt-6-luna"], gate["models"]["gpt-6.1-terra"]
    if abs(gate["gate_total_usd"] - sheet["spend.gate"]) > 1e-9:
        raise SystemExit("gate spend differs from the numbers sheet")
    return {
        "action": {k: action[k] for k in ("rows", "order", "order_hidden_pairs", "order_notes", "notes", "drop_gap_pp", "threshold_sensitivity")},
        "detectable": detectable,
        "explore": {"marking": marking, "cards": cards},
        "real_results": {k: real[k] for k in real_keys},
        "ledger": {"rows": len(ledger), "human_decision": ingest_rows[0]["human_decision"], "approver": ingest_rows[0]["approver"]},
        "policy": {k: policy[k] for k in ("decided_on", "post_hoc", "default", "duel_role", "fold_kind_counted", "consecutive_keeps_required", "frozen_label", "frozen_label_caveat")},
        "flags_random_95": {name: signal["overlap_top9"]["random_95"] for name, signal in flags.items()},
        "gate_audit": {
            "calls_answered": {"terra": terra["statuses"]["ok"], "luna": luna["statuses"]["ok"]},
            "seconds": {"terra_from_call_log": GATE_TERRA_SECONDS_FROM_CALL_LOG, "luna": luna["wall_clock_s"]},
            "terra_wall_clock_in_summary_with_failed_attempts": terra["wall_clock_s"],
        },
        "duel_bar": duel["bar"],
        "duel_reading": duel["reading"],
        "seed_note": sensitivity["note"],
        "allocation": {"cell_names": allocation["cell_names"], "reference_sources": allocation["reference_sources"]},
    }


def build_human_run():
    """The small run a person approved at a terminal. Chosen field by field; the explore sentences and diagnostics stay in results/."""
    action = read_json(HUMAN / "action.json")["action"]
    manifest = read_json(HUMAN / "manifest.json")
    counts = read_json(STAGE4 / "human2_call_counts.json")
    sheet = {r["key"]: r["value"] for r in read_json(RESULTS / "numbers_sheet.json")["rows"]}
    rows = [r for r in read_jsonl(STAGE4 / "ledger.jsonl") if r.get("run_id") == HUMAN.name and r.get("approval")]
    if len(rows) != 1:
        raise SystemExit("expected one ledger row of the person approved run")
    row = rows[0]
    if row["manifest_sha256"] != manifest["manifest_sha256"] or row["approval"]["channel"] != "terminal":
        raise SystemExit("the ledger row and the manifest of the person approved run differ")
    # The page describes A, B and C with the demo's cards. The two runs hold a different set of cards in all, so their card hashes differ.
    def concept_text(run):
        return {i["id"]: i["card_text"] for i in read_json(run / "questionnaire.json")["items"] if i["kind"] == "concept"}
    shown, demo_cards = concept_text(HUMAN), concept_text(FINAL_DEMO)
    if not shown or any(demo_cards.get(k) != v for k, v in shown.items()):
        raise SystemExit("the person approved run and the demo differ in the text of a candidate card")
    for item in action["rows"]:
        if sheet[f"stage4.human2.action.{item['card']}"] != item["label"]:
            raise SystemExit("human run action table differs from the numbers sheet")
    report = read_text(HUMAN / "report.md")
    if "\uc774 \uc2b9\uc778\uc740 \ud130\ubbf8\ub110\uc5d0\uc11c \uc0ac\ub78c\uc774 \uc774\ub984\uacfc \uacc4\ud68d \ud574\uc2dc\ub97c \uc785\ub825\ud55c \uae30\ub85d\uc785\ub2c8\ub2e4" not in report:
        raise SystemExit("the report of the person approved run lost its approval sentence")
    return {
        "run_id": manifest["run_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "plan_hash": manifest["plan_hash"],
        "models": counts["models"],
        "cards": counts["cards"],
        "n_personas": counts["n_personas"],
        "approval": {k: row["approval"][k] for k in ("approver", "note", "at", "channel", "cost_cap_usd")},
        "action": {k: action[k] for k in ("rows", "order", "order_hidden_pairs", "notes", "drop_gap_pp", "threshold_sensitivity")},
        "human_decision": row["human_decision"],
        "real_results": row["real_results"],
    }


TABLE_ROW = re.compile(r"^\| (\w+) \| (\w+) \| (\d+) \| (\d+) \| ([0-9.]+) \|")


def scenario_table(path):
    rows = []
    for line in read_text(path).splitlines():
        m = TABLE_ROW.match(line)
        if m:
            rows.append({"scenario": m.group(1), "mode": m.group(2), "runs": int(m.group(3)), "passed": int(m.group(4)), "cost_usd": float(m.group(5))})
    return rows


def build_attacks():
    record = read_json(FIX / "wf7_attack_record.json")
    live = read_json(FIX / "attack_replay_live.json")
    offline = read_json(FIX / "attack_replay_offline.json")
    probe = read_json(FIX / "decisions_store_probe.json")
    outcome_keys = ("status", "claimed_status", "by", "refused_classes", "note", "note_dropped")
    return {
        "wf7": {"spend_usd": record["spend_usd"], "live_runs": record["live_runs"], "live_outcomes": record["live_outcomes"], "offline_guard_variants": record["offline_guard_variants"], "probe": record["probe"], "note": record["note"]},
        "replay_live": {
            "total": live["total"],
            "still_passing": live["still_passing"],
            "cost_usd": live["cost_usd"],
            "rows": [{"id": r["id"], "kind": r["kind"], "previously_got_through": r["previously_got_through"], "still_passes": r["still_passes"], "why": r["why"], "outcome": {k: r["outcome"][k] for k in outcome_keys}, "cost_usd": r["cost_usd"]} for r in live["rows"]],
        },
        "replay_offline": offline,
        "store_probe": probe,
        "scenarios": {
            "first_batch": scenario_table(RESULTS / "agent" / "scenarios" / "first_batch" / "results.md"),
            "agent_final": scenario_table(RESULTS / "agent" / "scenarios" / "results.md"),
            "fix_stage": scenario_table(FIX / "scenarios" / "results.md"),
        },
    }


def build_intake():
    text = read_json(REPO / "config" / "agent_text.json")
    run = read_json(REPO / "config" / "agent_run.json")
    refusal, rules = text["refusal"], text["card_rules"]
    return {
        "from": ["config/agent_text.json", "config/agent_run.json"],
        "classes": refusal["classes"],
        "messages": refusal["messages"],
        "request_patterns": refusal["request_patterns"],
        "card_request_patterns": refusal["card_request_patterns"],
        "injection_patterns": rules["injection_patterns"],
        "real_brand_patterns": rules["real_brand_patterns"],
        "alcohol_patterns": rules["alcohol_patterns"],
        "under19_patterns": rules["under19_patterns"],
        "image_patterns": rules["image_patterns"],
        "leading_fact_patterns": rules["leading_fact_patterns"],
        "pricing_source": run["pricing_source"],
        "models": {"main": run["models"]["main"], "cheap": run["models"]["cheap"]},
        "planning": run["planning"],
        "concurrency": run["limits"]["concurrency"],
        "panel": {"n_personas": run["panel"]["n_personas"], "c0_model": run["panel"]["c0"]["model"], "c0_calls_per_card": run["panel"]["c0"]["calls_per_card"]},
    }


def build_controls():
    """Labels of the real answer control per item. The four slots are one result, which is checked here."""
    doc = read_json(RESULTS / "verdict_v3" / "verdict_v3.json")
    labels = {}
    for row in doc["real_answers"]["rows"]:
        entry = {"v1": row["v1"], "v2": row["v2"], "v3": row["v3"]}
        if labels.setdefault(row["item"], entry) != entry:
            raise SystemExit("real answer control rows differ between slots")
    return {"real_answer_labels": labels, "note": doc["real_answers"]["note"]}


# Short names of my own for the A15 options on the chart. The survey's wording stays off the site.
RANK_LABELS = {
    "1": "과일 주스", "2": "저과즙 음료", "3": "흰우유", "4": "가공우유", "5": "발효유",
    "6": "두유", "7": "가당 탄산", "8": "제로 탄산", "9": "이온 음료", "10": "차",
    "11": "기능성 음료", "12": "탄산수", "13+14": "커피", "15": "전문점 음료", "17": "물 외 안 마심",
}
AGE_LABELS = ["19~29세", "30~39세", "40~49세", "50~59세", "60~69세", "70세 이상"]


def build_viz():
    """Aggregates the charts need that the numbers sheet does not hold. Group means and shares only, checked against the sheet."""
    sheet = {r["key"]: r["value"] for r in read_json(RESULTS / "numbers_sheet.json")["rows"]}

    # Age band lines: the gate run's 300 person panel against the whole test truth.
    age = {}
    for slug, model in (("terra", "gpt-6.1-terra"), ("luna", "gpt-6-luna")):
        doc = read_json(RESULTS / "gate" / f"gate_explore_{model}.json")
        for condition in ("C1", "C2"):
            for item, block in doc["conditions"][condition]["items"].items():
                bands = block["by_age_band_pct"]
                if len(bands) != len(AGE_LABELS):
                    raise SystemExit("unexpected age bands in the gate exploration")
                rows = [{"band": label, "real": bands[key]["real"], "panel": bands[key]["panel"]} for label, key in zip(AGE_LABELS, sorted(bands))]
                age.setdefault(item, {})[f"{slug}_{condition}"] = {"rows": rows, "cell_pearson_r": block["cell_pearson_r"]}

    # Slope chart: shares of the 15 categories, real outside the 1000 panel against Terra C2, overall.
    ranking = read_json(RESULTS / "stage3" / "option_ranking.json")
    overall = ranking["sets"]["merged_coffee_15"]["groups"]["overall"]["estimators"]["panel_C2"]
    panel_shares = overall["_shares_pct"]
    truth = ranking["truth_shares_pct"]["overall"]
    real_shares = {key: (truth["13"] + truth["14"] if key == "13+14" else truth[key]) for key in panel_shares}
    for key, value in panel_shares.items():
        if abs(value - real_shares[key] - overall[f"bias|{key}"]["value"]) > 0.02:
            raise SystemExit(f"option {key}: panel minus truth differs from the stored bias")
    order_real = sorted(real_shares, key=lambda k: -real_shares[k])
    order_panel = sorted(panel_shares, key=lambda k: -panel_shares[k])
    categories = [{"id": k, "label": RANK_LABELS[k], "real_share": round(real_shares[k], 2), "panel_share": panel_shares[k], "real_rank": order_real.index(k) + 1, "panel_rank": order_panel.index(k) + 1} for k in order_real]

    # Gender gaps: the panel's own interval is in the stage 2 score file, not in the sheet.
    main = read_json(RESULTS / "main" / "main_score.json")["stereotypes"]
    gender = {}
    for item, block in main.items():
        by_panel = block["by_panel"]["gpt-6.1-terra|C2"]
        if by_panel["gender_gap_pp"] != sheet[f"stage2.stereotype.{item}.terra_C2.gender_gap_pp"]:
            raise SystemExit("gender gap differs from the numbers sheet")
        gender[item] = {"panel_ci95": by_panel["gender_gap_ci95"]}

    return {"age_bands": age, "ranking": categories, "gender": gender}


def git_output(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def build_provenance():
    files = {path.relative_to(REPO).as_posix(): USED[path] for path in sorted(USED)}
    return {
        "note": "Written by web/scripts/build_data.py. Each file below was read from this repo at this commit.",
        "commit": git_output("rev-parse", REF or "HEAD"),
        "branch": REF or git_output("rev-parse", "--abbrev-ref", "HEAD"),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "files": files,
    }


def scan_targets():
    paths = sorted(OUT.glob("*.json"))
    build = WEB / ".next"
    if build.exists():
        for folder in ("server", "static"):
            for path in (build / folder).rglob("*"):
                if path.is_file() and path.suffix in (".js", ".json", ".html", ".rsc", ".txt", ".map"):
                    paths.append(path)
    return paths


def collect_strings(node, out):
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            collect_strings(value, out)
    elif isinstance(node, list):
        for value in node:
            collect_strings(value, out)


def gate_seconds_check():
    """Terra's seconds against the ignored call log, when it is here. Prints the two numbers only."""
    log = REPO / "runs" / "gate" / "logs" / "calls.jsonl"
    if not log.exists():
        return
    stamps = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row["model"] == "gpt-6.1-terra" and row["status"] == "ok":
                stamps.append(row["ts"])
    span = round(max(stamps) - min(stamps), 1)
    print(json.dumps({"gate_terra_seconds_log": span, "gate_terra_seconds_page": GATE_TERRA_SECONDS_FROM_CALL_LOG}))
    if span != GATE_TERRA_SECONDS_FROM_CALL_LOG:
        raise SystemExit("gate seconds differ from the call log")


def forbidden_material():
    """Codes and persona sentences from the ignored folder. Held in memory and never printed."""
    codes = set()
    for name in ("gate", "main", "stage3"):
        key = REPO / "runs" / name / "key.csv"
        if key.exists():
            # By column name: the three files do not put the code in the same column.
            with key.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    codes.update(row[col] for col in ("code", "gate_code") if row.get(col))
    sentences = set()
    personas = REPO / "runs" / "main" / "inputs" / "personas.jsonl"
    if personas.exists():
        for line in personas.read_text(encoding="utf-8").splitlines():
            if line.strip():
                found = []
                collect_strings(json.loads(line), found)
                sentences.update(s for s in found if len(s) >= 40)
    return codes, sentences


def check():
    gate_seconds_check()
    codes, sentences = forbidden_material()
    token = re.compile(r"[A-Z0-9]{8}")
    findings = {"files": 0, "code_hits": 0, "persona_hits": 0, "key_shaped": 0, "local_path": 0, "brand_card": 0, "microdata_cols": 0}
    # The lookbehind keeps out words that merely end in sk, such as a minified task- or disk- name.
    key_shape = re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}")
    for path in scan_targets():
        text = path.read_text(encoding="utf-8", errors="ignore")
        findings["files"] += 1
        hits = sum(1 for t in set(token.findall(text)) if t in codes)
        findings["code_hits"] += hits
        persona_hits = sum(1 for s in sentences if s in text)
        findings["persona_hits"] += persona_hits
        if key_shape.search(text):
            findings["key_shaped"] += 1
        if str(path).startswith(str(OUT)) and ("C:\\\\Users" in text or "C:/Users" in text):
            findings["local_path"] += 1
        if "\uce60\uc131\uc0ac\uc774\ub2e4" in text:
            findings["brand_card"] += 1
        if str(path).startswith(str(OUT)) and ("row_index" in text or "panel_weight" in text or "psfwt_row" in text or "respondent_id" in text):
            findings["microdata_cols"] += 1
    print(json.dumps({"codes_known": len(codes), "persona_sentences_known": len(sentences), **findings}))
    bad = [k for k in findings if k != "files" and findings[k]]
    if bad:
        raise SystemExit(f"leak check failed: {bad}")
    print("leak check ok")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--ref", help="read the source files from this branch instead of the working tree")
    args = parser.parse_args()
    if not args.check:
        global REF
        REF = args.ref
        write("numbers.json", build_numbers())
        write("demo.json", build_demo())
        write("attacks.json", build_attacks())
        write("intake.json", build_intake())
        write("controls.json", build_controls())
        write("stage4.json", {**build_stage4(), "human_run": build_human_run()})
        write("viz.json", build_viz())
        write("provenance.json", build_provenance())
        for path in sorted(OUT.glob("*.json")):
            print(path.name, path.stat().st_size)
    check()


if __name__ == "__main__":
    sys.exit(main())
