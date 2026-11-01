"""The deterministic tools as plain functions on the context. tools.py wraps them for the SDK; the tests call them directly.

Order is enforced here. A tool whose precondition is unmet returns status blocked and does nothing, so a wrong tool order from
the model cannot produce a verdict. No tool takes a threshold, a label or a value as an argument.
"""
import asyncio
import datetime
import json

import panel_run
from .. import verdict_v2
from . import allocation, cards as card_rules, diagnostics, questionnaire, report, settings, verdict_rules


def blocked(tool, reason, **extra):
    return {"status": "blocked", "tool": tool, "reason": reason, **extra}


def _plan_hash(doc):
    return settings.canonical_hash({k: v for k, v in doc.items() if k != "plan_hash"})


def validate_card(ctx, card_id, fields=None, requested_outputs=None, suspected_instructions=None):
    intake = card_rules.Intake(ctx.text)
    if card_id in ctx.intake_cards:
        fields = ctx.intake_cards[card_id]
    elif fields is None:
        return {"status": "needs_input", "card_id": card_id, "reason": "card_not_registered", "next": "call validate_card again with fields filled from the card text in the message"}
    status, doc = intake.check(card_id, fields, requested_outputs, suspected_instructions)
    if status == "ok":
        ctx.cards[card_id] = doc
        ctx.plan = None  # a changed card set voids any plan and its approval
        ctx.approval = None
    for item in doc.get("removed", []):
        ctx.removed.append({"card_id": card_id, **item})
    for item in doc.get("excluded", []):
        ctx.excluded.append({"card_id": card_id, **item})
    public = {k: v for k, v in doc.items() if k not in ("clean_text",)}
    return {"status": status, **public}


def plan_run(ctx, models, n_personas, include_c0):
    if not ctx.cards:
        return blocked("plan_run", "no_validated_card")
    problems = card_rules.roles_problem(ctx.cards)
    if problems:
        return blocked("plan_run", "card_set_incomplete", problems=problems)
    allowed = {ctx.cfg["models"]["main"]["id"], ctx.cfg["models"]["cheap"]["id"]}
    unknown = [m for m in models if m not in allowed]
    if unknown or not models:
        return blocked("plan_run", "model_not_allowed", unknown=unknown, allowed=sorted(allowed))
    if n_personas <= 0:
        return blocked("plan_run", "n_personas_must_be_positive")
    card_ids = list(ctx.cards)
    panel_cfg = ctx.cfg["panel"]
    calls = {m: n_personas * len(card_ids) for m in models}
    c0 = None
    if include_c0:
        spec = panel_cfg["c0"]
        c0_cards = [c for c in spec["cards"] if c in ctx.cards]
        c0 = {"model": spec["model"], "calls_per_card": spec["calls_per_card"], "cards": c0_cards}
        calls[spec["model"]] = calls.get(spec["model"], 0) + spec["calls_per_card"] * len(c0_cards)
    from . import panel as panel_module

    money = panel_module.cost_planning(ctx.cfg, calls)
    remaining = ctx.budget.remaining()
    pilot_cards = panel_cfg["pilot"]["cards"]
    pilot = panel_cfg["pilot"]["model"] in models and all(c in ctx.cards for c in pilot_cards)
    plan = {
        "cards": card_ids,
        "models": list(models),
        "n_personas": n_personas,
        "c0": c0,
        "pilot": pilot,
        "calls_by_model": calls,
        "calls_total": sum(calls.values()),
        **money,
        "worst_case_every_call_at_output_cap_usd": panel_module.absolute_worst_case(ctx.cfg, calls),
        "estimated_minutes": round(sum(calls.values()) * ctx.cfg["planning"]["seconds_per_call"] / ctx.cfg["limits"]["concurrency"] / 60, 1),
        "formula": f"{n_personas} personas x {len(card_ids)} cards x {len(models)} models, plus no-persona calls",
    }
    plan["plan_hash"] = _plan_hash(plan)
    reasons = []
    if money["cost_cap_usd"] >= remaining:
        reasons.append(f"cost cap {money['cost_cap_usd']} USD does not fit the remaining {round(remaining, 4)} USD")
    if n_personas > panel_cfg["max_personas"]:
        reasons.append(f"at most {panel_cfg['max_personas']} personas")
    if reasons:
        ctx.plan = None
        ctx.approval = None
        ctx.event("plan_refused", reasons=reasons, cost_cap_usd=money["cost_cap_usd"], remaining_usd=round(remaining, 4), calls_total=plan["calls_total"])
        return {"status": "refused", "reasons": reasons, "plan": plan, "remaining_usd": round(remaining, 4)}
    ctx.plan = plan
    ctx.approval = None
    return {"status": "accepted", "plan": plan, "remaining_usd": round(remaining, 4), "needs_human_approval": True}


def record_approval(ctx, plan_hash, approver, note=None):
    """Called by the application when a person approves, never by the model."""
    if not ctx.plan or ctx.plan["plan_hash"] != plan_hash:
        raise ValueError("approval names a plan that is not the current plan")
    ctx.approval = {"plan_hash": plan_hash, "approver": approver, "note": note, "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "cost_cap_usd": ctx.plan["cost_cap_usd"]}
    ctx.event("approval_recorded", plan_hash=plan_hash, approver=approver, note=note)


def run_panel_preconditions(ctx, plan_hash):
    if not ctx.plan:
        return blocked("run_panel", "no_accepted_plan")
    if ctx.plan["plan_hash"] != plan_hash:
        return blocked("run_panel", "plan_hash_differs_from_current_plan")
    if not ctx.approval or ctx.approval["plan_hash"] != plan_hash:
        return blocked("run_panel", "no_human_approval_recorded")
    if not ctx.panel_allowed:
        return blocked("run_panel", "panel_disabled_in_this_context")
    if ctx.backend is None:
        return blocked("run_panel", "no_panel_backend")
    if ctx.plan["cost_cap_usd"] >= ctx.budget.remaining():
        return blocked("run_panel", "budget_no_longer_fits")
    return None


async def run_panel(ctx, plan_hash):
    stop = run_panel_preconditions(ctx, plan_hash)
    if stop:
        return stop
    if ctx.run_doc and ctx.run_doc.get("complete") and ctx.run_doc.get("plan_hash") == plan_hash:
        return blocked("run_panel", "this_plan_already_ran")
    plan = ctx.plan
    spent = ctx.budget.spent()
    # The runner stops at the approved cap, and never past the stage budget.
    ledger = panel_run.Ledger(min(ctx.budget.budget_usd, spent + plan["cost_cap_usd"]), spent)
    doc = await asyncio.to_thread(ctx.backend.run, ctx, plan, ledger, ctx.progress)
    doc["plan_hash"] = plan_hash
    doc["spent_this_run_usd"] = round(ctx.budget.spent() - spent, 6)
    failed = sum(s["counts"]["failed"] for s in doc["stages"])
    doc["codes_failed"] = failed
    ctx.run_doc = doc
    return {"status": "done" if doc["complete"] else "stopped", **doc}


def diagnose_run(ctx):
    if not ctx.run_doc:
        return blocked("diagnose_run", "panel_has_not_run")
    if not ctx.run_doc.get("complete"):
        return blocked("diagnose_run", "run_record_incomplete", stop_reason=ctx.run_doc.get("stop_reason"))
    loaded = ctx.backend.load_matrices(ctx, ctx.plan)
    roles = {c: {"role": v["role"], "paraphrase_of": v.get("paraphrase_of"), "brand_of": v.get("brand_of"), "anchor_items": v["anchor_items"]} for c, v in ctx.cards.items()}
    doc = diagnostics.compute(loaded["answers"], loaded["c0"], loaded["c0_model"], loaded["units"], loaded["segments"], roles, ctx.cfg["rules"])
    ctx.diagnostics = doc
    ctx.reason_tokens = loaded["reason_tokens"]
    ctx.reasons_too_long = loaded["reasons_too_long"]
    ctx.panel_sha256 = loaded["panel_sha256"]
    return {"status": "done", "summary": diagnostic_summary(doc)}


def diagnostic_summary(doc):
    """What the manager sees: flags only. The values stay in the context and the report."""
    out = {}
    for model, d in doc["by_model"].items():
        out[settings.short_model(model)] = {
            "rank": d["rank"],
            "distinguishable_pairs": [k for k, g in d["gaps"].items() if g["distinguishable"]],
            "indistinct_pairs": [k for k, g in d["gaps"].items() if not g["distinguishable"]],
            "negative_control_separated": {c: g["separated"] for c, g in d["negative"].items()},
            "brand_exceeds_noise": bool(d["brand"] and d["brand"]["exceeds_noise"]),
        }
    out["model_disagreement_pairs"] = doc["model_disagreement"]["pairs"]
    out["no_personal_information"] = bool(doc["c0"] and doc["c0"]["flag_no_personal_information"])
    return out


def decide_verdict(ctx):
    if not ctx.diagnostics:
        return blocked("decide_verdict", "diagnostics_missing")
    if not ctx.run_doc or not ctx.run_doc.get("complete"):
        return blocked("decide_verdict", "run_record_incomplete")
    stored = json.loads((settings.paths.RESULTS / "stage3" / "verdict_v2.json").read_text(encoding="utf-8"))
    if stored["rule_version"] != verdict_v2.RULE_VERSION:
        return blocked("decide_verdict", "stored_rule_version_differs")
    roles = {c: {"role": v["role"], "anchor_items": v["anchor_items"]} for c, v in ctx.cards.items()}
    ctx.verdict = verdict_rules.decide(ctx.diagnostics, roles, stored["answers"]["rows"], ctx.cfg["panel"]["condition"], ctx.text)
    ctx.catalog = verdict_rules.metric_catalog(ctx.diagnostics, ctx.verdict, ctx.text)
    return {"status": "done", "sentences": ctx.verdict["sentences"], "metric_ids": sorted(ctx.catalog)}


def allocate_real_sample(ctx):
    if not ctx.verdict:
        return blocked("allocate_real_sample", "verdict_missing")
    roles = {c: {"role": v["role"], "target_segment": v["target_segment"]} for c, v in ctx.cards.items()}
    ctx.allocation = allocation.allocate(ctx.verdict, roles, ctx.diagnostics, ctx.cfg, ctx.text)
    return {"status": "done", "cards": ctx.allocation["cards"], "target_segment": ctx.allocation["target_segment"]}


def build_questionnaire(ctx):
    if not ctx.allocation:
        return blocked("build_questionnaire", "allocation_missing")
    ctx.questionnaire = questionnaire.build(ctx.allocation, ctx.cards, ctx.text)
    return {"status": "done", "items": len(ctx.questionnaire["items"])}


def write_ledger(ctx):
    if not (ctx.verdict and ctx.allocation and ctx.questionnaire):
        return blocked("write_ledger", "verdict_allocation_or_questionnaire_missing")
    if ctx.ledger_entry:
        return blocked("write_ledger", "already_written")
    out = report.write_outputs(ctx)
    ctx.ledger_entry = out["entry"]
    return {"status": "done", "manifest_sha256": out["entry"]["manifest_sha256"], "report": out["report_path"]}
