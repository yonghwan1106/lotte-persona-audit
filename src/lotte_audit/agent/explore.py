"""explore_card: stored panel reason sentences of a candidate card, grouped by one Terra call into hypotheses for a person writing a survey.

These are LLM outputs, not respondent text. Every sentence is labelled a hypothesis. Code removes what breaks the number rule or the blocked patterns in the
forms listed, and what shares a long run of characters with a persona or with a stored reason. A form not listed passes, so this is no guarantee of a sentence's content. Persona text and reason sentences stay in memory
and under runs/. What leaves is the filtered sentences and counts, with no code.
"""
import hashlib
import json
import random
import re
import time
from pathlib import Path

import httpx
import numpy as np

import panel_run
from .. import paths
from . import metered, narration, settings

SECTIONS = ("objections", "attractions", "segment_hypotheses", "survey_questions")
SCHEMA = {
    "type": "object",
    "properties": {s: {"type": "array", "items": {"type": "string"}} for s in SECTIONS},
    "required": list(SECTIONS),
    "additionalProperties": False,
}
PROMPT = paths.CONFIG / "explore_prompt.json"
SCENARIOS = paths.CONFIG / "explore_scenarios.json"
MIN_REASONS = 30
PERSONA_RUN = 10
REASON_RUN = 15
FIELDS = ("p1", "p2", "p3", "p4", "p5")


def load_template():
    return json.loads(PROMPT.read_text(encoding="utf-8"))["template"]


def squeeze(text):
    """Spaces and punctuation out, so an echo cannot hide behind them."""
    return re.sub(r"[\s.,!?\u3002\uff0c\uff1f\uff01'\"\u201c\u201d\u2018\u2019()\[\]:;~-]+", "", text or "")


def runs_of(text, size):
    s = squeeze(text)
    return {s[i : i + size] for i in range(len(s) - size + 1)}


def shared_run(sentence, corpus_runs, card_runs, size):
    """A run of size characters shared with the corpus and not with the card itself. The card's own wording is fine to repeat."""
    return bool((runs_of(sentence, size) - card_runs) & corpus_runs)


def age_word(segment, words):
    return words[segment.rsplit("_", 1)[0]]


def gather(reason_rows, words):
    """Prompt lines from (reason, t2b, segment) rows: age word and intent third. Row order is shuffled by a fixed seed, and no code is here."""
    rows = [r for r in reason_rows if r["reason"]]
    if not rows:
        return []
    values = np.array([r["t2b"] for r in rows], dtype=float)
    low, high = np.percentile(values, [100 / 3, 200 / 3])
    lines = []
    for r in rows:
        band = "low" if r["t2b"] <= low else "high" if r["t2b"] >= high else "mid"
        lines.append(f"[{age_word(r['segment'], words['age_words'])}, {words['intent_words'][band]}] {r['reason']}")
    random.Random(paths.SEED).shuffle(lines)
    return lines


def collect_reasons(ctx, card_id, model):
    """Reasons and panel internal values of the card from the cache. Returns rows, and the persona texts for the echo check, both held in memory only."""
    backend = ctx.backend
    panel = backend.panel(ctx.plan["n_personas"])
    items = backend.items_for("C1", card_id, ctx.cards[card_id]["clean_text"], panel["codes"], panel["persona"])
    rows = []
    for i, item in enumerate(items):
        record = backend.cached(model, item)
        if record is None:
            continue
        answer = record["answer"]
        total = sum(answer[f] for f in FIELDS)
        rows.append({"reason": answer.get("reason"), "t2b": 100.0 * (answer["p4"] + answer["p5"]) / total if total else 0.0, "segment": str(panel["segments"][i])})
    return rows, list(panel["persona"].values())


def build_prompt(card_text, lines):
    return load_template().replace("{CARD}", card_text).replace("{REASONS}", "\n".join(lines))


def sentence_problem(section, sentence, guard, blocked, question_end, persona_runs, reason_runs, card_persona, card_reason):
    """A code naming why a sentence goes, or None. Only codes are kept, not the sentence."""
    if not sentence or not sentence.strip():
        return "empty"
    if guard.check_sentence(sentence, set()):
        return "number_or_claim"
    if blocked.search(narration.normalise(sentence)):
        return "blocked_pattern"
    outside = narration.normalise(sentence).strip()
    if guard.taste.search(outside):
        return "taste"
    if guard.restatement.search(outside):
        return "restates_verdict"
    if section == "survey_questions":
        if not question_end.search(outside):
            return "not_a_question"
    elif not guard.ending.search(outside):
        return "not_a_hypothesis"
    if shared_run(sentence, persona_runs, card_persona, PERSONA_RUN):
        return "persona_echo"
    if shared_run(sentence, reason_runs, card_reason, REASON_RUN):
        return "reason_echo"
    return None


def filter_output(raw, agent_text, stage_text, limits, personas, reasons, card_text):
    """Filtered, cut and labelled sentences per section, and the count of what was dropped per code."""
    guard = narration.Guard(agent_text)
    t = stage_text["explore"]
    blocked = re.compile(t["blocked_patterns"])
    question_end = re.compile(t["question_ending"])
    persona_runs = set().union(*[runs_of(p, PERSONA_RUN) for p in personas]) if personas else set()
    reason_runs = set().union(*[runs_of(r, REASON_RUN) for r in reasons]) if reasons else set()
    card_persona, card_reason = runs_of(card_text, PERSONA_RUN), runs_of(card_text, REASON_RUN)
    out = {}
    dropped = {}
    returned = {}
    for section in SECTIONS:
        items = raw.get(section) or []
        returned[section] = len(items)
        kept = []
        for sentence in items:
            problem = sentence_problem(section, sentence, guard, blocked, question_end, persona_runs, reason_runs, card_persona, card_reason)
            if problem:
                dropped[problem] = dropped.get(problem, 0) + 1
            elif len(kept) < limits[section]:
                kept.append(t["label_prefix"] + sentence.strip())
            else:
                dropped["over_limit"] = dropped.get("over_limit", 0) + 1
        out[section] = kept
    return {"sections": out, "returned": returned, "dropped": dropped}


def filter_scenarios(agent_text, stage_text, limits, doc=None):
    """Planted sentences through the filter, no API. Each section is tried, since the filter treats questions apart. Pass or fail comes from code."""
    doc = doc or json.loads(SCENARIOS.read_text(encoding="utf-8"))
    rows = []
    for expected, group in (("dropped", doc["drop"]), ("kept", doc["keep"])):
        for name, sentence in group.items():
            for section in ("objections", "attractions", "segment_hypotheses"):
                got = filter_output({section: [sentence]}, agent_text, stage_text, limits, [], [], "")
                outcome = "kept" if got["sections"][section] else "dropped"
                rows.append({"scenario": name, "section": section, "expected": expected, "outcome": outcome, "codes": got["dropped"], "passed": outcome == expected})
    failed = sorted({r["scenario"] for r in rows if not r["passed"]})
    return {"note": "Synthetic sentences, code checks, no API call. Patterns catch the forms listed. This is not a guarantee about forms not listed.", "total": len(rows), "passed": sum(r["passed"] for r in rows), "failed": failed, "rows": rows}


def echo_check(sections, personas, reasons, card_text, prefix):
    """The last look before a file is saved: no kept sentence shares a long run with a persona or a reason."""
    persona_runs = set().union(*[runs_of(p, PERSONA_RUN) for p in personas]) if personas else set()
    reason_runs = set().union(*[runs_of(r, REASON_RUN) for r in reasons]) if reasons else set()
    card_persona, card_reason = runs_of(card_text, PERSONA_RUN), runs_of(card_text, REASON_RUN)
    bad = {"persona": 0, "reason": 0}
    checked = 0
    for items in sections.values():
        for sentence in items:
            body = sentence[len(prefix) :] if sentence.startswith(prefix) else sentence
            checked += 1
            bad["persona"] += int(shared_run(body, persona_runs, card_persona, PERSONA_RUN))
            bad["reason"] += int(shared_run(body, reason_runs, card_reason, REASON_RUN))
    return {"sentences_checked": checked, "personas_compared": len(personas), "reasons_compared": len(reasons), "persona_echo": bad["persona"], "reason_echo": bad["reason"], "passed": not (bad["persona"] or bad["reason"]), "persona_run_chars": PERSONA_RUN, "reason_run_chars": REASON_RUN}


def request_body(cfg, model, prompt):
    req = cfg["request"]
    return {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "text": {"format": {"type": "json_schema", "name": "explore_card", "strict": True, "schema": SCHEMA}},
        "store": req["store"],
        "reasoning": {"effort": req["reasoning_effort"]},
        "service_tier": req["service_tier"],
        "max_output_tokens": req["max_output_tokens"],
    }


class Explorer:
    """One Terra call for one card, behind the stage budget and a cache under runs/. The key comes from the runner."""

    def __init__(self, cfg, api_key, cache_dir=None, client=None):
        self.cfg = cfg
        self.api_key = api_key
        self.cache_dir = Path(cache_dir or settings.STAGE / "explore_cache")
        self.client = client

    def __call__(self, card_id, prompt, budget, run_id):
        model = self.cfg["models"]["main"]["id"]
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        path = self.cache_dir / f"{card_id}_{digest[:16]}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["output"], 0.0
        price = settings.price_of(self.cfg, model)
        worst = (len(prompt.encode("utf-8")) * price["input"] + self.cfg["request"]["max_output_tokens"] * price["output"]) / 1_000_000
        budget.check(worst, "explore call")
        owns = self.client is None
        client = self.client or httpx.Client(timeout=self.cfg["limits"]["timeout_s"])
        t0 = time.time()
        try:
            resp = client.post(self.cfg["endpoint"], headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=request_body(self.cfg, model, prompt))
        finally:
            if owns:
                client.close()
        if resp.status_code != 200:
            metered.append_row(settings.MODEL_LOG, {"ts": round(time.time(), 3), "run_id": run_id, "kind": "explore", "role": "explore", "model": model, "status": f"http_{resp.status_code}", "cost_usd": 0.0})
            raise RuntimeError(f"explore call failed with status {resp.status_code}")
        body = resp.json()
        usage = body.get("usage") or {}
        cost = panel_run.call_cost(usage, price) if usage else worst
        metered.append_row(settings.MODEL_LOG, {"ts": round(time.time(), 3), "run_id": run_id, "kind": "explore", "role": "explore", "model": model, "served_model": body.get("model"), "status": body.get("status"), "store": body.get("store"), "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "latency_s": round(time.time() - t0, 3), "cost_usd": cost, **({} if usage else {"cost_assumed": True})})
        texts = [part.get("text", "") for item in body.get("output") or [] if item.get("type") == "message" for part in item.get("content") or [] if part.get("type") == "output_text"]
        output = json.loads("".join(texts))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"model": model, "prompt_sha256": digest, "output": output}, ensure_ascii=False), encoding="utf-8")
        return output, cost


def run(ctx, card_id, rules):
    """Everything for one card. Returns the document that may be saved, or a status naming why not."""
    model = ctx.cfg["models"]["main"]["id"]
    text = ctx.text["stage4"]
    rows, personas = collect_reasons(ctx, card_id, model)
    reasons = [r["reason"] for r in rows if r["reason"]]
    if len(reasons) < MIN_REASONS:
        return {"status": "blocked", "reason": "no_cached_reasons", "cached_reasons": len(reasons), "next": "the new run branch of at most 60 calls is not built; run the panel for this card under a person's approval first"}
    lines = gather(rows, text["explore"])
    card_text = ctx.cards[card_id]["clean_text"]
    raw, cost = ctx.explorer(card_id, build_prompt(card_text, lines), ctx.budget, ctx.run_id)
    got = filter_output(raw, ctx.text, text, rules["explore"]["limits"], personas, reasons, card_text)
    check = echo_check(got["sections"], personas, reasons, card_text, text["explore"]["label_prefix"])
    if not check["passed"]:
        return {"status": "blocked", "reason": "echo_check_failed", "check": check}
    return {
        "status": "done",
        "card": card_id,
        "marking": text["explore"]["banner"],
        "source": {"model_of_reasons": model, "reasons_read": len(reasons), "calls_this_card": 0 if cost == 0.0 else 1, "cost_usd": round(cost, 6)},
        "sections": got["sections"],
        "returned_by_model": got["returned"],
        "dropped_by_code": got["dropped"],
        "echo_check": check,
    }


def to_markdown(docs, text):
    t = text["explore"]
    lines = [f"# {t['title']}", "", t["banner"], ""]
    for card, doc in docs.items():
        lines += [f"## {card}", ""]
        for section, label in t["sections"].items():
            lines += [f"### {label}", ""]
            lines += [f"- {s}" for s in doc["sections"][section]] or ["- (none left after the filter)"]
            lines += [""]
        lines += [f"Filter: returned {doc['returned_by_model']}, dropped {doc['dropped_by_code'] or 'none'}. Echo check: {doc['echo_check']['passed']}.", ""]
    return "\n".join(lines) + "\n"
