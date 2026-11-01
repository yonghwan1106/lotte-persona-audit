"""The two agents and the loop around them.

The manager on gpt-6.1-sol holds the final answer. The narrator on gpt-6.1-terra is a tool of the manager, not a handoff, because the
manager keeps the turn. The panel responder is not an agent at all: see panel.py.

store=False is set on both agents, because the SDK's ModelSettings otherwise leaves stored responses on. Tracing is off for the run,
and sensitive data is off as a second lock. The transcript under results/ and the logs under runs/ are the audit record.
"""
import json
from pathlib import Path
from typing import Literal, Optional

from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    ModelSettings,
    OutputGuardrailTripwireTriggered,
    RunConfig,
    RunContextWrapper,
    RunHooks,
    Runner,
    RunState,
    function_tool,
    input_guardrail,
    output_guardrail,
)
from openai import AsyncOpenAI
from openai.types.shared import Reasoning
from pydantic import BaseModel

import panel_run
from . import intake, metered, narration, settings, toolimpl
from .state import AuditContext

REFUSAL_CLASSES = Literal["taste", "packaging", "sales_forecast", "success_probability", "single_score", "threshold_change", "out_of_scope"]


class CardFields(BaseModel):
    description: str
    role: str
    target_segment: str
    anchor_items: list[str]
    attributes: list[str]
    price_band: Optional[str]
    alternatives: list[str]
    paraphrase_of: Optional[str]
    brand_of: Optional[str]


class AuditReply(BaseModel):
    status: Literal["refused", "needs_input", "blocked", "complete", "stopped"]
    refused_classes: list[REFUSAL_CLASSES]
    note: str


class NarrationSentence(BaseModel):
    text: str
    metric_ids: list[str]


class NarrationOutput(BaseModel):
    sentences: list[NarrationSentence]


def _tool_failure(ctx, error):
    """What the model sees when a tool raises. The transcript gets the same text, with anything shaped like a key removed."""
    message = panel_run.scrub(f"{type(error).__name__}: {error}")
    context = getattr(ctx, "context", None)
    if isinstance(context, AuditContext):
        context.event("tool_error", error=message)
    return json.dumps({"status": "tool_error", "error": message}, ensure_ascii=False)


def _logged(wrapper, name, args, fn):
    ctx = wrapper.context
    ctx.count_tool(name)
    ctx.event("tool_call", tool=name, args=args)
    result = fn()
    ctx.event("tool_output", tool=name, output=result)
    return json.dumps(result, ensure_ascii=False, default=str)


def build_tools(text):
    d = text["tool_descriptions"]

    @function_tool(name_override="validate_card", description_override=d["validate_card"], failure_error_function=_tool_failure)
    def validate_card(ctx: RunContextWrapper[AuditContext], card_id: str, fields: Optional[CardFields], requested_outputs: list[str], suspected_instructions: list[str]) -> str:
        plain = fields.model_dump() if fields else None
        return _logged(ctx, "validate_card", {"card_id": card_id, "fields": plain, "requested_outputs": requested_outputs, "suspected_instructions": suspected_instructions}, lambda: toolimpl.validate_card(ctx.context, card_id, plain, requested_outputs, suspected_instructions))

    @function_tool(name_override="plan_run", description_override=d["plan_run"], failure_error_function=_tool_failure)
    def plan_run(ctx: RunContextWrapper[AuditContext], models: list[str], n_personas: int, include_c0: bool) -> str:
        return _logged(ctx, "plan_run", {"models": models, "n_personas": n_personas, "include_c0": include_c0}, lambda: toolimpl.plan_run(ctx.context, models, n_personas, include_c0))

    @function_tool(name_override="run_panel", description_override=d["run_panel"], needs_approval=True, failure_error_function=_tool_failure)
    async def run_panel(ctx: RunContextWrapper[AuditContext], plan_hash: str) -> str:
        c = ctx.context
        c.count_tool("run_panel")
        c.event("tool_call", tool="run_panel", args={"plan_hash": plan_hash})
        result = await toolimpl.run_panel(c, plan_hash)
        c.event("tool_output", tool="run_panel", output=result)
        return json.dumps(result, ensure_ascii=False, default=str)

    @function_tool(name_override="diagnose_run", description_override=d["diagnose_run"], failure_error_function=_tool_failure)
    def diagnose_run(ctx: RunContextWrapper[AuditContext]) -> str:
        return _logged(ctx, "diagnose_run", {}, lambda: toolimpl.diagnose_run(ctx.context))

    @function_tool(name_override="decide_verdict", description_override=d["decide_verdict"], failure_error_function=_tool_failure)
    def decide_verdict(ctx: RunContextWrapper[AuditContext]) -> str:
        return _logged(ctx, "decide_verdict", {}, lambda: toolimpl.decide_verdict(ctx.context))

    @function_tool(name_override="allocate_real_sample", description_override=d["allocate_real_sample"], failure_error_function=_tool_failure)
    def allocate_real_sample(ctx: RunContextWrapper[AuditContext]) -> str:
        return _logged(ctx, "allocate_real_sample", {}, lambda: toolimpl.allocate_real_sample(ctx.context))

    @function_tool(name_override="build_questionnaire", description_override=d["build_questionnaire"], failure_error_function=_tool_failure)
    def build_questionnaire(ctx: RunContextWrapper[AuditContext]) -> str:
        return _logged(ctx, "build_questionnaire", {}, lambda: toolimpl.build_questionnaire(ctx.context))

    @function_tool(name_override="write_ledger", description_override=d["write_ledger"], failure_error_function=_tool_failure)
    def write_ledger(ctx: RunContextWrapper[AuditContext]) -> str:
        return _logged(ctx, "write_ledger", {}, lambda: toolimpl.write_ledger(ctx.context))

    return [validate_card, plan_run, run_panel, diagnose_run, decide_verdict, allocate_real_sample, build_questionnaire, write_ledger]


def build_stage4_tools(text):
    d = text["stage4"]["tool_descriptions"]

    @function_tool(name_override="explore_card", description_override=d["explore_card"], failure_error_function=_tool_failure)
    def explore_card(ctx: RunContextWrapper[AuditContext], card_id: str) -> str:
        return _logged(ctx, "explore_card", {"card_id": card_id}, lambda: toolimpl.explore_card(ctx.context, card_id))

    @function_tool(name_override="ingest_real", description_override=d["ingest_real"], failure_error_function=_tool_failure)
    def ingest_real(ctx: RunContextWrapper[AuditContext]) -> str:
        return _logged(ctx, "ingest_real", {}, lambda: toolimpl.ingest_real(ctx.context))

    return [explore_card, ingest_real]


def run_state_flags(ctx):
    """What is done, from the context. A run resumed in a new conversation has no other way to know."""
    return {
        **({"explored_cards": sorted(ctx.explore)} if ctx.stage4 else {}),
        "cards_validated": sorted(ctx.cards),
        "cards_waiting_for_a_person": sorted(ctx.pending_confirmations),
        "plan_accepted": bool(ctx.plan),
        "approval_recorded": bool(ctx.approval),
        "panel_complete": bool(ctx.run_doc and ctx.run_doc.get("complete")),
        "diagnostics": bool(ctx.diagnostics),
        "verdict": bool(ctx.verdict),
        "narration": bool(ctx.narration.get("accepted")),
        "allocation": bool(ctx.allocation),
        "questionnaire": bool(ctx.questionnaire),
        "ledger_written": bool(ctx.ledger_entry),
    }


def manager_instructions(wrapper, _agent):
    ctx = wrapper.context
    suffix = "\n\n" + ctx.text["stage4"]["manager_suffix"] if ctx.stage4 else ""
    return ctx.text["manager_instructions"] + suffix + "\n\n" + ctx.text["manager_state_header"] + "\n" + json.dumps(run_state_flags(ctx), ensure_ascii=False)


def narrator_instructions(wrapper, _agent):
    ctx = wrapper.context
    text = ctx.text["narrator_instructions"]
    facts = {"sentences": ctx.verdict["sentences"] if ctx.verdict else []}
    metrics = {k: v["what"] for k, v in (ctx.catalog or {}).items()}
    return text.replace("{FACTS}", json.dumps(facts, ensure_ascii=False)).replace("{METRICS}", json.dumps(metrics, ensure_ascii=False)).replace("{REASON_TOKENS}", json.dumps({c: [w for w, _ in t] for c, t in (ctx.reason_tokens or {}).items()}, ensure_ascii=False))


@output_guardrail
async def number_rule(wrapper, _agent, output):
    """Rejects a numeral form listed in the rule outside placeholders, an unknown metric id, a market claim and a taste guess."""
    ctx = wrapper.context
    ctx.narration["attempts"] += 1
    guard = narration.Guard(ctx.text)
    sentences = [s.model_dump() for s in output.sentences]
    reasons = guard.check_output(sentences, set(ctx.catalog or {}))
    if reasons:
        ctx.narration["rejections"].append(reasons)
    else:
        ctx.narration["accepted"] = sentences
    ctx.event("narrator_output", sentences=sentences, reasons=reasons, accepted=not reasons)
    return GuardrailFunctionOutput(output_info={"reasons": reasons}, tripwire_triggered=bool(reasons))


def _narrator_failure(wrapper, error):
    ctx = wrapper.context
    reasons = ctx.narration["rejections"][-1] if isinstance(error, OutputGuardrailTripwireTriggered) and ctx.narration["rejections"] else [f"{type(error).__name__}"]
    left = ctx.cfg["agent"]["narrator_max_attempts"] - ctx.narration["attempts"]
    ctx.event("narrator_rejected", reasons=reasons, attempts_left=left)
    return json.dumps({"status": "rejected", "reasons": reasons, "attempts_left": max(left, 0)}, ensure_ascii=False)


async def _narrator_result(result):
    return json.dumps({"status": "accepted", "sentences": len(result.final_output.sentences)}, ensure_ascii=False)


class NarratorHooks(RunHooks):
    """The narrator is called through as_tool, so its call goes on the transcript here. The system prompt is left out."""

    async def on_llm_start(self, context, agent, system_prompt, input_items):
        ctx = context.context
        ctx.count_tool("narrate_verdict")
        ctx.event("tool_call", tool="narrate_verdict", args={"input": input_items})


def _narrator_enabled(wrapper, _agent):
    ctx = wrapper.context
    return bool(ctx.verdict) and not ctx.narration.get("accepted") and ctx.narration["attempts"] < ctx.cfg["agent"]["narrator_max_attempts"]


@input_guardrail(run_in_parallel=False)
async def intake_check(wrapper, _agent, input_items):
    ctx = wrapper.context
    if not ctx.guardrail_enabled or ctx.guardrail_fn is None:
        return GuardrailFunctionOutput(output_info={"by": "disabled"}, tripwire_triggered=False)
    text = input_items if isinstance(input_items, str) else json.dumps(input_items, ensure_ascii=False, default=str)
    info = await ctx.guardrail_fn(ctx, text)
    ctx.event("intake_check", **{k: v for k, v in info.items()})
    return GuardrailFunctionOutput(output_info=info, tripwire_triggered=info["tripwire"])


def agent_settings(cfg):
    a = cfg["agent"]
    return ModelSettings(store=False, reasoning=Reasoning(effort=a["reasoning_effort"]), max_tokens=a["max_output_tokens"], response_include=["reasoning.encrypted_content"])


def run_config():
    return RunConfig(tracing_disabled=True, trace_include_sensitive_data=False, workflow_name="lotte_persona_audit")


def build_agents(ctx, client, narrator_model=None, manager_model=None):
    """The manager, with the narrator as its tool. The models can be replaced in tests and in the planted digit scenario."""
    cfg, text = ctx.cfg, ctx.text
    narrator = Agent(
        name="narrator",
        instructions=narrator_instructions,
        model=narrator_model or metered.MeteredResponsesModel(cfg["models"]["main"]["id"], client, cfg, ctx.budget, "narrator", ctx.run_id),
        model_settings=agent_settings(cfg),
        output_type=NarrationOutput,
        output_guardrails=[number_rule],
    )
    manager = Agent(
        name="audit_manager",
        instructions=manager_instructions,
        model=manager_model or metered.MeteredResponsesModel(cfg["models"]["manager"]["id"], client, cfg, ctx.budget, "manager", ctx.run_id),
        model_settings=agent_settings(cfg),
        tools=[
            *build_tools(text),
            *(build_stage4_tools(text) if ctx.stage4 else []),
            narrator.as_tool(
                tool_name="narrate_verdict",
                tool_description=text["narrate_tool_description"],
                custom_output_extractor=_narrator_result,
                is_enabled=_narrator_enabled,
                max_turns=cfg["agent"]["narrator_max_turns"],
                failure_error_function=_narrator_failure,
                hooks=NarratorHooks(),
                run_config=run_config(),
            ),
        ],
        input_guardrails=[intake_check],
        output_type=AuditReply,
    )
    return manager, narrator


def make_client(cfg):
    """The only place the agent stage reads the API key for the SDK."""
    key = panel_run.read_api_key(cfg["api_key_file"])
    return AsyncOpenAI(api_key=key, max_retries=2, timeout=cfg["limits"]["timeout_s"]), key


def refusal_message(text, classes):
    return " ".join(text["refusal"]["messages"][c] for c in classes if c in text["refusal"]["messages"])


def checked_status(ctx, claimed):
    """A claimed complete stands only when the ledger is written and nothing waits for a person. The model's word is not the record."""
    if claimed == "complete" and (not ctx.ledger_entry or ctx.pending_confirmations):
        return "stopped"
    return claimed


def outcome_from_final(ctx, reply):
    guard = narration.Guard(ctx.text)
    status = checked_status(ctx, reply.status)
    return {
        "status": status,
        "claimed_status": reply.status,
        "status_corrected_by_code": status != reply.status,
        "refused_classes": list(reply.refused_classes),
        "by": "manager",
        "note": guard.clean_note(reply.note),
        "note_dropped": bool(reply.note) and guard.clean_note(reply.note) is None,
        "message": refusal_message(ctx.text, reply.refused_classes) if reply.refused_classes else None,
    }


def interruption_args(item):
    raw = getattr(item, "arguments", None)
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


async def resolve_interruptions(ctx, result, approve_fn, state_path=None):
    """Ask the application about each pending approval. Returns the state to resume with, or None when paused for later."""
    state = result.to_state()
    if state_path:
        Path(state_path).parent.mkdir(parents=True, exist_ok=True)
        Path(state_path).write_text(state.to_string(context_serializer=lambda c: {"run_id": c.run_id}), encoding="utf-8")
    for item in result.interruptions:
        name = getattr(item, "name", None) or getattr(item, "tool_name", None)
        args = interruption_args(item)
        ctx.event("approval_requested", tool=name, args=args, plan=ctx.plan)
        decision = approve_fn(ctx, name, args) if approve_fn else None
        if decision is None:
            ctx.event("approval_pending", tool=name)
            return None
        if decision.get("approved"):
            toolimpl.record_approval(ctx, args.get("plan_hash"), decision["approver"], decision.get("note"))
            state.approve(item)
            ctx.event("approval_granted", tool=name, approver=decision["approver"])
        else:
            state.reject(item, rejection_message=decision.get("reason") or "rejected")
            ctx.event("approval_rejected", tool=name, reason=decision.get("reason"))
    return state


async def drive(ctx, manager, start, approve_fn=None, state_path=None):
    """Run from a message or a resumed state to a final reply or a pause. Every stop is a reported outcome, never a silent one."""
    max_turns = ctx.cfg["agent"]["max_turns"]
    try:
        if isinstance(start, RunState):
            result = await Runner.run(manager, start, max_turns=max_turns, run_config=run_config())
        else:
            result = await Runner.run(manager, start, context=ctx, max_turns=max_turns, run_config=run_config())
        interruptions = 0
        while result.interruptions:
            interruptions += len(result.interruptions)
            state = await resolve_interruptions(ctx, result, approve_fn, state_path)
            if state is None:
                return {"status": "paused_for_approval", "by": "system", "refused_classes": [], "interruptions": interruptions}
            result = await Runner.run(manager, state, max_turns=max_turns, run_config=run_config())
        outcome = outcome_from_final(ctx, result.final_output)
        outcome["interruptions"] = interruptions
    except InputGuardrailTripwireTriggered as exc:
        info = exc.guardrail_result.output.output_info
        if info.get("ask_human"):
            outcome = {"status": "needs_input", "by": info["by"], "refused_classes": [], "suspected_classes": info["classes"], "message": ctx.text["refusal"]["ask_human"]}
        else:
            outcome = {"status": "refused", "by": info["by"], "refused_classes": info["classes"], "message": refusal_message(ctx.text, info["classes"])}
    except MaxTurnsExceeded:
        outcome = {"status": "stopped", "by": "max_turns", "refused_classes": []}
    except settings.BudgetExceeded as exc:
        outcome = {"status": "stopped", "by": "budget", "refused_classes": [], "error": str(exc)}
    ctx.event("final", **outcome)
    return outcome


async def resume_from_file(ctx, manager, state_path, approve_fn):
    """Load a paused run from disk and go on with the same run. The stored state comes from runs/, which only this application writes."""
    raw = Path(state_path).read_text(encoding="utf-8")
    state = await RunState.from_string(manager, raw, context_override=RunContextWrapper(ctx))
    for item in state.get_interruptions():
        name = getattr(item, "name", None) or getattr(item, "tool_name", None)
        args = interruption_args(item)
        decision = approve_fn(ctx, name, args)
        if decision and decision.get("approved"):
            toolimpl.record_approval(ctx, args.get("plan_hash"), decision["approver"], decision.get("note"))
            state.approve(item)
            ctx.event("approval_granted", tool=name, approver=decision["approver"], resumed=True)
        else:
            state.reject(item, rejection_message=(decision or {}).get("reason") or "rejected")
            ctx.event("approval_rejected", tool=name, resumed=True)
    return await drive(ctx, manager, state, approve_fn, state_path)


def plan_guard_decision(ctx, name, args):
    """A run_panel request for a plan that is not the current accepted plan is rejected without asking anyone."""
    if name != "run_panel":
        return {"approved": False, "reason": "only run_panel takes approval"}
    if not ctx.plan or ctx.plan["plan_hash"] != args.get("plan_hash"):
        return {"approved": False, "reason": "no accepted plan with this hash"}
    return None
