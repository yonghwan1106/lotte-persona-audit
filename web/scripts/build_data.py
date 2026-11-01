"""Copy aggregates from results/ and config/ into web/data. No API call. Run from anywhere.

  python web/scripts/build_data.py              write web/data from this checkout, then check it
  python web/scripts/build_data.py --ref public write web/data from the files of that branch, then check it
  python web/scripts/build_data.py --check      check web/data and web/.next only, write nothing

What leaves results/ is chosen field by field below. Nothing is read from runs/ or data/ for output.
The check reads the respondent codes and persona sentences in the ignored runs/ folder to prove that none of them
reached web/data or the build, and prints only counts.
"""
import argparse
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
FINAL_DEMO = RESULTS / "stage4" / "demo7"
STAGE4 = RESULTS / "stage4"
EXPLORE = RESULTS / "explore" / "demo7"
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
    # These three are byte for byte the same in the first demo run and in demo7, which is the run the page replays.
    same = {}
    for name in ("verdict.json", "allocation.json", "questionnaire.json"):
        same[name] = read_bytes(AGENT_DEMO / name) == read_bytes(FINAL_DEMO / name)
        if not same[name]:
            raise SystemExit(f"{name} differs between demo5 and demo7")
    verdict = read_json(FINAL_DEMO / "verdict.json")
    allocation = read_json(FINAL_DEMO / "allocation.json")
    questionnaire = read_json(FINAL_DEMO / "questionnaire.json")
    manifest = read_json(FINAL_DEMO / "manifest.json")
    transcript = read_jsonl(FINAL_DEMO / "transcript.jsonl")
    diagnostics = read_json(FINAL_DEMO / "diagnostics.json")
    report = read_text(FINAL_DEMO / "report.md")

    if "internal" in json.dumps(diagnostics["by_model"]) or "t2b" in json.dumps(diagnostics["by_model"]):
        raise SystemExit("demo7 diagnostics hold an absolute value")
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
        if sheet[f"stage4.demo7.action.{row['card']}"] != row["label"]:
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
            "cost_usd": doc["source"]["cost_usd"],
            "dropped_by_code": doc["dropped_by_code"],
            "echo": {k: doc["echo_check"][k] for k in ("sentences_checked", "personas_compared", "reasons_compared", "persona_echo", "reason_echo", "passed")},
        }

    real = read_json(FINAL_DEMO / "real_results.json")
    real_keys = ("source_label", "is_real_concept_survey", "n_respondents", "anchors_used", "concepts_used", "folds", "metric", "decision", "anchors", "concept_duel", "duel_grade", "seed_runs", "seed_runs_failed", "approver", "approver_note", "lines")
    duel = read_json(STAGE4 / "duel_validity.json")
    sensitivity = read_json(STAGE4 / "duel_seed_sensitivity.json")
    allocation = read_json(STAGE4 / "allocation.json")
    ledger = read_jsonl(STAGE4 / "ledger.jsonl")
    ingest_rows = [r for r in ledger if r.get("kind") == "real_results"]
    if len(ingest_rows) != 1:
        raise SystemExit("expected one real_results row in the stage 4 ledger")
    return {
        "action": {k: action[k] for k in ("rows", "order", "order_hidden_pairs", "notes", "drop_gap_pp")},
        "detectable": detectable,
        "explore": {"marking": marking, "cards": cards},
        "real_results": {k: real[k] for k in real_keys},
        "ledger": {"rows": len(ledger), "human_decision": ingest_rows[0]["human_decision"], "approver": ingest_rows[0]["approver"]},
        "duel_bar": duel["bar"],
        "duel_reading": duel["reading"],
        "seed_note": sensitivity["note"],
        "allocation": {"cell_names": allocation["cell_names"], "reference_sources": allocation["reference_sources"]},
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


def forbidden_material():
    """Codes and persona sentences from the ignored folder. Held in memory and never printed."""
    codes = set()
    for name in ("gate", "main", "stage3"):
        key = REPO / "runs" / name / "key.csv"
        if key.exists():
            for line in key.read_text(encoding="utf-8").splitlines()[1:]:
                parts = line.split(",")
                if len(parts) > 1:
                    codes.add(parts[1])
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
        write("stage4.json", build_stage4())
        write("provenance.json", build_provenance())
        for path in sorted(OUT.glob("*.json")):
            print(path.name, path.stat().st_size)
    check()


if __name__ == "__main__":
    sys.exit(main())
