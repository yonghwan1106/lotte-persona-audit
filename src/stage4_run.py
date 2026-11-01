"""Stage 4 runner: the demo from cached panel answers, the survey ingestion path, and the command with which a person approves one small run.

Use the project venv:
  .venv/Scripts/python.exe src/stage4_run.py check
  .venv/Scripts/python.exe src/stage4_run.py demo-start --run-id demo8
  .venv/Scripts/python.exe src/stage4_run.py demo-resume --run-id demo8 --approver "NAME"
  .venv/Scripts/python.exe src/stage4_run.py make-standin --name krei_draw0      writes row level stand-in files under runs/stage4/ingest
  .venv/Scripts/python.exe src/stage4_run.py ingest-real --run-id demo8 --real FILE --panel FILE --panel-model MODEL --panel-condition C1 --source-label LABEL --approver "NAME"
  .venv/Scripts/python.exe src/stage4_run.py explore-scenarios                   the exploration filter on planted sentences, no API call
  .venv/Scripts/python.exe src/stage4_run.py scenarios --runs 1 --demo-run demo8 behaviour scenarios on the live API
  .venv/Scripts/python.exe src/stage4_run.py human-plan --run-id human1          a person's small run, step one: the plan, no call
  .venv/Scripts/python.exe src/stage4_run.py human-approve --run-id human1       step two, at a terminal: a person types name and plan hash, then it runs
  .venv/Scripts/python.exe src/stage4_run.py status --write

human-approve refuses without an interactive terminal. No demo or stage brief goes through it, and code still cannot tell who typed.
--budget-ceiling USD, before the command, stops this process's model calls once the stage has spent that much, so a step can stop before the stage budget.
The API key is read by runner code only. Persona text, respondent codes and the row level files stay under runs/.
"""
import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lotte_audit.agent import settings  # noqa: E402

settings.activate_stage4()

import agent_run  # noqa: E402
import panel_run  # noqa: E402
from lotte_audit import paths  # noqa: E402
from lotte_audit.agent import action, explore, fixstage, human, ingest, runtime, toolimpl  # noqa: E402
from lotte_audit.agent import panel as panel_module  # noqa: E402
from lotte_audit.agent.state import AuditContext  # noqa: E402

agent_run.BACKEND_CLASS = fixstage.CacheOnlyBackend
INGEST_DIR = settings.STAGE / "ingest"
COMMITTED = ("config/stage4.json", "config/stage4_text.json", "config/explore_prompt.json", "config/explore_scenarios.json", "config/panel_value_policy.json", "config/prereg_stage4.json", "src/lotte_audit/duel_units.py", "src/lotte_audit/agent/action.py", "src/lotte_audit/agent/explore.py", "src/lotte_audit/agent/human.py", "src/lotte_audit/agent/ingest.py", "src/lotte_audit/agent/report4.py", "src/stage4_run.py")
SMALL_RUN = {"n_personas": 100, "cards": ("A", "A_para", "B", "C", "N")}


def require_committed():
    """No model call before this stage's wording and rules are in git."""
    for name in COMMITTED:
        if subprocess.run(["git", "-C", str(paths.ROOT), "ls-files", "--error-unmatch", name], capture_output=True).returncode != 0:
            raise SystemExit(f"{name} is not committed")
    if subprocess.run(["git", "-C", str(paths.ROOT), "diff", "--quiet", "HEAD", "--", *COMMITTED]).returncode != 0:
        raise SystemExit("stage 4 files have uncommitted changes")


def stage_text():
    text = settings.load_text()
    text["stage4"] = action.load_text()
    text["allocation_text"] = {**text["allocation_text"], "manual": text["stage4"]["allocation_manual"]}
    return text


def stage_context(cfg, text, api_key, run_id, backend_class):
    budget = settings.StageBudget(cfg["limits"]["budget_usd"])
    p = agent_run.demo_paths(run_id)
    ctx = AuditContext(run_id=run_id, cfg=cfg, text=text, budget=budget, transcript_path=p["transcript"], demo=True, results_dir=p["dir"], progress=200, stage4=True)
    ctx.backend = backend_class(cfg, api_key)
    ctx.explorer = explore.Explorer(cfg, api_key)

    async def guard(c, request_text):
        from lotte_audit.agent import intake

        return await intake.check_request(c, request_text, api_key)

    ctx.guardrail_fn = guard
    return ctx


def cmd_check(_args):
    cfg = settings.load_config()
    settings.check_frozen(agent_run.load_panel_hash(cfg))
    settings.require_committed()
    require_committed()
    budget = settings.StageBudget(cfg["limits"]["budget_usd"])
    print(json.dumps({"frozen_agent": "ok", "committed": "ok", "budget_usd": budget.budget_usd, "stage_spent_usd": round(budget.spent(), 6)}, indent=2))


def cmd_demo_start(args):
    cfg = settings.load_config()
    settings.check_frozen(agent_run.load_panel_hash(cfg))
    settings.require_committed()
    require_committed()
    text = stage_text()
    client, api_key = runtime.make_client(cfg)
    ctx = stage_context(cfg, text, api_key, args.run_id, agent_run.BACKEND_CLASS)
    ctx.intake_cards = settings.load_cards()["cards"]
    p = agent_run.demo_paths(args.run_id)
    if p["transcript"].exists():
        raise SystemExit("this run id has a transcript already; use another --run-id")
    manager, _ = runtime.build_agents(ctx, client)
    message = text["stage4"]["demo_message"]
    ctx.event("user_message", text=message)
    outcome = asyncio.run(runtime.drive(ctx, manager, message, approve_fn=None, state_path=p["state"]))
    ctx.save(p["ctx"])
    print(json.dumps({"outcome": outcome, "plan_hash": (ctx.plan or {}).get("plan_hash"), "calls_total": (ctx.plan or {}).get("calls_total"), "cost_cap_usd": (ctx.plan or {}).get("cost_cap_usd"), "stage_spent_usd": round(ctx.budget.spent(), 6)}, ensure_ascii=False, indent=2))


def cmd_demo_resume(args):
    cfg = settings.load_config()
    text = stage_text()
    client, api_key = runtime.make_client(cfg)
    ctx = stage_context(cfg, text, api_key, args.run_id, agent_run.BACKEND_CLASS)
    p = agent_run.demo_paths(args.run_id)
    ctx.restore(json.loads(p["ctx"].read_text(encoding="utf-8")))
    ctx.stage4 = True
    manager, _ = runtime.build_agents(ctx, client)

    def approve(c, name, a):
        known = runtime.plan_guard_decision(c, name, a)
        return known or {"approved": True, "approver": args.approver, "note": args.note}

    outcome = asyncio.run(runtime.resume_from_file(ctx, manager, p["state"], approve))
    ctx.save(p["ctx"])
    print(json.dumps({"outcome": outcome, "manifest": (ctx.ledger_entry or {}).get("manifest_sha256"), "explored": sorted(ctx.explore), "stage_spent_usd": round(ctx.budget.spent(), 6)}, ensure_ascii=False, indent=2))


def cmd_make_standin(args):
    """A KREI calibration draw as a stand-in on the anchor items. Row level, so it goes under runs/ only."""
    import pandas as pd

    import stage4_measures as sm

    rules = action.load_rules()["ingest"]
    s = sm.setup()
    answers = sm.stored(s, sm.TERRA, "C2")
    draws = sm.stage2_draws(s, 0, "row")
    idx, wts = draws[rules["standin_draw_index"]]
    pool_rows = s["pool_rows"][idx]
    df = s["df"]
    ids = [f"R{i:04d}" for i in range(len(idx))]
    real = {"respondent_id": ids, "age_band": df[paths.AGE].astype(int).to_numpy()[pool_rows], "sex": df[paths.SEX].astype(int).to_numpy()[pool_rows], "weight": wts}
    panel = {"respondent_id": ids}
    for item in ingest.ANCHORS:
        real[item] = s["ctx"]["pool"]["y"][item][idx].astype(int)
        panel[f"p_{item}"] = answers["calibration"][item][idx]
    INGEST_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(real).to_csv(INGEST_DIR / f"{args.name}_real.csv", index=False, encoding="utf-8")
    pd.DataFrame(panel).to_csv(INGEST_DIR / f"{args.name}_panel.csv", index=False, encoding="utf-8")
    print(json.dumps({"folder": "runs/stage4/ingest", "name": args.name, "respondents": len(ids), "label": rules["standin_label"], "panel_answers": "gpt-6.1-terra C2, stage 2 cache"}, ensure_ascii=False))


def cmd_ingest_real(args):
    text = action.load_text()
    run_dir = settings.RESULTS / args.run_id
    if not (run_dir / "manifest.json").exists():
        raise SystemExit(f"no finished run {args.run_id}")
    doc = ingest.ingest(args.real, args.panel, run_dir, settings.LEDGER, args.source_label, args.approver, text, args.panel_model, args.panel_condition)
    print(json.dumps({k: doc[k] for k in ("source_label", "panel", "is_real_concept_survey", "n_respondents", "report_status", "panel_values_in_report", "duel_outcome", "health_check", "concept_duel", "anchors", "duel_grade", "seed_runs", "seed_runs_failed", "approver", "lines")}, ensure_ascii=False, indent=1))


def cmd_explore_scenarios(_args):
    doc = explore.filter_scenarios(settings.load_text(), action.load_text(), action.load_rules()["explore"]["limits"])
    settings.RESULTS.mkdir(parents=True, exist_ok=True)
    (settings.RESULTS / "explore_filter_scenarios.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("total", "passed", "failed")}, ensure_ascii=False))


def human_paths(run_id):
    p = agent_run.demo_paths(run_id)
    return p


def plan_context(cfg, text, run_id):
    """A context with registered cards validated and one small plan. No model and no API call. The cards are the frozen demo cards."""
    budget = settings.StageBudget(cfg["limits"]["budget_usd"])
    p = human_paths(run_id)
    ctx = AuditContext(run_id=run_id, cfg=cfg, text=text, budget=budget, transcript_path=p["transcript"], demo=True, results_dir=p["dir"], progress=50, stage4=True)
    ctx.intake_cards = settings.load_cards()["cards"]
    return ctx


def cmd_human_plan(args):
    cfg = settings.load_config()
    text = stage_text()
    p = human_paths(args.run_id)
    if p["ctx"].exists():
        raise SystemExit("this run id has a saved plan already; use another --run-id")
    ctx = plan_context(cfg, text, args.run_id)
    for card in SMALL_RUN["cards"]:
        toolimpl.validate_card(ctx, card)
    out = toolimpl.plan_run(ctx, [cfg["models"]["main"]["id"], cfg["models"]["cheap"]["id"]], SMALL_RUN["n_personas"], False)
    if out["status"] != "accepted":
        raise SystemExit(json.dumps(out, ensure_ascii=False))
    ctx.save(p["ctx"])
    print(json.dumps({"plan_hash": ctx.plan["plan_hash"], "calls_total": ctx.plan["calls_total"], "cost_cap_usd": ctx.plan["cost_cap_usd"], "formula": ctx.plan["formula"], "remaining_usd": out["remaining_usd"], "next": f"at a terminal: .venv/Scripts/python.exe src/stage4_run.py human-approve --run-id {args.run_id}"}, ensure_ascii=False, indent=2))


def cmd_human_approve(args):
    cfg = settings.load_config()
    text = stage_text()
    p = human_paths(args.run_id)
    if not p["ctx"].exists():
        raise SystemExit("no saved plan; run human-plan first")
    ctx = plan_context(cfg, text, args.run_id)
    ctx.restore(json.loads(p["ctx"].read_text(encoding="utf-8")))
    ctx.stage4 = True
    if ctx.approval:
        raise SystemExit("this plan was approved already")
    name = human.typed_approval(ctx.plan)
    settings.check_frozen(agent_run.load_panel_hash(cfg))
    settings.require_committed()
    require_committed()
    api_key = panel_run.read_api_key(cfg["api_key_file"])
    ctx.backend = panel_module.RealBackend(cfg, api_key)
    ctx.explorer = explore.Explorer(cfg, api_key)
    toolimpl.record_approval(ctx, ctx.plan["plan_hash"], name, "typed at a terminal", channel=human.CHANNEL)
    ctx.save(p["ctx"])
    outcome = asyncio.run(human.run_after_approval(ctx))
    ctx.save(p["ctx"])
    print(json.dumps({"outcome": outcome, "stage_spent_usd": round(ctx.budget.spent(), 6)}, ensure_ascii=False, indent=2))


def cmd_detectable(_args):
    doc = action.detectable(action.load_rules())
    settings.RESULTS.mkdir(parents=True, exist_ok=True)
    (settings.RESULTS / "detectable.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--budget-ceiling", type=float, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("detectable").set_defaults(func=cmd_detectable)
    d = sub.add_parser("demo-start")
    d.add_argument("--run-id", default="demo8")
    d.set_defaults(func=cmd_demo_start)
    r = sub.add_parser("demo-resume")
    r.add_argument("--run-id", default="demo8")
    r.add_argument("--approver", required=True)
    r.add_argument("--note", default=None)
    r.set_defaults(func=cmd_demo_resume)
    m = sub.add_parser("make-standin")
    m.add_argument("--name", default="krei_draw0")
    m.set_defaults(func=cmd_make_standin)
    i = sub.add_parser("ingest-real")
    i.add_argument("--run-id", default="demo8")
    i.add_argument("--real", required=True)
    i.add_argument("--panel", required=True)
    i.add_argument("--panel-model", required=True)
    i.add_argument("--panel-condition", required=True)
    i.add_argument("--source-label", required=True)
    i.add_argument("--approver", required=True)
    i.set_defaults(func=cmd_ingest_real)
    h = sub.add_parser("human-plan")
    h.add_argument("--run-id", default="human1")
    h.set_defaults(func=cmd_human_plan)
    a = sub.add_parser("human-approve")
    a.add_argument("--run-id", default="human1")
    a.set_defaults(func=cmd_human_approve)
    t = sub.add_parser("status")
    t.add_argument("--write", action="store_true")
    t.set_defaults(func=agent_run.cmd_status)
    sub.add_parser("explore-scenarios").set_defaults(func=cmd_explore_scenarios)
    c = sub.add_parser("scenarios")
    c.add_argument("--runs", type=int, default=1)
    c.add_argument("--demo-run", default="demo8")
    c.add_argument("--only", default=None)
    c.add_argument("--tag", default=None)
    c.add_argument("--probe", action="store_true")
    c.set_defaults(func=lambda a: agent_run.cmd_scenarios(a, stage_text()))
    args = parser.parse_args()
    if args.budget_ceiling is not None:
        settings.set_call_ceiling(args.budget_ceiling)
    args.func(args)


if __name__ == "__main__":
    main()
