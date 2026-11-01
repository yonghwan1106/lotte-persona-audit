"""The SDK's Responses model with the stage budget in front of every request and a log row behind it.

The budget check runs before the request leaves. Each row keeps tokens, cost, the served model and the store flag the API echoed.
It keeps no prompt and no output text. _fetch_response is private to the SDK, which is why requirements.txt pins openai-agents.
"""
import json
import time
from pathlib import Path

import panel_run
from agents.models.openai_responses import OpenAIResponsesModel

from . import settings


def _bytes(obj):
    try:
        return len(json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return len(str(obj).encode("utf-8"))


def append_row(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")


class MeteredResponsesModel(OpenAIResponsesModel):
    def __init__(self, model, client, cfg, budget, role, run_id, log_path=None):
        super().__init__(model=model, openai_client=client)
        self.price = settings.price_of(cfg, model)
        self.budget = budget
        self.role = role
        self.run_id = run_id
        self.log_path = log_path or settings.MODEL_LOG
        self.default_max_output = cfg["agent"]["max_output_tokens"]

    def worst_case(self, system_instructions, input, tools, model_settings):
        """Bytes bound tokens from above, and the output is at its cap."""
        tool_bytes = sum(_bytes(getattr(t, "params_json_schema", None)) + len(getattr(t, "description", "") or "") for t in tools or [])
        tokens_in = _bytes(system_instructions) + _bytes(input) + tool_bytes + 500
        out = model_settings.max_tokens or self.default_max_output
        return (tokens_in * self.price["input"] + out * self.price["output"]) / 1_000_000

    async def _fetch_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, previous_response_id=None, conversation_id=None, stream=False, prompt=None):
        self.budget.check(self.worst_case(system_instructions, input, tools, model_settings), f"{self.role} call")
        t0 = time.time()
        response = await super()._fetch_response(system_instructions, input, model_settings, tools, output_schema, handoffs, previous_response_id=previous_response_id, conversation_id=conversation_id, stream=stream, prompt=prompt)
        usage = response.usage
        cost = 0.0
        row = {"ts": round(time.time(), 3), "run_id": self.run_id, "kind": "agent_model", "role": self.role, "model": self.model, "served_model": response.model, "status": response.status, "store": response.store, "service_tier": response.service_tier, "latency_s": round(time.time() - t0, 3)}
        if usage is not None:
            details_in = usage.input_tokens_details
            details_out = usage.output_tokens_details
            usage_doc = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "input_tokens_details": {"cached_tokens": details_in.cached_tokens if details_in else 0, "cache_write_tokens": getattr(details_in, "cache_write_tokens", 0) if details_in else 0},
            }
            cost = panel_run.call_cost(usage_doc, self.price)
            row.update(input_tokens=usage.input_tokens, cached_tokens=usage_doc["input_tokens_details"]["cached_tokens"], output_tokens=usage.output_tokens, reasoning_tokens=details_out.reasoning_tokens if details_out else None)
        else:
            cost = self.worst_case(system_instructions, input, tools, model_settings)
            row["cost_assumed"] = True
        row["cost_usd"] = cost
        append_row(self.log_path, row)
        return response
