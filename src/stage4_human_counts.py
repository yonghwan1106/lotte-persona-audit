"""results/stage4/human2_call_counts.json: how many answers of the person approved run were new and how many came from the cache.

Reads the saved run state and the call log under runs/, which git ignores, and writes counts only. No API call. No code, persona or answer leaves runs/.

  python src/stage4_human_counts.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lotte_audit import paths  # noqa: E402

RUN = "human2"
STATE = paths.ROOT / "runs" / "stage4" / "saved" / f"{RUN}_ctx.json"
LOG = paths.ROOT / "runs" / "stage4" / "logs" / "panel_calls.jsonl"
OUT = paths.RESULTS / "stage4" / f"{RUN}_call_counts.json"


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    stages = state["run_doc"]["stages"]
    # The full stage reads the pilot's answers back from the cache, so a stage's cached count is not the number of answers from earlier runs.
    called = sum(s["counts"]["called"] for s in stages)
    cached = state["plan"]["calls_total"] - called
    rows = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    statuses = Counter(r["status"] for r in rows)
    cost = round(sum(r.get("cost_usd") or 0 for r in rows), 6)
    if cost != state["run_doc"]["spent_this_run_usd"]:
        raise SystemExit("the call log holds more than this run")
    if called != statuses["ok"]:
        raise SystemExit("new answers differ from the answered rows of the call log")
    doc = {
        "note": "Counts only, from runs/ which git ignores. An answer already in the cache of an earlier run is not called again, so the panel cost of this run is not the cost of calling the whole plan.",
        "run_id": RUN,
        "plan_answers": state["plan"]["calls_total"],
        "n_personas": state["plan"]["n_personas"],
        "cards": state["plan"]["cards"],
        "models": state["plan"]["models"],
        "plan_expected_usd": state["plan"]["expected_usd"],
        "new_answers": called,
        "answers_from_cache": cached,
        "log_rows": len(rows),
        "log_rows_by_status": dict(sorted(statuses.items())),
        "panel_cost_usd_from_log": cost,
        "complete": state["run_doc"]["complete"],
        "codes_failed": state["run_doc"]["codes_failed"],
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(doc, ensure_ascii=False))


if __name__ == "__main__":
    main()
