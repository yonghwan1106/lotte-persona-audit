"""Audit agent runner. Use the project venv: .venv/Scripts/python.exe src/agent_run.py <command>.

  check                  frozen files, commit state, spend, no API call
  smoke                  3 calls per model on a card outside the demo: tokens and cost only, no answers printed
  freeze                 write the prompt hash into the config and hash the frozen files, then commit
  demo-start             the manager validates and plans, then the run pauses for approval and its state is saved
  demo-resume --approver NAME   loads the saved run, records the approval, and goes on with the same run to the ledger
  card-confirm --run-id NAME --card ID --decision remove|keep --approver NAME   a person decides on flagged fact style sentences
  scenarios --runs N     behaviour scenarios on the live API, results/agent/scenarios
  status                 spend per log

The API key is read by runner code only, from the file named in the config. Persona text and respondent codes stay under runs/.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import panel_run  # noqa: E402
from lotte_audit.agent import panel as panel_module  # noqa: E402
from lotte_audit.agent import runtime, scenarios, settings, toolimpl  # noqa: E402
from lotte_audit.agent.state import AuditContext  # noqa: E402

BACKEND_CLASS = panel_module.RealBackend  # the fix stage replaces this with a backend that only reads the cache


def demo_paths(run_id):
    out = settings.RESULTS / run_id
    return {"dir": out, "transcript": out / "transcript.jsonl", "ctx": settings.SAVED_DIR / f"{run_id}_ctx.json", "state": settings.SAVED_DIR / f"{run_id}_run_state.json"}


def load_panel_hash(cfg):
    return panel_module.panel_hash(panel_module.load_real_panel(cfg)["codes"])


def cmd_freeze(_args):
    cfg = settings.load_config(check_prompt=False)
    sha = settings.template_sha256(settings.load_prompt())
    if cfg["prompt_sha256"] != sha:
        raw = settings.RUN_CONFIG.read_text(encoding="utf-8").replace(cfg["prompt_sha256"], sha)
        settings.RUN_CONFIG.write_text(raw, encoding="utf-8", newline="\n")
        cfg = settings.load_config()
    doc = settings.current_hashes(load_panel_hash(cfg))
    settings.FROZEN.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(json.dumps(doc, indent=2))


def cmd_check(_args):
    cfg = settings.load_config()
    settings.check_frozen(load_panel_hash(cfg))
    settings.require_committed()
    budget = settings.StageBudget(cfg["limits"]["budget_usd"])
    print(json.dumps({"prompt_sha256": cfg["prompt_sha256"], "frozen": "ok", "committed": "ok", "budget_usd": budget.budget_usd, "stage_spent_usd": round(budget.spent(), 6)}, indent=2))


def cmd_status(_args):
    cfg = settings.load_config(check_prompt=False)
    budget = settings.StageBudget(cfg["limits"]["budget_usd"])
    panel = panel_run.summarize_log(settings.PANEL_LOG)
    panel["panel_total_usd"] = panel.pop("gate_total_usd")
    rows = []
    if settings.MODEL_LOG.exists():
        rows = [json.loads(x) for x in settings.MODEL_LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    agents = {}
    for r in rows:
        key = f"{r.get('kind')}/{r.get('role', '-')}/{r.get('model')}"
        d = agents.setdefault(key, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "stores_seen": set()})
        d["calls"] += 1
        d["input_tokens"] += r.get("input_tokens") or 0
        d["output_tokens"] += r.get("output_tokens") or 0
        d["cost_usd"] = round(d["cost_usd"] + (r.get("cost_usd") or 0.0), 6)
        d["stores_seen"].add(str(r.get("store")))
    for d in agents.values():
        d["stores_seen"] = sorted(d["stores_seen"])
    doc = {"panel": panel, "agent_models": agents, "stage_spent_usd": round(budget.spent(), 6), "budget_usd": budget.budget_usd}
    print(json.dumps(doc, indent=2))
    if _args.write:
        settings.RESULTS.mkdir(parents=True, exist_ok=True)
        (settings.RESULTS / "run_summary.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")


def cmd_smoke(_args):
    cfg = settings.load_config(check_prompt=False)
    budget = settings.StageBudget(cfg["limits"]["budget_usd"])
    api_key = panel_run.read_api_key(cfg["api_key_file"])
    backend = panel_module.RealBackend(cfg, api_key, enforce_freeze=False)
    panel = backend.panel(cfg["panel"]["n_personas"])
    card = settings.load_cards()["smoke_card"]["description"]
    ledger = panel_run.Ledger(budget.budget_usd, budget.spent())
    out = {}
    for model in (cfg["models"]["main"]["id"], cfg["models"]["cheap"]["id"]):
        items = backend.items_for("C1", "smoke", card, panel["codes"][:3], panel["persona"])
        out[model] = backend.run_items(model, items, ledger)
    rows = [json.loads(x) for x in settings.PANEL_LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    means = {}
    for model in out:
        ok = [r for r in rows if r["model"] == model and r["status"] == "ok" and r.get("card") == "smoke"]
        if ok:
            means[model] = {f: round(sum(r.get(f) or 0 for r in ok) / len(ok), 6) for f in ("input_tokens", "output_tokens", "reasoning_tokens", "cost_usd", "latency_s")}
            means[model]["store_echoed"] = sorted({str(r.get("store")) for r in ok})
    print(json.dumps({"runs": out, "mean_per_call": means, "statuses": sorted({r["status"] for r in rows if r.get("card") == "smoke"}), "stage_spent_usd": round(budget.spent(), 6)}, indent=2))


def demo_context(cfg, text, api_key, run_id):
    budget = settings.StageBudget(cfg["limits"]["budget_usd"])
    p = demo_paths(run_id)
    ctx = AuditContext(run_id=run_id, cfg=cfg, text=text, budget=budget, transcript_path=p["transcript"], demo=True, results_dir=p["dir"], progress=200)
    ctx.backend = BACKEND_CLASS(cfg, api_key)

    async def guard(c, request_text):
        from lotte_audit.agent import intake

        return await intake.check_request(c, request_text, api_key)

    ctx.guardrail_fn = guard
    return ctx


def cmd_demo_start(args):
    cfg = settings.load_config()
    settings.check_frozen(load_panel_hash(cfg))
    settings.require_committed()
    text = settings.load_text()
    client, api_key = runtime.make_client(cfg)
    ctx = demo_context(cfg, text, api_key, args.run_id)
    ctx.intake_cards = settings.load_cards()["cards"]
    p = demo_paths(args.run_id)
    if p["transcript"].exists():
        raise SystemExit("this run id has a transcript already; use another --run-id")
    manager, _ = runtime.build_agents(ctx, client)
    message = text["scenario_messages"]["demo"]
    ctx.event("user_message", text=message)
    outcome = asyncio.run(runtime.drive(ctx, manager, message, approve_fn=None, state_path=p["state"]))
    ctx.save(p["ctx"])
    plan = ctx.plan
    print(json.dumps({"outcome": outcome, "plan": plan, "stage_spent_usd": round(ctx.budget.spent(), 6)}, ensure_ascii=False, indent=2))


def cmd_demo_resume(args):
    cfg = settings.load_config()
    text = settings.load_text()
    client, api_key = runtime.make_client(cfg)
    ctx = demo_context(cfg, text, api_key, args.run_id)
    p = demo_paths(args.run_id)
    ctx.restore(json.loads(p["ctx"].read_text(encoding="utf-8")))
    manager, _ = runtime.build_agents(ctx, client)

    def approve(c, name, a):
        known = runtime.plan_guard_decision(c, name, a)
        return known or {"approved": True, "approver": args.approver, "note": args.note}

    outcome = asyncio.run(runtime.resume_from_file(ctx, manager, p["state"], approve))
    ctx.save(p["ctx"])
    print(json.dumps({"outcome": outcome, "manifest": (ctx.ledger_entry or {}).get("manifest_sha256"), "stage_spent_usd": round(ctx.budget.spent(), 6)}, ensure_ascii=False, indent=2))


def cmd_card_confirm(args):
    """A person's decision on the fact style sentences of one card, recorded on the saved run. The model has no tool for this."""
    cfg = settings.load_config()
    text = settings.load_text()
    budget = settings.StageBudget(cfg["limits"]["budget_usd"])
    p = demo_paths(args.run_id)
    ctx = AuditContext(run_id=args.run_id, cfg=cfg, text=text, budget=budget, transcript_path=p["transcript"], demo=True, results_dir=p["dir"])
    ctx.restore(json.loads(p["ctx"].read_text(encoding="utf-8")))
    out = toolimpl.record_leading_decision(ctx, args.card, args.decision, args.approver, args.note)
    ctx.save(p["ctx"])
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_scenarios(args, text=None):
    cfg = settings.load_config()
    text = text or settings.load_text()
    client, api_key = runtime.make_client(cfg)
    ctx_path = demo_paths(args.demo_run)["ctx"]
    demo_state = json.loads(ctx_path.read_text(encoding="utf-8")) if ctx_path.exists() else None
    if demo_state and not demo_state.get("verdict"):
        demo_state = None
    only = set(args.only.split(",")) if args.only else None
    results = asyncio.run(scenarios.run_all(cfg, text, client, api_key, demo_state, args.runs, only=only))
    scenarios.SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    tag = f"_{args.tag}" if args.tag else ""
    probe = None
    if args.probe:
        probe = scenarios.injection_probe(cfg, text, api_key)
        print(json.dumps(probe, ensure_ascii=False, indent=1))
    rows = scenarios.summarise(results)
    (scenarios.SCENARIO_DIR / f"results{tag}.json").write_text(json.dumps({"results": results, "summary": rows, "probe": probe}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    text_out = scenarios.to_markdown(rows, probe)
    (scenarios.SCENARIO_DIR / f"results{tag}.md").write_text(text_out, encoding="utf-8")
    print(text_out)
    print(json.dumps({"stage_spent_usd": round(settings.StageBudget(cfg["limits"]["budget_usd"]).spent(), 6)}))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze").set_defaults(func=cmd_freeze)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("smoke").set_defaults(func=cmd_smoke)
    d = sub.add_parser("demo-start")
    d.add_argument("--run-id", default="demo")
    d.set_defaults(func=cmd_demo_start)
    r = sub.add_parser("demo-resume")
    r.add_argument("--run-id", default="demo")
    r.add_argument("--approver", required=True)
    r.add_argument("--note", default=None)
    r.set_defaults(func=cmd_demo_resume)
    c = sub.add_parser("card-confirm")
    c.add_argument("--run-id", required=True)
    c.add_argument("--card", required=True)
    c.add_argument("--decision", required=True, choices=("remove", "keep"))
    c.add_argument("--approver", required=True)
    c.add_argument("--note", default=None)
    c.set_defaults(func=cmd_card_confirm)
    s = sub.add_parser("scenarios")
    s.add_argument("--runs", type=int, default=1)
    s.add_argument("--demo-run", default="demo")
    s.add_argument("--only", default=None)
    s.add_argument("--tag", default=None)
    s.add_argument("--probe", action="store_true")
    s.set_defaults(func=cmd_scenarios)
    t = sub.add_parser("status")
    t.add_argument("--write", action="store_true")
    t.set_defaults(func=cmd_status)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
