"""The fix stage runner. Same commands as agent_run.py, on this stage's own logs, results and USD 3 budget, with cached panel answers only.

Use the project venv:
  .venv/Scripts/python.exe src/agent_fix_run.py check
  .venv/Scripts/python.exe src/agent_fix_run.py demo-start --run-id demo6
  .venv/Scripts/python.exe src/agent_fix_run.py demo-resume --run-id demo6 --approver "NAME"
  .venv/Scripts/python.exe src/agent_fix_run.py scenarios --runs 3 --demo-run demo6
  .venv/Scripts/python.exe src/agent_fix_run.py attacks --demo-run demo6       the wf7 attacks that got through, live
  .venv/Scripts/python.exe src/agent_fix_run.py attacks-offline --demo-run demo6
  .venv/Scripts/python.exe src/agent_fix_run.py probe-decisions-store          one Decisions request with store false
  .venv/Scripts/python.exe src/agent_fix_run.py status --write

freeze and smoke belong to the frozen agent stage and are refused here. The API key is read by runner code only.
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lotte_audit.agent import settings  # noqa: E402

settings.activate_fix_stage()

import agent_run  # noqa: E402
import panel_run  # noqa: E402
from lotte_audit.agent import attack_replay, fixstage, runtime  # noqa: E402

agent_run.BACKEND_CLASS = fixstage.CacheOnlyBackend


def demo_state(run_id):
    path = agent_run.demo_paths(run_id)["ctx"]
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def cmd_attacks(run_id):
    cfg = settings.load_config()
    text = settings.load_text()
    client, api_key = runtime.make_client(cfg)
    state = demo_state(run_id)
    if not state or not state.get("verdict"):
        raise SystemExit(f"no finished demo state for {run_id}")
    rows = asyncio.run(attack_replay.run_live(cfg, text, client, api_key, state))
    doc = {"demo_run": run_id, "rows": rows, "still_passing": [r["id"] for r in rows if r["still_passes"]], "total": len(rows), "cost_usd": round(sum(r["cost_usd"] for r in rows), 6)}
    settings.RESULTS.mkdir(parents=True, exist_ok=True)
    (settings.RESULTS / "attack_replay_live.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("still_passing", "total", "cost_usd")}, ensure_ascii=False))


def cmd_attacks_offline(run_id):
    cfg = settings.load_config()
    text = settings.load_text()
    with tempfile.TemporaryDirectory() as tmp:
        doc = attack_replay.offline(cfg, text, demo_state(run_id), Path(tmp))
    settings.RESULTS.mkdir(parents=True, exist_ok=True)
    (settings.RESULTS / "attack_replay_offline.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in doc.items() if k != "guard_variants"}, ensure_ascii=False, indent=1))
    print(json.dumps({k: doc["guard_variants"][k] for k in ("total", "accepted", "accepted_texts")}, ensure_ascii=False))


def cmd_probe():
    cfg = settings.load_config()
    api_key = panel_run.read_api_key(cfg["api_key_file"])
    doc = fixstage.probe_decisions_store(cfg, api_key)
    fixstage.write_probe(doc)
    print(json.dumps(doc, ensure_ascii=False, indent=1))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:]
    command = argv[0] if argv else None
    if command in ("freeze", "smoke"):
        raise SystemExit(f"{command} belongs to the frozen agent stage")
    run_id = argv[argv.index("--demo-run") + 1] if "--demo-run" in argv else "demo6"
    if command == "attacks":
        cmd_attacks(run_id)
    elif command == "attacks-offline":
        cmd_attacks_offline(run_id)
    elif command == "probe-decisions-store":
        cmd_probe()
    else:
        agent_run.main()


if __name__ == "__main__":
    main()
