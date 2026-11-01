"""The person's approval of one small run, and the fixed tool order that follows it.

Refuses without an interactive terminal. A stage brief, a demo or an agent has no business here. Code still cannot tell who typed: the record says what was typed and at which channel.
"""
import json
import sys

from . import toolimpl

CHANNEL = "terminal"
HASH_CHARS = 12


class NotApproved(SystemExit):
    """Nothing was approved and nothing ran."""


def typed_approval(plan, stdin=None, read=input, out=print):
    """Show the plan, take a name and the plan hash typed back. Returns the name."""
    stdin = stdin or sys.stdin
    if not stdin.isatty():
        raise NotApproved("human-approve needs a person at an interactive terminal; nothing was approved and nothing ran")
    out(json.dumps({"plan_hash": plan["plan_hash"], "calls_total": plan["calls_total"], "cost_cap_usd": plan["cost_cap_usd"], "formula": plan["formula"], "cards": plan["cards"]}, ensure_ascii=False, indent=2))
    name = read("Your name: ").strip()
    if not name:
        raise NotApproved("no name, nothing was approved")
    typed = read(f"Type the first {HASH_CHARS} characters of the plan hash to approve this spend: ").strip()
    if typed != plan["plan_hash"][:HASH_CHARS]:
        raise NotApproved("the hash does not match, nothing was approved")
    return name


async def run_after_approval(ctx):
    """The code path of a small run once a person has approved. No manager model here: the tools run in their fixed order."""
    out = await toolimpl.run_panel(ctx, ctx.plan["plan_hash"])
    if out.get("status") != "done":
        return {"stopped_at": "run_panel", "out": {k: out.get(k) for k in ("status", "reason", "stop_reason")}}
    for step, fn in (("diagnose_run", toolimpl.diagnose_run), ("decide_verdict", toolimpl.decide_verdict)):
        got = fn(ctx)
        if got["status"] != "done":
            return {"stopped_at": step, "out": got}
    for card, doc in ctx.cards.items():
        if doc["role"] == "candidate":
            got = toolimpl.explore_card(ctx, card)
            if got.get("status") != "done":
                return {"stopped_at": "explore_card", "out": got}
    for step, fn in (("allocate_real_sample", toolimpl.allocate_real_sample), ("build_questionnaire", toolimpl.build_questionnaire), ("write_ledger", toolimpl.write_ledger)):
        got = fn(ctx)
        if got["status"] != "done":
            return {"stopped_at": step, "out": got}
    return {"status": "done", "manifest": ctx.ledger_entry["manifest_sha256"]}
