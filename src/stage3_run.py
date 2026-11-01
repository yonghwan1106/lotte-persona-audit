"""Stage 3 runner and scorer. Part 1 (verdict) makes no API call. Part 2 (ranking) sends only the frozen A15 prompt.

  python src/stage3_run.py prepare     the gate's 300 respondents in C1 and C2, key under runs/stage3, no calls
  python src/stage3_run.py screen      train split screen of the C2 allowlist against each A15 option, no calls
  python src/stage3_run.py freeze      hash the frozen files and the panel into manifests/frozen_stage3.json
  python src/stage3_run.py check       verify frozen files and commit state, no calls
  python src/stage3_run.py smoke       3 C2 and 3 C1 calls, validity and token means only, cost projection
  python src/stage3_run.py run         all codes in the frozen order under the USD 3 budget of this stage
  python src/stage3_run.py status      spend and call counts from this stage's log, --write saves aggregates
  python src/stage3_run.py verdict     v1 and v2 trust maps on stored stage 2 answers and on stand-in panels, no calls
  python src/stage3_run.py score       score complete ranking answers into results/stage3

The API key is read by the runner only, from the file named in the config. Key, cache and log stay under runs/stage3,
which git ignores. Nothing here prints persona text or per-respondent answers.
"""
import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

sys.path.insert(0, str(Path(__file__).resolve().parent))

import main_run  # noqa: E402
import panel_run  # noqa: E402
from lotte_audit import baselines, data, leakguard, main_score, metrics, option_ranking as rank, paths, score, splits, verdict_study, verdict_v2  # noqa: E402

STAGE = paths.ROOT / "runs" / "stage3"
KEY = STAGE / "key.csv"
CACHE_DIR = STAGE / "cache"
LOG_DIR = STAGE / "logs"
CALL_LOG = LOG_DIR / "calls.jsonl"
RESULTS = paths.RESULTS / "stage3"
RUN_CONFIG = paths.CONFIG / "stage3_run.json"
PROMPT = paths.CONFIG / "stage3_prompt.json"
PREREG = paths.CONFIG / "prereg_stage3.json"
FROZEN = paths.MANIFESTS / "frozen_stage3.json"
FROZEN_FILES = (
    "config/prereg_stage3.json",
    "config/stage3_run.json",
    "config/stage3_prompt.json",
    "config/gate_run.json",
    "config/gate_prompt.json",
    "config/allowlist_final.json",
    "config/persona_templates.json",
    "config/leak_patterns.json",
    "src/stage3_run.py",
    "src/panel_run.py",
    "src/main_run.py",
    "src/lotte_audit/verdict.py",
    "src/lotte_audit/verdict_v2.py",
    "src/lotte_audit/verdict_study.py",
    "src/lotte_audit/option_ranking.py",
    "src/lotte_audit/calibration.py",
    "src/lotte_audit/main_score.py",
    "src/lotte_audit/metrics.py",
)
SHARED_WITH_GATE = ("endpoint", "api_key_file", "request")
FIELDS = tuple(f"opt_{o:02d}" for o in rank.OPTIONS)
SCHEMA = {
    "type": "object",
    "properties": {f: {"type": "number", "minimum": 0, "maximum": 1} for f in FIELDS},
    "required": list(FIELDS),
    "additionalProperties": False,
}


# ---------- config and freeze ----------


def load_config():
    """The frozen stage 3 config. Refuses when the request differs from the gate or the prompt no longer matches its hash."""
    cfg = json.loads(RUN_CONFIG.read_text(encoding="utf-8"))
    gate_cfg, _ = panel_run.load_config()
    for field in SHARED_WITH_GATE:
        if cfg[field] != gate_cfg[field]:
            raise RuntimeError(f"config/stage3_run.json differs from config/gate_run.json on {field}")
    if cfg["models"]["main"] != gate_cfg["models"]["main"]:
        raise RuntimeError("config/stage3_run.json differs from config/gate_run.json on the main model")
    template = json.loads(PROMPT.read_text(encoding="utf-8"))["template"]
    if panel_run.template_sha256(template) != cfg["prompt_sha256"]:
        raise RuntimeError("config/stage3_prompt.json changed since config/stage3_run.json was frozen")
    return cfg, template


def panel_hash(key):
    rows = key.sort_values(["condition", "row_index"])[["condition", "row_index"]]
    return hashlib.sha256(rows.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def current_hashes(key):
    return {"files": {name: main_run.file_hash(name) for name in FROZEN_FILES}, "panel_sha256": panel_hash(key)}


def freeze():
    FROZEN.write_text(json.dumps(current_hashes(load_key()), indent=2), encoding="utf-8")


def check_frozen(key):
    """Refuse when a frozen file or the panel changed since freeze, and keep the earlier stages' own checks as well."""
    main_run.check_frozen(main_run.load_key())
    expected = json.loads(FROZEN.read_text(encoding="utf-8"))
    now = current_hashes(key)
    changed = [k for k in expected["files"] if expected["files"][k] != now["files"].get(k)]
    if changed:
        raise RuntimeError(f"frozen files changed since freeze: {changed}")
    if expected["panel_sha256"] != now["panel_sha256"]:
        raise RuntimeError("the stage 3 panel changed since freeze")


def require_committed():
    """No call and no score before the frozen plan is in git."""
    names = [*FROZEN_FILES, "manifests/frozen_stage3.json"]
    for name in names:
        if subprocess.run(["git", "-C", str(paths.ROOT), "ls-files", "--error-unmatch", name], capture_output=True).returncode != 0:
            raise RuntimeError(f"{name} is not committed")
    if subprocess.run(["git", "-C", str(paths.ROOT), "diff", "--quiet", "HEAD", "--", *names]).returncode != 0:
        raise RuntimeError("frozen files have uncommitted changes")


# ---------- panel ----------


def build_key(main_key, gate_key):
    """The gate's test respondents in C1 and C2, with their gate codes and gate panel weights."""
    sub = main_key.loc[(main_key.gate_code == 1) & (main_key.split == "test") & main_key.condition.isin(["C1", "C2"]), ["condition", "code", "row_index"]]
    weights = gate_key.set_index("code")["panel_weight"]
    out = sub.assign(panel_weight=weights.reindex(sub["code"]).to_numpy())
    if out["panel_weight"].isna().any():
        raise RuntimeError("a stage 3 code has no gate weight")
    return out.sort_values(["condition", "row_index"]).reset_index(drop=True)


def prepare():
    gate_key = score.load_key()
    main_key = main_run.load_key()
    key = build_key(main_key, gate_key)
    personas = main_run.load_personas()
    for code in key["code"]:
        leakguard.scan_text(personas[code])
    df, _ = data.load_sav()
    mk = splits.masks(splits.load_manifest(df))
    c1 = key.loc[key.condition == "C1", "row_index"].to_numpy()
    c2 = key.loc[key.condition == "C2", "row_index"].to_numpy()
    if c1.tolist() != c2.tolist() or not mk["test"][c1].all():
        raise RuntimeError("the two conditions must hold the same test respondents")
    STAGE.mkdir(parents=True, exist_ok=True)
    key.to_csv(KEY, index=False, encoding="utf-8")
    units = df[paths.PSU].to_numpy()
    panel_rows = main_key.loc[(main_key.split == "test") & (main_key.condition == "C1"), "row_index"].to_numpy()
    outside = mk["test"].copy()
    outside[panel_rows] = False
    design = {
        "respondents": int(len(c1)),
        "conditions": ["C2", "C1"],
        "calls_needed": int(len(key)),
        "units_of_respondents": int(len(set(units[c1]))),
        "test_split_rows": int(mk["test"].sum()),
        "panel_1000_rows_excluded_from_truth": int(len(panel_rows)),
        "truth_rows": int(outside.sum()),
        "truth_units": int(len(set(units[outside]))),
        "respondents_in_truth": int(outside[c1].sum()),
        "gate_weight_max_over_median": round(float(key["panel_weight"].max() / key["panel_weight"].median()), 2),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "panel_design.json").write_text(json.dumps(design, indent=2), encoding="utf-8")
    return design


def load_key():
    return pd.read_csv(KEY, dtype={"code": str})


def stage_items(key, personas, condition):
    sub = key.loc[key.condition == condition]
    items = [{"condition": condition, "code": c, "persona": personas[c]} for c in sub["code"]]
    random.Random(paths.SEED).shuffle(items)
    return items


# ---------- screen ----------


def allowlist_screen():
    """Train split only. The allowlist was screened on the three old targets, so check it against each option. AUC only, no counts or shares."""
    df, meta = data.load_sav()
    train = splits.masks(splits.load_manifest(df))["train"]
    allow = json.loads((paths.CONFIG / "allowlist_final.json").read_text(encoding="utf-8"))["items"]
    threshold = leakguard.load_patterns()["screen_auc_threshold"]
    w = df[paths.WEIGHT].to_numpy()[train]
    a15 = df["A15_1"].to_numpy()[train]
    rows = []
    no_positive = []
    for option in rank.OPTIONS:
        y = (a15 == option).astype(int)
        if y.min() == y.max():
            no_positive.append(option)
            continue
        best = (0.0, None)
        over = []
        for item in allow:
            auc = leakguard.univariate_auc(df[item["var"]].to_numpy()[train], y, w)
            if auc > best[0]:
                best = (auc, item["var"])
            if auc > threshold:
                over.append({"var": item["var"], "label": data.var_label(meta, item["var"])[:60], "auc": round(auc, 3)})
        rows.append({"option": option, "highest_auc": round(best[0], 3), "highest_var": best[1], "over_threshold": over})
    return {
        "what": "Larger of ordered and category-encoded univariate AUC, folded above 0.5, on the train split, as in the original screen. The C2 allowlist was screened against ever, weekly and carb only.",
        "threshold": threshold,
        "options_with_no_train_respondent": no_positive,
        "by_option": rows,
    }


# ---------- calling ----------


def build_request(cfg, model, prompt):
    req = cfg["request"]
    return {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "text": {"format": {"type": "json_schema", "name": "option_answer", "strict": True, "schema": SCHEMA}},
        "store": req["store"],
        "reasoning": {"effort": req["reasoning_effort"]},
        "service_tier": req["service_tier"],
        "prompt_cache_options": {"mode": req["prompt_cache_mode"]},
        "max_output_tokens": req["max_output_tokens"],
    }


def parse_answer(body):
    """The validated answer dict from a Responses API body, or raise AnswerError. A zero sum cannot be normalised."""
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
    if not isinstance(answer, dict) or set(answer) != set(FIELDS):
        raise panel_run.AnswerError("wrong_fields")
    for f in FIELDS:
        v = answer[f]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise panel_run.AnswerError("value_out_of_schema")
    if sum(answer[f] for f in FIELDS) <= 0:
        raise panel_run.AnswerError("zero_sum")
    return {f: float(answer[f]) for f in FIELDS}


class Stage3Runner(panel_run.Runner):
    """The gate runner with this stage's schema, parser, cache and ledger. panel_run.py itself is left unchanged."""

    def one_attempt(self, item, prompt, attempt):
        """One HTTP call. Same stop, retry and billing behaviour as panel_run.Runner.one_attempt."""
        reserve = self.worst_case_cost(prompt)
        if not self.ledger.reserve(reserve):
            self.halt("budget")
            return None, None
        base = {"condition": item["condition"], "code": item["code"], "attempt": attempt}
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
        except panel_run.AnswerError as exc:
            self.log(**base, status="bad_answer", error=panel_run.scrub(exc), **fields)
            return None, 1.0
        self.log(**base, status="ok", **fields)
        return {"code": item["code"], "condition": item["condition"], "model": self.model, "prompt_sha256": panel_run.prompt_hash(prompt), "answer": answer, "raw_sum": sum(answer.values()), **fields}, None


def run_all(cfg, template, key, personas, api_key, client=None, sleep=None, log_path=CALL_LOG, cache_dir=CACHE_DIR, progress=100, items_by_condition=None):
    """All conditions in the frozen order. Stops at the first stop reason or failed code."""
    model = cfg["models"]["main"]["id"]
    ledger = panel_run.Ledger(cfg["limits"]["budget_usd"], panel_run.spent_from_log(log_path))
    extra = {} if sleep is None else {"sleep": sleep}
    summaries = []
    for cond in cfg["run_order"]:
        items = items_by_condition[cond] if items_by_condition else stage_items(key, personas, cond)
        runner = Stage3Runner(cfg, template, model, api_key, client=client, log_path=log_path, cache_dir=cache_dir, ledger=ledger, **extra)
        print(f"start {cond} codes={len(items)} stage_spent_usd={ledger.spent:.4f}", flush=True)
        summary = {"stage": cond, **runner.run(items, progress=progress)}
        print(json.dumps(summary), flush=True)
        summaries.append(summary)
        if summary["stop_reason"] or summary["counts"]["failed"]:
            return summaries, False
    return summaries, True


# ---------- answers ----------


def load_answers(model, condition, key, personas, template, cache_dir=CACHE_DIR):
    """(raw array aligned to sorted row_index) or None when any answer is missing. A partial set is not scored."""
    sub = key.loc[key.condition == condition].sort_values("row_index")
    rows = []
    for code in sub["code"]:
        prompt = panel_run.render(template, personas[code])
        full = panel_run.prompt_hash(prompt)
        path = Path(cache_dir) / model / f"{code}_{full[:16]}.json"
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("prompt_sha256") != full:
            return None
        rows.append([record["answer"][f] for f in FIELDS])
    return np.array(rows, dtype=float)


def share_by_group(options, weights, ages):
    return rank.group_shares(rank.one_hot(options), weights, ages)


def build_ranking_context(df, df_2024, main_key, key):
    """Arrays for scoring. Truth is the test split without any of the 1000 panel respondents."""
    mk = splits.masks(splits.load_manifest(df))
    w = df[paths.WEIGHT].to_numpy()
    options = df["A15_1"].to_numpy().astype(int)
    ages = df[paths.AGE].astype(int).to_numpy()
    units = df[paths.PSU].to_numpy()
    cells = data.cell_id(df)
    panel_rows = main_key.loc[(main_key.split == "test") & (main_key.condition == "C1"), "row_index"].to_numpy()
    outside = mk["test"].copy()
    outside[panel_rows] = False
    gate = key.loc[key.condition == "C1"].sort_values("row_index")
    gate_rows = gate["row_index"].to_numpy()
    if outside[gate_rows].any():
        raise RuntimeError("a panel respondent is in the truth")
    pool = np.flatnonzero(mk["calibration"])
    # Sensitivity weights: outside rows re-scaled to the whole test split's psfwt total in each age by sex cell.
    scale = np.ones(len(df))
    for c in np.unique(cells[mk["test"]]):
        in_cell = cells == c
        scale[in_cell] = w[mk["test"] & in_cell].sum() / w[outside & in_cell].sum()
    return {
        "truth": {"options": options[outside], "w": w[outside], "w_poststratified": (w * scale)[outside], "ages": ages[outside], "units": units[outside]},
        "gate": {"options": options[gate_rows], "w": gate["panel_weight"].to_numpy(), "ages": ages[gate_rows], "units": units[gate_rows]},
        "pool": {"options": options[pool], "w": w[pool], "ages": ages[pool], "units": units[pool]},
        "train": share_by_group(options[mk["train"]], w[mk["train"]], ages[mk["train"]]),
        "krei_2024": share_by_group(df_2024["A15_1"].to_numpy().astype(int), df_2024[paths.WEIGHT].to_numpy(), df_2024[paths.AGE].astype(int).to_numpy()),
    }


def load_2024():
    df, _ = pyreadstat.read_sav(str(paths.SAV_2024), usecols=["A15_1", paths.WEIGHT, paths.AGE])
    return df


# ---------- commands ----------


def cmd_prepare(_args):
    print(json.dumps(prepare(), indent=2))


def cmd_screen(_args):
    result = allowlist_screen()
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "allowlist_option_screen.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


def cmd_freeze(_args):
    freeze()
    print(json.dumps(json.loads(FROZEN.read_text(encoding="utf-8")), indent=2))


def cmd_check(_args):
    cfg, template = load_config()
    key = load_key()
    check_frozen(key)
    require_committed()
    print(json.dumps({"prompt_sha256": cfg["prompt_sha256"], "frozen": "ok", "committed": "ok", "codes": int(len(key)), "budget_usd": cfg["limits"]["budget_usd"], "stage_spent_usd": round(panel_run.spent_from_log(CALL_LOG), 6)}, indent=2))


def cmd_smoke(_args):
    cfg, template = load_config()
    key = load_key()
    check_frozen(key)
    require_committed()
    personas = main_run.load_personas()
    items = {c: stage_items(key, personas, c)[:3] for c in cfg["run_order"]}
    _, complete = run_all(cfg, template, key, personas, panel_run.read_api_key(cfg["api_key_file"]), items_by_condition=items, progress=None)
    rows = [json.loads(line) for line in CALL_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    means = {}
    for cond in cfg["run_order"]:
        ok = [r for r in rows if r["condition"] == cond and r["status"] == "ok"]
        means[cond] = {f: round(float(np.mean([r.get(f) or 0 for r in ok])), 6) for f in ("input_tokens", "output_tokens", "reasoning_tokens", "cost_usd", "latency_s")} if ok else None
    per_condition = int(len(key) / 2)
    projection = None if not all(means.values()) else round(sum(m["cost_usd"] * per_condition for m in means.values()), 4)
    result = {"complete": complete, "statuses": pd.Series([r["status"] for r in rows]).value_counts().to_dict(), "served_models": sorted({r["served_model"] for r in rows if r.get("served_model")}), "service_tiers": sorted({r["service_tier"] for r in rows if r.get("service_tier")}), "mean_per_call": means, "projected_full_stage_usd": projection, "budget_usd": cfg["limits"]["budget_usd"], "stage_spent_usd": round(panel_run.spent_from_log(CALL_LOG), 6)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "smoke.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def cmd_run(_args):
    cfg, template = load_config()
    key = load_key()
    check_frozen(key)
    require_committed()
    personas = main_run.load_personas()
    _, complete = run_all(cfg, template, key, personas, panel_run.read_api_key(cfg["api_key_file"]))
    print(json.dumps({"complete": complete, "stage_spent_usd": round(panel_run.spent_from_log(CALL_LOG), 6)}), flush=True)
    if not complete:
        sys.exit(3)


def cmd_status(args):
    summary = panel_run.summarize_log(CALL_LOG)
    summary["stage_total_usd"] = summary.pop("gate_total_usd")
    print(json.dumps(summary, indent=2))
    if args.write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "stage3_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def cmd_verdict(_args):
    key = load_key()
    check_frozen(key)
    require_committed()
    cfg_main, template = main_run.load_config()
    main_key = main_run.load_key()
    personas = main_run.load_personas()
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    plan = prereg["part1_verdict"]["plan"]
    df, _ = data.load_sav()
    baseline_doc = json.loads((paths.RESULTS / "baselines.json").read_text(encoding="utf-8"))
    ctx = main_score.build_context(df, main_key, baseline_doc)
    answers = {}
    for stage in cfg_main["run_order"]:
        got = main_run.load_answer_arrays(stage["model"], stage["condition"], main_key, personas, template)
        if got is None:
            raise SystemExit(f"stage 2 answers missing for {stage}")
        answers[main_score.label(stage["model"], stage["condition"])] = got
    answers_doc = verdict_study.study_answers(ctx, answers, plan)
    stored = json.loads((paths.RESULTS / "main" / "main_score.json").read_text(encoding="utf-8"))["trust_map"]
    stored_map = {(v["item"], v["model"], v["condition"]): (v["verdict"], v["winning_estimators"], v["level_trusted"]) for v in stored}
    mismatch = [r for r in answers_doc["rows"] if stored_map[(r["item"], r["model"], r["condition"])] != (r["v1"]["verdict"], r["v1"]["winning_estimators"], r["v1"]["beats_e2"])]

    targets = data.derive_targets(df)
    train = splits.masks(splits.load_manifest(df))["train"]
    test_rows = main_key.loc[(main_key.split == "test") & (main_key.condition == "C1")].sort_values("row_index")["row_index"].to_numpy()
    pool_rows = main_key.loc[(main_key.split == "calibration") & (main_key.condition == "C1")].sort_values("row_index")["row_index"].to_numpy()
    surrogate = verdict_study.study_answers(ctx, verdict_study.surrogate_answers(df, targets, train, test_rows, pool_rows), plan)
    controls = verdict_study.known_signal_answers(df, targets, train, test_rows, pool_rows, prereg["part1_verdict"]["positive_control_strengths"])
    control_doc = verdict_study.study_answers(ctx, controls, plan)
    control_doc["auc"] = {k.split("|")[0]: {t: round(metrics.weighted_auc(ctx["panel"]["y"][t], v["test"][t], ctx["panel"]["w"]), 4) for t in ctx["items"]} for k, v in controls.items()}
    doc = {
        "not_preregistered_for_stage2_answers": "v2 was written after the stage 2 answers were seen, because v1 failed to discriminate. It is not pre-registered with respect to those answers.",
        "rule_version": verdict_v2.RULE_VERSION,
        "v1_reproduced_from_main_score": not mismatch,
        "answers": answers_doc,
        "surrogate": surrogate,
        "positive_control": control_doc,
        "frozen": json.loads(FROZEN.read_text(encoding="utf-8")),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "verdict_v2.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    text = verdict_study.to_markdown(doc)
    (RESULTS / "verdict_v2.md").write_text(text, encoding="utf-8")
    print(text)
    print(json.dumps({"v1_mismatches": len(mismatch)}))


def cmd_score(_args):
    cfg, template = load_config()
    key = load_key()
    check_frozen(key)
    require_committed()
    personas = main_run.load_personas()
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    model = cfg["models"]["main"]["id"]
    answers, sums, incomplete = {}, {}, []
    for cond in cfg["run_order"]:
        raw = load_answers(model, cond, key, personas, template)
        if raw is None:
            incomplete.append(cond)
            continue
        answers[cond], s = rank.normalise_answers(raw)
        sums[cond] = rank.sum_check(s)
    if not answers:
        raise SystemExit("no complete condition to score")
    df, _ = data.load_sav()
    ctx = build_ranking_context(df, load_2024(), main_run.load_key(), key)
    result = rank.score_ranking(ctx, answers, prereg["part2_ranking"]["plan"])
    result["sum_check"] = sums
    result["incomplete"] = incomplete
    result["frozen"] = json.loads(FROZEN.read_text(encoding="utf-8"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "option_ranking.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {"frame": prereg["part2_ranking"]["frame_for_results"], "sum_check": sums, "truth_rows": int(len(ctx["truth"]["w"])), "truth_units": int(len(set(ctx["truth"]["units"].tolist()))), "scored": sorted(answers), "incomplete": incomplete}
    text = rank.to_markdown(result, cfg["option_labels"], meta)
    (RESULTS / "option_ranking.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in (("prepare", cmd_prepare), ("screen", cmd_screen), ("freeze", cmd_freeze), ("check", cmd_check), ("smoke", cmd_smoke), ("run", cmd_run), ("verdict", cmd_verdict), ("score", cmd_score)):
        sub.add_parser(name).set_defaults(func=fn)
    s = sub.add_parser("status")
    s.add_argument("--write", action="store_true")
    s.set_defaults(func=cmd_status)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
