"""Gate runner. One OpenAI Responses API call per respondent code, nothing else in the call.

  python src/panel_run.py check                 verify the frozen run config, no calls
  python src/panel_run.py smoke                 3 C1 and 3 C2 calls on the main model, cost projection
  python src/panel_run.py run --model ID        all codes in runs/gate/key.csv for one model
  python src/panel_run.py answers --model ID    cached answers to runs/gate/answers_<model>/*.csv
  python src/panel_run.py status                spend and call counts from the call log

The API key is read at runtime from the file named in config/gate_run.json and is only ever placed in
the Authorization header. Answers, the cache and the call log stay under runs/, which git ignores.
Nothing here prints persona text or per-respondent answers.
"""
import argparse
import hashlib
import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lotte_audit import leakguard, paths  # noqa: E402

GATE_RUN = paths.CONFIG / "gate_run.json"
GATE_PROMPT = paths.CONFIG / "gate_prompt.json"
CACHE_DIR = paths.GATE / "cache"
LOG_DIR = paths.GATE / "logs"
CALL_LOG = LOG_DIR / "calls.jsonl"
SMOKE_RESULT = paths.RESULTS / "gate_smoke.json"
FIELDS = ("p_zero_ever", "p_zero_weekly", "p_carb_top1")
SCHEMA = {
    "type": "object",
    "properties": {f: {"type": "number", "minimum": 0, "maximum": 1} for f in FIELDS},
    "required": list(FIELDS),
    "additionalProperties": False,
}
SECRET_RE = re.compile(r"sk-[A-Za-z0-9_\-*]{4,}")
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 520, 522, 524, 529}


class AnswerError(ValueError):
    """The model returned something that is not a valid answer."""


def scrub(text):
    """Remove anything shaped like a key from text bound for a log, including masked echoes in error bodies."""
    return SECRET_RE.sub("[redacted]", str(text))[:300]


def template_sha256(template):
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


def load_config():
    """Load the frozen run config and refuse to continue if the prompt no longer matches its hash."""
    cfg = json.loads(GATE_RUN.read_text(encoding="utf-8"))
    template = json.loads(GATE_PROMPT.read_text(encoding="utf-8"))["template"]
    got = template_sha256(template)
    if got != cfg["prompt_sha256"]:
        raise RuntimeError("config/gate_prompt.json changed since config/gate_run.json was frozen")
    return cfg, template


def render(template, persona):
    if template.count("{PERSONA}") != 1:
        raise ValueError("template must hold exactly one {PERSONA}")
    return template.replace("{PERSONA}", persona)


def prompt_hash(prompt):
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def load_items(inputs_dir=None, key_path=None):
    """Read (condition, code, persona) from the batch files and check them against the key and the guard."""
    inputs_dir = Path(inputs_dir or paths.GATE_INPUTS)
    key = pd.read_csv(key_path or paths.GATE_KEY, dtype={"code": str})
    cond_of = dict(zip(key["code"], key["condition"]))
    items = []
    for path in sorted(inputs_dir.glob("*_batch*.txt")):
        body = path.read_text(encoding="utf-8").split("----\n", 1)[1]
        for code, text in re.findall(r"code: ([A-Z2-9]{8})\n(.*?)(?=\n\ncode: |\n*$)", body, flags=re.S):
            cond = path.name[:2]
            if cond_of.get(code) != cond:
                raise RuntimeError(f"code in {path.name} does not match the key")
            leakguard.scan_text(text)
            items.append({"condition": cond, "code": code, "persona": text})
    if {i["code"] for i in items} != set(key["code"]) or len(items) != len(key):
        raise RuntimeError("batch files and key disagree on the set of codes")
    random.Random(paths.SEED).shuffle(items)
    return items


def build_request(cfg, model, prompt):
    req = cfg["request"]
    return {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "text": {"format": {"type": "json_schema", "name": "panel_answer", "strict": True, "schema": SCHEMA}},
        "store": req["store"],
        "reasoning": {"effort": req["reasoning_effort"]},
        "service_tier": req["service_tier"],
        "prompt_cache_options": {"mode": req["prompt_cache_mode"]},
        "max_output_tokens": req["max_output_tokens"],
    }


def price_of(cfg, model):
    for m in cfg["models"].values():
        if m["id"] == model:
            return m["usd_per_1m"]
    raise KeyError(f"model {model} is not in config/gate_run.json")


def call_cost(usage, price):
    """USD for one response usage block, following the prompt caching guide's formula."""
    details = usage.get("input_tokens_details") or {}
    cached = details.get("cached_tokens") or 0
    write = details.get("cache_write_tokens") or 0
    ordinary = usage["input_tokens"] - cached - write
    total = ordinary * price["input"] + cached * price["cached_input"] + write * price["cache_write_30m"] + usage["output_tokens"] * price["output"]
    return total / 1_000_000


def parse_answer(body):
    """Return the validated answer dict from a Responses API body, or raise AnswerError."""
    if body.get("status") != "completed":
        reason = (body.get("incomplete_details") or {}).get("reason")
        raise AnswerError(f"status_{body.get('status')}_{reason}")
    texts = []
    for item in body.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "refusal":
                raise AnswerError("refusal")
            if part.get("type") == "output_text":
                texts.append(part.get("text", ""))
    if not texts:
        raise AnswerError("no_output_text")
    try:
        answer = json.loads("".join(texts))
    except json.JSONDecodeError as exc:
        raise AnswerError("not_json") from exc
    if not isinstance(answer, dict) or set(answer) != set(FIELDS):
        raise AnswerError("wrong_fields")
    for f in FIELDS:
        v = answer[f]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise AnswerError("value_out_of_schema")
    return {f: float(answer[f]) for f in FIELDS}


class Ledger:
    """Spend across the whole gate. Reservations make it impossible to pass the budget with calls in flight."""

    def __init__(self, budget, spent=0.0):
        self.budget = budget
        self.spent = spent
        self.reserved = 0.0
        self.lock = threading.Lock()

    def reserve(self, amount):
        with self.lock:
            if self.spent + self.reserved + amount >= self.budget:
                return False
            self.reserved += amount
            return True

    def settle(self, reserved, actual):
        with self.lock:
            self.reserved -= reserved
            self.spent += actual


def spent_from_log(log_path):
    log_path = Path(log_path)
    if not log_path.exists():
        return 0.0
    total = 0.0
    with log_path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                total += json.loads(line).get("cost_usd", 0.0)
    return total


class Runner:
    def __init__(self, cfg, template, model, api_key, client=None, log_path=CALL_LOG, cache_dir=CACHE_DIR, sleep=time.sleep, ledger=None, concurrency=None):
        self.cfg = cfg
        self.template = template
        self.model = model
        self.price = price_of(cfg, model)
        self.req = cfg["request"]
        self.limits = cfg["limits"]
        self.url = cfg["endpoint"]
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.client = client or httpx.Client(timeout=self.limits["timeout_s"])
        self.log_path = Path(log_path)
        self.cache_dir = Path(cache_dir) / model
        self.sleep = sleep
        self.ledger = ledger or Ledger(self.limits["budget_usd"], spent_from_log(self.log_path))
        self.concurrency = concurrency or self.limits["concurrency"]
        self.stop_reason = None
        self.stop_lock = threading.Lock()
        self.log_lock = threading.Lock()
        self.consecutive_failures = 0
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_path(self, code, prompt):
        return self.cache_dir / f"{code}_{prompt_hash(prompt)[:16]}.json"

    def halt(self, reason):
        with self.stop_lock:
            if self.stop_reason is None:
                self.stop_reason = reason

    def log(self, **row):
        row = {"ts": round(time.time(), 3), "model": self.model, **row}
        with self.log_lock:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    def worst_case_cost(self, prompt):
        # Bytes bound the token count; the small constant covers hidden system tokens.
        tokens = len(prompt.encode("utf-8")) + 500
        return (tokens * self.price["input"] + self.req["max_output_tokens"] * self.price["output"]) / 1_000_000

    def one_attempt(self, item, prompt, attempt):
        """One HTTP call. Returns (answer record or None, retry delay or None). Sets stop_reason on fatal errors."""
        reserve = self.worst_case_cost(prompt)
        if not self.ledger.reserve(reserve):
            self.halt("budget")
            return None, None
        base = {"condition": item["condition"], "code": item["code"], "attempt": attempt}
        t0 = time.time()
        try:
            resp = self.client.post(self.url, headers=self.headers, json=build_request(self.cfg, self.model, prompt))
        except httpx.HTTPError as exc:
            # The request may have been billed with no usage returned, so the worst case goes on the ledger.
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
            self.log(**base, status=f"http_{resp.status_code}", http_status=resp.status_code, error=scrub(code), latency_s=latency, cost_usd=0.0)
            # No credit is an account state, so retries cannot help. The 429 carries type insufficient_quota
            # with code credit_balance_exhausted when the balance is empty.
            if err.get("type") == "insufficient_quota" or code in ("insufficient_quota", "credit_balance_exhausted"):
                self.halt("insufficient_quota")
                return None, None
            if resp.status_code not in RETRY_STATUS:
                self.halt(f"fatal_http_{resp.status_code}_{scrub(code)}")
                return None, None
            after = resp.headers.get("retry-after")
            try:
                delay = float(after) if after else min(60.0, 2.0**attempt)
            except ValueError:
                delay = min(60.0, 2.0**attempt)
            return None, delay + random.uniform(0, 1)
        body = resp.json()
        usage = body.get("usage") or {}
        cost = call_cost(usage, self.price) if usage else reserve
        self.ledger.settle(reserve, cost)
        details_in = usage.get("input_tokens_details") or {}
        details_out = usage.get("output_tokens_details") or {}
        fields = dict(
            http_status=200,
            latency_s=latency,
            served_model=body.get("model"),
            service_tier=body.get("service_tier"),
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
            answer = parse_answer(body)
        except AnswerError as exc:
            self.log(**base, status="bad_answer", error=scrub(exc), **fields)
            return None, 1.0
        self.log(**base, status="ok", **fields)
        return {"code": item["code"], "condition": item["condition"], "model": self.model, "prompt_sha256": prompt_hash(prompt), "answer": answer, **fields}, None

    def one_code(self, item):
        prompt = render(self.template, item["persona"])
        path = self.cache_path(item["code"], prompt)
        if path.exists():
            return "cached"
        for attempt in range(1, self.limits["max_attempts"] + 1):
            if self.stop_reason:
                return "stopped"
            record, delay = self.one_attempt(item, prompt, attempt)
            if record is not None:
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(record, ensure_ascii=True), encoding="utf-8")
                tmp.replace(path)
                with self.stop_lock:
                    self.consecutive_failures = 0
                return "called"
            if delay is None:
                return "stopped"
            self.sleep(delay)
        self.log(condition=item["condition"], code=item["code"], attempt=self.limits["max_attempts"], status="gave_up", cost_usd=0.0)
        with self.stop_lock:
            self.consecutive_failures += 1
            trip = self.consecutive_failures >= self.limits["persistent_failure_codes"]
        if trip:
            self.halt("persistent_failures")
        return "failed"

    def run(self, items, progress=None):
        counts = {"called": 0, "cached": 0, "failed": 0, "stopped": 0}
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [pool.submit(self.one_code, item) for item in items]
            for i, fut in enumerate(as_completed(futures), start=1):
                counts[fut.result()] += 1
                if progress and i % progress == 0:
                    print(f"done {i}/{len(items)} {counts} spent_usd={self.ledger.spent:.4f} stop={self.stop_reason}", flush=True)
        return {"model": self.model, "counts": counts, "stop_reason": self.stop_reason, "gate_spent_usd": round(self.ledger.spent, 6)}


def read_api_key(path):
    key = Path(path).read_text(encoding="utf-8-sig").strip()
    if not key:
        raise RuntimeError("API key file is empty")
    return key


def cached_records(model, items, template, cache_dir=CACHE_DIR):
    out, missing = {}, []
    for item in items:
        prompt = render(template, item["persona"])
        path = Path(cache_dir) / model / f"{item['code']}_{prompt_hash(prompt)[:16]}.json"
        if path.exists():
            out[item["code"]] = json.loads(path.read_text(encoding="utf-8"))
        else:
            missing.append(item["code"])
    return out, missing


def write_answers(model, items, template, cache_dir=CACHE_DIR, out_root=None):
    """Write one CSV per condition. Refuses to write a partial set, since score would refuse it anyway."""
    records, missing = cached_records(model, items, template, cache_dir)
    if missing:
        raise RuntimeError(f"{len(missing)} codes have no cached answer for {model}")
    out_dir = Path(out_root or paths.GATE) / f"answers_{model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [{"condition": i["condition"], "code": i["code"], **records[i["code"]]["answer"]} for i in items]
    frame = pd.DataFrame(rows)
    for cond, sub in frame.groupby("condition"):
        sub.drop(columns="condition").sort_values("code").to_csv(out_dir / f"{cond}.csv", index=False, encoding="utf-8")
    return out_dir, len(rows)


def smoke_items(items, n=3):
    picked = []
    for cond in ("C1", "C2"):
        picked += [i for i in items if i["condition"] == cond][:n]
    return picked


def mean_tokens(records):
    keys = ("input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens", "cache_write_tokens", "cost_usd", "latency_s")
    return {k: sum((r.get(k) or 0) for r in records) / len(records) for k in keys}


def project(cfg, by_cond):
    """Full gate cost from smoke means. C0 has no C0 smoke calls, so it uses the C1 means, which overstate it slightly."""
    counts = cfg["codes_per_condition"]
    usage = {"C0": by_cond["C1"], "C1": by_cond["C1"], "C2": by_cond["C2"]}
    out = {}
    for role, m in cfg["models"].items():
        total = 0.0
        for cond, n in counts.items():
            u = usage[cond]
            total += n * call_cost({"input_tokens": u["input_tokens"], "output_tokens": u["output_tokens"]}, m["usd_per_1m"])
        out[m["id"]] = round(total, 4)
    return out


def cmd_smoke(cfg, template, _args):
    model = cfg["models"]["main"]["id"]
    items = smoke_items(load_items())
    runner = Runner(cfg, template, model, read_api_key(cfg["api_key_file"]))
    summary = runner.run(items)
    records, missing = cached_records(model, items, template)
    by_cond = {}
    for cond in ("C1", "C2"):
        got = [r for r in records.values() if r["condition"] == cond]
        by_cond[cond] = mean_tokens(got) if got else None
    result = {
        "model": model,
        "calls_with_valid_schema": len(records),
        "missing": len(missing),
        "stop_reason": summary["stop_reason"],
        "served_models": sorted({r.get("served_model") or "" for r in records.values()}),
        "service_tiers": sorted({r.get("service_tier") or "" for r in records.values()}),
        "mean_per_call": by_cond,
        "gate_spent_usd_after_smoke": round(spent_from_log(CALL_LOG), 6),
    }
    if not missing:
        proj = project(cfg, by_cond)
        result["projected_full_gate_usd"] = proj
        result["projected_total_usd"] = round(sum(proj.values()), 4)
        result["second_model_assumption"] = "the second model is projected with the main model's token counts at its own prices"
    SMOKE_RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def cmd_run(cfg, template, args):
    if args.model not in [m["id"] for m in cfg["models"].values()]:
        raise SystemExit(f"model {args.model} is not in the frozen config")
    items = load_items()
    runner = Runner(cfg, template, args.model, read_api_key(cfg["api_key_file"]), concurrency=args.concurrency)
    print(f"start model={args.model} codes={len(items)} gate_spent_usd={runner.ledger.spent:.4f}", flush=True)
    summary = runner.run(items, progress=25)
    print(json.dumps(summary), flush=True)
    if summary["stop_reason"] or summary["counts"]["failed"]:
        sys.exit(3)
    out_dir, n = write_answers(args.model, items, template)
    print(f"answers written: {n} rows in {out_dir.name}", flush=True)


def cmd_answers(cfg, template, args):
    out_dir, n = write_answers(args.model, load_items(), template)
    print(f"answers written: {n} rows in {out_dir.name}")


def summarize_log(log_path=CALL_LOG):
    rows = []
    log_path = Path(log_path)
    if log_path.exists():
        with log_path.open(encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    out = {}
    for model in sorted({r["model"] for r in rows}):
        sub = [r for r in rows if r["model"] == model]
        statuses = {}
        for r in sub:
            statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        ok = [r for r in sub if r["status"] == "ok"]
        lat = sorted(r["latency_s"] for r in ok)
        by_cond = {}
        for cond in ("C0", "C1", "C2"):
            c = [r for r in sub if r.get("condition") == cond and r.get("http_status") == 200]
            by_cond[cond] = {
                "calls_billed": len(c),
                "input_tokens": sum(r.get("input_tokens") or 0 for r in c),
                "cached_tokens": sum(r.get("cached_tokens") or 0 for r in c),
                "cache_write_tokens": sum(r.get("cache_write_tokens") or 0 for r in c),
                "output_tokens": sum(r.get("output_tokens") or 0 for r in c),
                "reasoning_tokens": sum(r.get("reasoning_tokens") or 0 for r in c),
                "cost_usd": round(sum(r.get("cost_usd") or 0 for r in c), 6),
            }
        out[model] = {
            "attempts": len(sub),
            "statuses": statuses,
            "retried_attempts": sum(1 for r in sub if (r.get("attempt") or 1) > 1),
            "codes_ok": len({r["code"] for r in ok}),
            "cost_usd": round(sum(r.get("cost_usd", 0.0) for r in sub), 6),
            "cost_assumed_usd": round(sum(r.get("cost_usd", 0.0) for r in sub if r.get("cost_assumed")), 6),
            "latency_s_median": lat[len(lat) // 2] if lat else None,
            "latency_s_max": lat[-1] if lat else None,
            "wall_clock_s": round(max(r["ts"] for r in sub) - min(r["ts"] for r in sub), 1),
            "served_models": sorted({r["served_model"] for r in ok if r.get("served_model")}),
            "service_tiers": sorted({r["service_tier"] for r in ok if r.get("service_tier")}),
            "by_condition": by_cond,
        }
    return {"models": out, "gate_total_usd": round(sum(m["cost_usd"] for m in out.values()), 6)}


def cmd_status(_cfg, _template, args):
    summary = summarize_log()
    print(json.dumps(summary, indent=2))
    if args.write:
        (paths.RESULTS / "gate_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def cmd_check(cfg, _template, _args):
    items = load_items()
    print(f"config ok, prompt_sha256 {cfg['prompt_sha256']}, codes {len(items)}, models {[m['id'] for m in cfg['models'].values()]}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("smoke").set_defaults(func=cmd_smoke)
    r = sub.add_parser("run")
    r.add_argument("--model", required=True)
    r.add_argument("--concurrency", type=int, default=None)
    r.set_defaults(func=cmd_run)
    a = sub.add_parser("answers")
    a.add_argument("--model", required=True)
    a.set_defaults(func=cmd_answers)
    s = sub.add_parser("status")
    s.add_argument("--write", action="store_true")
    s.set_defaults(func=cmd_status)
    args = parser.parse_args()
    cfg, template = load_config()
    args.func(cfg, template, args)


if __name__ == "__main__":
    main()
