"""The fix stage: the scenarios and the demo again after the must_fix changes, with cached panel answers only.

settings.activate_fix_stage moves logs, results and budget. This module holds what only this stage needs. Import it after activation.
"""
import json
import time

import panel_run
from . import metered, panel, settings


class CacheOnlyBackend(panel.RealBackend):
    """The real backend, except that a cache miss stops the run. No new panel call can leave from this stage."""

    def run_items(self, model, items, ledger, progress=None):
        missing = [item for item in items if self.cached(model, item) is None]
        if missing:
            return {"counts": {"called": 0, "cached": len(items) - len(missing), "failed": 0, "stopped": len(missing)}, "stop_reason": "cache_miss_no_new_panel_call"}
        return super().run_items(model, items, ledger, progress=progress)


def probe_decisions_store(cfg, api_key, client=None):
    """One Decisions request with store false. What the endpoint does with the field is measured here, not assumed."""
    model = cfg["intake"]["decisions_model"]
    price = settings.price_of(cfg, model)
    question = [{"type": "predicate", "name": "is_drink", "instructions": "Does the text name a drink?"}]
    settings.StageBudget(cfg["limits"]["budget_usd"]).check(0.002, "decisions store probe")
    owns = client is None
    client = client or panel_run.httpx.Client(timeout=60)
    try:
        resp = client.post(cfg["decisions_endpoint"], headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": model, "input": "zero sugar soda", "questions": question, "store": False})
    finally:
        if owns:
            client.close()
    try:
        body = resp.json()
    except ValueError:
        body = {}
    usage = body.get("usage") or {}
    cost = panel_run.call_cost({"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0), "input_tokens_details": usage.get("input_tokens_details")}, price) if usage else 0.0
    metered.append_row(settings.MODEL_LOG, {"ts": round(time.time(), 3), "run_id": "decisions_store_probe", "kind": "decisions", "model": model, "status": f"http_{resp.status_code}", "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "cost_usd": cost})
    err = body.get("error") or {}
    return {
        "request": "POST /v1/decisions with store false and one predicate on a fixed harmless text",
        "http_status": resp.status_code,
        "accepted": resp.status_code == 200,
        "error_type": panel_run.scrub(err.get("type") or ""),
        "error_code": panel_run.scrub(err.get("code") or ""),
        "error_param": panel_run.scrub(err.get("param") or ""),
        "error_message": panel_run.scrub(err.get("message") or ""),
        "response_has_store_field": "store" in body,
        "cost_usd": cost,
    }


def write_probe(doc):
    settings.RESULTS.mkdir(parents=True, exist_ok=True)
    (settings.RESULTS / "decisions_store_probe.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
