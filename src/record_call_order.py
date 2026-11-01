"""results/fix_stage/call_order.json: when each stage froze and when its first and last answers came, as aggregates.

The call logs stay under runs/ and hold respondent codes, so a public reader cannot see them. This keeps only the times and the commit
subject and date, which survive a history rewrite, so the freeze before first call order stays checkable without any row level file.
"""
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lotte_audit import paths  # noqa: E402

OUT = paths.RESULTS / "fix_stage" / "call_order.json"
STAGES = (
    ("gate", "Freeze the gate run config and prompt before the first persona call", "Lower the gate budget to USD 8 before the first answer", "runs/gate/logs/calls.jsonl", None),
    ("stage 2", "Freeze the main stage plan before its first call", None, "runs/main/logs/calls.jsonl", None),
    ("stage 3", "Freeze the stage 3 plan before its first call", None, "runs/stage3/logs/calls.jsonl", None),
    ("agent demo", "Freeze the audit agent's concept demo plan before its first demo call", None, "runs/agent/logs/panel_calls.jsonl", ("A", "A_para", "A_brand", "B", "C", "N")),
)


def iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="seconds")


def commit(subject, branch="HEAD"):
    out = subprocess.run(["git", "-C", str(paths.ROOT), "log", branch, "--fixed-strings", "--grep", subject, "--format=%h|%cI|%s"], capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    rows = [line.split("|", 2) for line in out if line.split("|", 2)[2] == subject]
    if len(rows) != 1:
        raise SystemExit(f"expected one commit for: {subject}")
    return {"subject": rows[0][2], "committer_date": rows[0][1], "epoch": datetime.datetime.fromisoformat(rows[0][1]).timestamp()}


def main():
    doc = {"note": "Times only. A stage's log rows are under runs/ and are not public. Commit subjects and committer dates are the same on every branch. The hash of a commit differs on the public branch: see manifests/public_history_map.json there.", "stages": []}
    for stage, freeze_subject, last_change, log, cards in STAGES:
        rows = [json.loads(line) for line in (paths.ROOT / log).read_text(encoding="utf-8").splitlines() if line.strip()]
        if cards:
            rows = [r for r in rows if r.get("card") in cards]
        freeze = commit(last_change or freeze_subject)
        answers = [r["ts"] for r in rows if r.get("status") == "ok"]
        first_any = min(r["ts"] for r in rows)
        doc["stages"].append({
            "stage": stage,
            "freeze_commit": {k: freeze[k] for k in ("subject", "committer_date")},
            "first_request_utc": iso(first_any),
            "first_answer_utc": iso(min(answers)),
            "last_answer_utc": iso(max(answers)),
            "seconds_from_freeze_to_first_answer": round(min(answers) - freeze["epoch"], 1),
            "rows_counted": len(rows),
            "cards_counted": list(cards) if cards else None,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc["stages"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
