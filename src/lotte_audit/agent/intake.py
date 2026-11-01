"""The intake check before the manager runs: fixed patterns first, then a Decisions API predicate on gpt-6-luna.

A request that holds a card passes through, because the design removes only the offending item and goes on. validate_card does that.
"""
import json
import time

import httpx

import panel_run
from . import cards as card_rules, metered, settings


async def ask_decisions(cfg, text_cfg, api_key, request_text, budget, run_id, client=None, log_path=None):
    """{class: probability} from one Decisions call, or None when the call failed. A failure falls through to the manager.

    The request carries no store field: the endpoint's reference lists none. See results/fix_stage/decisions_store_probe.json.
    """
    log_path = log_path or settings.MODEL_LOG
    questions = [{"type": "predicate", "name": name, "instructions": wording} for name, wording in text_cfg["refusal"]["decisions_questions"].items()]
    model = cfg["intake"]["decisions_model"]
    price = settings.price_of(cfg, model)
    budget.check((len(request_text.encode("utf-8")) + 2000) * price["input"] / 1_000_000 + 2000 * price["output"] / 1_000_000, "decisions call")
    owns = client is None
    client = client or httpx.AsyncClient(timeout=60)
    t0 = time.time()
    try:
        resp = await client.post(cfg["decisions_endpoint"], headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": model, "input": request_text, "questions": questions})
    except httpx.HTTPError as exc:
        metered.append_row(log_path, {"ts": round(time.time(), 3), "run_id": run_id, "kind": "decisions", "model": model, "status": "transport_error", "error": type(exc).__name__, "cost_usd": 0.0})
        return None
    finally:
        if owns:
            await client.aclose()
    if resp.status_code != 200:
        try:
            err = resp.json().get("error") or {}
        except ValueError:
            err = {}
        metered.append_row(log_path, {"ts": round(time.time(), 3), "run_id": run_id, "kind": "decisions", "model": model, "status": f"http_{resp.status_code}", "error": panel_run.scrub(err.get("code") or err.get("type") or ""), "cost_usd": 0.0})
        return None
    body = resp.json()
    usage = body.get("usage") or {}
    cost = panel_run.call_cost({"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0), "input_tokens_details": usage.get("input_tokens_details")}, price) if usage else 0.0
    metered.append_row(log_path, {"ts": round(time.time(), 3), "run_id": run_id, "kind": "decisions", "model": model, "status": "ok", "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "latency_s": round(time.time() - t0, 3), "cost_usd": cost})
    return {a["name"]: a["probability"] for a in body.get("answers", []) if a.get("type") == "predicate"}


def holds_card(text, text_cfg):
    return any(marker in text for marker in text_cfg["card_rules"]["card_markers"])


def decide_from_probabilities(probabilities, cfg):
    """(tripwire, classes, ask_human)."""
    intake = cfg["intake"]
    refuse = [k for k, p in probabilities.items() if p >= intake["refuse_at"]]
    if refuse:
        return True, refuse, False
    ask = [k for k, p in probabilities.items() if p >= intake["ask_human_at"]]
    if ask:
        return True, ask, True
    return False, [], False


async def check_request(ctx, request_text, api_key, decisions_client=None):
    """{tripwire, classes, by, ask_human, probabilities}. No model is called when a fixed pattern already matches."""
    if holds_card(request_text, ctx.text):
        return {"tripwire": False, "classes": [], "by": "holds_card", "ask_human": False}
    classes = card_rules.Intake(ctx.text).classify_request(request_text)
    if classes:
        return {"tripwire": True, "classes": classes, "by": "pattern", "ask_human": False}
    probabilities = await ask_decisions(ctx.cfg, ctx.text, api_key, request_text, ctx.budget, ctx.run_id, client=decisions_client)
    if probabilities is None:
        return {"tripwire": False, "classes": [], "by": "decisions_failed", "ask_human": False}
    tripwire, found, ask = decide_from_probabilities(probabilities, ctx.cfg)
    return {"tripwire": tripwire, "classes": found, "by": "decisions", "ask_human": ask, "probabilities": probabilities}


def dumps(doc):
    return json.dumps(doc, ensure_ascii=False, default=str)
