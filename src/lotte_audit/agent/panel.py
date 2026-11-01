"""The panel responder. Not an agent: a stateless Responses call per persona and card, no tools, no web, code handles concurrency and retries.

panel_run.Runner keeps its cache, ledger, retry and stop behaviour. Only the request, the parser and the log row differ here.
Persona text is sent to the API and read from runs/, and it never leaves this module: everything returned to a caller is aggregate.
The respondent code is never in a prompt. It names the cache file and the log row, both under runs/, which git ignores.
"""
import hashlib
import json
import math
import random
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np

import panel_run
from .. import paths, persona
from . import diagnostics, settings

FIELDS = ("p1", "p2", "p3", "p4", "p5")
REASON_MAX = 60
SCHEMA = {
    "type": "object",
    "properties": {
        **{f: {"type": "number", "minimum": 0, "maximum": 1} for f in FIELDS},
        "reason": {"type": "string", "maxLength": REASON_MAX},
    },
    "required": [*FIELDS, "reason"],
    "additionalProperties": False,
}
TOKEN_RE = re.compile("[\uac00-\ud7a3]{2,}")
JOSA_RE = re.compile("(\uc73c\ub85c|\uc5d0\uc11c|\uc5d0\uac8c|\ubcf4\ub2e4|\ucc98\ub7fc|\uae4c\uc9c0|\uc740|\ub294|\uc774|\uac00|\uc744|\ub97c|\uc5d0|\uc758|\ub3c4|\ub85c|\uc640|\uacfc|\ub9cc)$")


def render(template, card_text, persona_text):
    if template.count("{CARD}") != 1 or template.count("{PERSONA}") != 1:
        raise ValueError("template must hold one {CARD} and one {PERSONA}")
    return template.replace("{CARD}", card_text).replace("{PERSONA}", persona_text)


def build_request(cfg, model, prompt):
    req = cfg["request"]
    return {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "text": {"format": {"type": "json_schema", "name": "concept_answer", "strict": True, "schema": SCHEMA}},
        "store": req["store"],
        "reasoning": {"effort": req["reasoning_effort"]},
        "service_tier": req["service_tier"],
        "prompt_cache_options": {"mode": req["prompt_cache_mode"]},
        "max_output_tokens": req["max_output_tokens"],
    }


def parse_answer(body, sum_tolerance):
    """Validated answer from a Responses body, or AnswerError. A refusal or an incomplete answer is missing, never zero."""
    if body.get("status") != "completed":
        reason = (body.get("incomplete_details") or {}).get("reason")
        raise panel_run.AnswerError(f"status_{body.get('status')}_{reason}")
    texts = []
    for item in body.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "refusal":
                raise panel_run.AnswerError("refusal")
            if part.get("type") == "output_text":
                texts.append(part.get("text", ""))
    if not texts:
        raise panel_run.AnswerError("no_output_text")
    try:
        answer = json.loads("".join(texts))
    except json.JSONDecodeError as exc:
        raise panel_run.AnswerError("not_json") from exc
    if not isinstance(answer, dict) or set(answer) != {*FIELDS, "reason"}:
        raise panel_run.AnswerError("wrong_fields")
    for f in FIELDS:
        v = answer[f]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise panel_run.AnswerError("value_out_of_schema")
    total = sum(answer[f] for f in FIELDS)
    if abs(total - 1.0) > sum_tolerance:
        raise panel_run.AnswerError("sum_out_of_tolerance")
    reason = answer["reason"]
    if not isinstance(reason, str):
        raise panel_run.AnswerError("reason_not_text")
    # A long reason does not invalidate the probabilities. It is dropped, not cut, and counted.
    return {**{f: float(answer[f]) for f in FIELDS}, "reason": reason if len(reason) <= REASON_MAX else None, "reason_too_long": len(reason) > REASON_MAX, "raw_sum": total}


class ConceptRunner(panel_run.Runner):
    """Same cache, ledger, retry and stop behaviour as the gate runner. Each item's persona field holds the whole rendered prompt."""

    def __init__(self, cfg, model, api_key, **kwargs):
        super().__init__(cfg, "{PERSONA}", model, api_key, **kwargs)
        self.sum_tolerance = cfg["rules"]["sum_tolerance"]

    def one_attempt(self, item, prompt, attempt):
        reserve = self.worst_case_cost(prompt)
        if not self.ledger.reserve(reserve):
            self.halt("budget")
            return None, None
        base = {"condition": item["condition"], "card": item["card"], "code": item["code"], "attempt": attempt}
        t0 = time.time()
        try:
            resp = self.client.post(self.url, headers=self.headers, json=build_request(self.cfg, self.model, prompt))
        except panel_run.httpx.HTTPError as exc:
            self.ledger.settle(reserve, reserve)
            self.log(**base, status="transport_error", error=type(exc).__name__, latency_s=round(time.time() - t0, 3), cost_usd=reserve, cost_assumed=True)
            return None, min(60.0, 2.0**attempt)
        latency = round(time.time() - t0, 3)
        if resp.status_code != 200:
            self.ledger.settle(reserve, 0.0)
            try:
                err = resp.json().get("error") or {}
            except ValueError:
                err = {}
            code = str(err.get("code") or err.get("type") or "")
            self.log(**base, status=f"http_{resp.status_code}", http_status=resp.status_code, error=panel_run.scrub(code), latency_s=latency, cost_usd=0.0)
            if err.get("type") == "insufficient_quota" or code in ("insufficient_quota", "credit_balance_exhausted"):
                self.halt("insufficient_quota")
                return None, None
            if resp.status_code not in panel_run.RETRY_STATUS:
                self.halt(f"fatal_http_{resp.status_code}_{panel_run.scrub(code)}")
                return None, None
            after = resp.headers.get("retry-after")
            try:
                delay = float(after) if after else min(60.0, 2.0**attempt)
            except ValueError:
                delay = min(60.0, 2.0**attempt)
            return None, delay + random.uniform(0, 1)
        body = resp.json()
        usage = body.get("usage") or {}
        cost = panel_run.call_cost(usage, self.price) if usage else reserve
        self.ledger.settle(reserve, cost)
        details_in = usage.get("input_tokens_details") or {}
        details_out = usage.get("output_tokens_details") or {}
        fields = dict(
            http_status=200,
            latency_s=latency,
            served_model=body.get("model"),
            service_tier=body.get("service_tier"),
            store=body.get("store"),
            input_tokens=usage.get("input_tokens"),
            cached_tokens=details_in.get("cached_tokens"),
            cache_write_tokens=details_in.get("cache_write_tokens"),
            output_tokens=usage.get("output_tokens"),
            reasoning_tokens=details_out.get("reasoning_tokens"),
            cost_usd=cost,
        )
        if not usage:
            fields["cost_assumed"] = True
        try:
            answer = parse_answer(body, self.sum_tolerance)
        except panel_run.AnswerError as exc:
            self.log(**base, status="bad_answer", error=panel_run.scrub(exc), **fields)
            return None, 1.0
        self.log(**base, status="ok", **fields)
        return {"code": item["code"], "condition": item["condition"], "card": item["card"], "model": self.model, "prompt_sha256": panel_run.prompt_hash(prompt), "answer": answer, **fields}, None


def segment_label(age_code, sex_code, seg_cfg):
    for name, codes in seg_cfg["age_groups"].items():
        if int(age_code) in codes:
            return f"{name}_{seg_cfg['sex'][str(int(sex_code))]}"
    raise ValueError(f"age code {age_code} is outside the adult bands")


def select_panel(key_c1, ages, sexes, units, n, seed):
    """n respondents stratified by age band and sex with the largest remainder. Returns positions into key_c1."""
    cells = np.array([f"{int(a)}_{int(s)}" for a, s in zip(ages, sexes)])
    uniq, counts = np.unique(cells, return_counts=True)
    quota = counts / counts.sum() * n
    take = np.floor(quota).astype(int)
    for i in np.argsort(-(quota - take), kind="stable")[: n - take.sum()]:
        take[i] += 1
    rng = np.random.default_rng(seed)
    picked = []
    for cell, t in zip(uniq, take):
        positions = np.flatnonzero(cells == cell)
        picked.extend(rng.choice(positions, size=int(t), replace=False).tolist())
    return np.sort(np.array(picked))


def panel_hash(codes):
    return hashlib.sha256("\n".join(sorted(codes)).encode("utf-8")).hexdigest()


def load_real_panel(cfg, n=None):
    """Codes, persona text, survey units and segments of the test panel, from runs/ and the raw file. Stays in memory."""
    import pandas as pd
    import main_run
    from .. import data, splits

    key = pd.read_csv(paths.ROOT / "runs" / "stage3" / "key.csv", dtype={"code": str})
    key = key.loc[key.condition == cfg["panel"]["condition"]].sort_values("row_index").reset_index(drop=True)
    df, _ = data.load_sav()
    mk = splits.masks(splits.load_manifest(df))
    rows = key["row_index"].to_numpy()
    if not mk["test"][rows].all():
        raise RuntimeError("a panel respondent is outside the test split")
    ages = df[paths.AGE].to_numpy()[rows]
    sexes = df[paths.SEX].to_numpy()[rows]
    units = df[paths.PSU].to_numpy()[rows]
    n = n or cfg["panel"]["n_personas"]
    pick = select_panel(key, ages, sexes, units, n, cfg["panel"]["selection_seed"])
    codes = key["code"].to_numpy()[pick].tolist()
    personas = main_run.load_personas()
    return {
        "codes": codes,
        "persona": {c: personas[c] for c in codes},
        "units": units[pick],
        "segments": np.array([segment_label(a, s, cfg["segments"]) for a, s in zip(ages[pick], sexes[pick])]),
        "c0_text": persona.render_c0(),
    }


def cost_planning(cfg, calls_by_model):
    """Expected USD and the cap. The cap is what the runner stops at, and what the human approves."""
    plan = cfg["planning"]
    expected = {}
    for model, calls in calls_by_model.items():
        tok = plan["tokens_per_call"][model]
        price = settings.price_of(cfg, model)
        expected[model] = calls * (tok["input"] * price["input"] + tok["output"] * price["output"]) / 1_000_000
    total = sum(expected.values())
    return {"expected_by_model": {m: round(v, 4) for m, v in expected.items()}, "expected_usd": round(total, 4), "cost_cap_usd": round(total * plan["safety_factor"], 4)}


def absolute_worst_case(cfg, calls_by_model):
    """Every call at the output cap. Shown for information: the cap above is what actually stops the run."""
    total = 0.0
    for model, calls in calls_by_model.items():
        price = settings.price_of(cfg, model)
        total += calls * (cfg["planning"]["tokens_per_call"][model]["input"] * price["input"] + cfg["request"]["max_output_tokens"] * price["output"]) / 1_000_000
    return round(total, 2)


class RealBackend:
    """Calls the API. Everything it returns to the caller is aggregate."""

    def __init__(self, cfg, api_key, client=None, log_path=settings.PANEL_LOG, cache_dir=settings.CACHE_DIR, panel_loader=load_real_panel, enforce_freeze=True):
        self.cfg = cfg
        self.template = settings.load_prompt()
        self.api_key = api_key
        self.client = client
        self.log_path = Path(log_path)
        self.cache_dir = Path(cache_dir)
        self.panel_loader = panel_loader
        self.enforce_freeze = enforce_freeze
        self._panel = None

    def panel(self, n=None):
        if self._panel is None or (n and len(self._panel["codes"]) != n):
            self._panel = self.panel_loader(self.cfg, n)
        return self._panel

    def items_for(self, condition, card_id, card_text, codes, personas, c0_text=None, c0_calls=0):
        if condition == "C0":
            return [{"condition": "C0", "card": card_id, "code": f"C0_{card_id}_{i:02d}", "persona": render(self.template, card_text, c0_text)} for i in range(c0_calls)]
        return [{"condition": condition, "card": card_id, "code": c, "persona": render(self.template, card_text, personas[c])} for c in codes]

    def run_items(self, model, items, ledger, progress=None):
        """Run one model's items. A stop reason ends the batch with what is cached so far."""
        if not items:
            return {"counts": {"called": 0, "cached": 0, "failed": 0, "stopped": 0}, "stop_reason": None}
        runner = ConceptRunner(self.cfg, model, self.api_key, client=self.client, log_path=self.log_path, cache_dir=self.cache_dir, ledger=ledger)
        summary = runner.run(items, progress=progress)
        return {"counts": summary["counts"], "stop_reason": summary["stop_reason"]}

    def cached(self, model, item):
        path = self.cache_dir / model / f"{item['code']}_{panel_run.prompt_hash(item['persona'])[:16]}.json"
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        return record if record.get("prompt_sha256") == panel_run.prompt_hash(item["persona"]) else None

    def matrix(self, model, items):
        """n by 5 array in item order, NaN where no valid answer exists, and the reasons."""
        rows, reasons, too_long = [], [], 0
        for item in items:
            record = self.cached(model, item)
            if record is None:
                rows.append([math.nan] * 5)
                continue
            rows.append([record["answer"][f] for f in FIELDS])
            if record["answer"].get("reason"):
                reasons.append(record["answer"]["reason"])
            too_long += int(bool(record["answer"].get("reason_too_long")))
        return np.array(rows, dtype=float), reasons, too_long

    def run(self, ctx, plan, ledger, progress=None):
        """Pilot, then the full plan. Returns aggregates only."""
        panel = self.panel(plan["n_personas"])
        if self.enforce_freeze:
            settings.check_frozen(panel_hash(panel["codes"]))
            settings.require_committed()
        cards = {c: ctx.cards[c]["clean_text"] for c in plan["cards"]}
        doc = {"pilot": None, "stages": [], "complete": False, "stop_reason": None}
        pilot_cfg = self.cfg["panel"]["pilot"]
        if plan["pilot"]:
            pilot_codes = random.Random(paths.SEED).sample(panel["codes"], min(pilot_cfg["n_personas"], len(panel["codes"])))
            pilot_items = []
            for card in pilot_cfg["cards"]:
                pilot_items += self.items_for("C1", card, cards[card], pilot_codes, panel["persona"])
            s = self.run_items(pilot_cfg["model"], pilot_items, ledger, progress)
            doc["stages"].append({"stage": "pilot", "model": pilot_cfg["model"], **s})
            if s["stop_reason"] or s["counts"]["failed"]:
                doc["stop_reason"] = s["stop_reason"] or "pilot_failures"
                return doc
            order = {c: i for i, c in enumerate(panel["codes"])}
            pos = [order[c] for c in pilot_codes]
            cand = self.matrix(pilot_cfg["model"], self.items_for("C1", pilot_cfg["cards"][0], cards[pilot_cfg["cards"][0]], pilot_codes, panel["persona"]))[0]
            neg = self.matrix(pilot_cfg["model"], self.items_for("C1", pilot_cfg["cards"][1], cards[pilot_cfg["cards"][1]], pilot_codes, panel["persona"]))[0]
            gate = diagnostics.pilot_gate(cand, neg, panel["units"][pos], self.cfg["rules"])
            doc["pilot"] = gate
            if not gate["passed"]:
                doc["stop_reason"] = "pilot_negative_control_not_separated"
                return doc
        for model in plan["models"]:
            items = []
            for card, text in cards.items():
                items += self.items_for("C1", card, text, panel["codes"], panel["persona"])
            random.Random(paths.SEED).shuffle(items)
            s = self.run_items(model, items, ledger, progress)
            doc["stages"].append({"stage": "full", "model": model, **s})
            if s["stop_reason"]:
                doc["stop_reason"] = s["stop_reason"]
                return doc
        if plan["c0"]:
            c0 = plan["c0"]
            items = []
            for card in c0["cards"]:
                items += self.items_for("C0", card, cards[card], [], {}, panel["c0_text"], c0["calls_per_card"])
            s = self.run_items(c0["model"], items, ledger, progress)
            doc["stages"].append({"stage": "c0", "model": c0["model"], **s})
            if s["stop_reason"]:
                doc["stop_reason"] = s["stop_reason"]
                return doc
        doc["complete"] = True
        return doc

    def load_matrices(self, ctx, plan):
        """Answers for diagnostics. The returned arrays hold no text and no code, and reasons are only turned into counts."""
        panel = self.panel(plan["n_personas"])
        cards = {c: ctx.cards[c]["clean_text"] for c in plan["cards"]}
        answers, reasons, too_long = {}, {}, 0
        for model in plan["models"]:
            answers[model] = {}
            for card, text in cards.items():
                m, rs, tl = self.matrix(model, self.items_for("C1", card, text, panel["codes"], panel["persona"]))
                answers[model][card] = m
                too_long += tl
                reasons.setdefault(card, []).extend(rs)
        c0_answers = {}
        if plan["c0"]:
            c0 = plan["c0"]
            for card in c0["cards"]:
                c0_answers[card], _, tl = self.matrix(c0["model"], self.items_for("C0", card, cards[card], [], {}, panel["c0_text"], c0["calls_per_card"]))
                too_long += tl
        return {
            "answers": answers,
            "c0": c0_answers,
            "c0_model": plan["c0"]["model"] if plan["c0"] else None,
            "units": panel["units"],
            "segments": panel["segments"],
            "reason_tokens": {c: reason_tokens(r, ctx.text["reason_stop_tokens"]) for c, r in reasons.items()},
            "reasons_too_long": too_long,
            "panel_sha256": panel_hash(panel["codes"]),
        }


def reason_tokens(reasons, stop, top=8, min_count=5):
    """Most frequent words across all reasons of a card. Words with digits never match, and persona words are dropped."""
    counts = Counter()
    for text in reasons:
        seen = set()
        for raw in TOKEN_RE.findall(text):
            word = JOSA_RE.sub("", raw)
            if len(word) < 2 or word in stop:
                continue
            seen.add(word)
        counts.update(seen)
    return [[w, c] for w, c in counts.most_common(top) if c >= min_count]
