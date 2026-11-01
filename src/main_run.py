"""Main stage runner. Builds on panel_run.py and sends only the frozen prompt with allowlisted persona text.

  python src/main_run.py prepare     extend the test panel, add the calibration panel, write the key, no calls
  python src/main_run.py freeze      hash the frozen files and the panel into manifests/frozen_main.json
  python src/main_run.py check       verify the frozen files, counts, reuse and projected cost, no calls
  python src/main_run.py run         all stages in the frozen order under the USD 6 budget of this stage
  python src/main_run.py status      spend and call counts from this stage's log, --write saves aggregates
  python src/main_run.py score       score complete answers into results/main

The API key is read by the runner only, from the file named in the config. Key, inputs, cache and log stay
under runs/main, which git ignores. Nothing here prints persona text or per-respondent answers.
"""
import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import panel_run  # noqa: E402
from lotte_audit import batches, data, leakguard, main_score, paths, persona, score, splits  # noqa: E402

MAIN = paths.ROOT / "runs" / "main"
KEY = MAIN / "key.csv"
PERSONAS = MAIN / "inputs" / "personas.jsonl"
CACHE_DIR = MAIN / "cache"
LOG_DIR = MAIN / "logs"
CALL_LOG = LOG_DIR / "calls.jsonl"
RESULTS = paths.RESULTS / "main"
MAIN_RUN = paths.CONFIG / "main_run.json"
PREREG = paths.CONFIG / "prereg_main.json"
FROZEN = paths.MANIFESTS / "frozen_main.json"
FROZEN_FILES = (
    "config/prereg_main.json",
    "config/main_run.json",
    "config/gate_run.json",
    "config/gate_prompt.json",
    "config/allowlist_final.json",
    "config/persona_templates.json",
    "config/leak_patterns.json",
    "src/main_run.py",
    "src/lotte_audit/verdict.py",
    "src/lotte_audit/calibration.py",
    "src/lotte_audit/main_score.py",
)
SHARED_WITH_GATE = ("models", "endpoint", "api_key_file", "request", "prompt_file", "prompt_sha256")
FORBIDDEN_COLS = (paths.HOUSEHOLD, "id", "FID", "\uc8fc\uad6c\uc785\uc790id", paths.PSU)


# ---------- config and freeze ----------


def load_config():
    """The frozen main config. Refuses when anything the prompt or request depends on differs from the gate."""
    cfg = json.loads(MAIN_RUN.read_text(encoding="utf-8"))
    gate_cfg, template = panel_run.load_config()
    for field in SHARED_WITH_GATE:
        if cfg[field] != gate_cfg[field]:
            raise RuntimeError(f"config/main_run.json differs from config/gate_run.json on {field}")
    return cfg, template


def file_hash(relative):
    # Line endings are normalised, as in score.config_hashes.
    return hashlib.sha256((paths.ROOT / relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def panel_hash(key):
    rows = key.sort_values(["split", "condition", "row_index"])[["split", "condition", "row_index", "stability"]]
    return hashlib.sha256(rows.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def current_hashes(key):
    return {"files": {name: file_hash(name) for name in FROZEN_FILES}, "panel_sha256": panel_hash(key)}


def freeze():
    FROZEN.write_text(json.dumps(current_hashes(load_key()), indent=2), encoding="utf-8")


def check_frozen(key):
    """Refuse when a frozen file or the panel changed since freeze, and keep the gate's own check as well."""
    score.check_frozen()
    expected = json.loads(FROZEN.read_text(encoding="utf-8"))
    now = current_hashes(key)
    changed = [k for k in expected["files"] if expected["files"][k] != now["files"].get(k)]
    if changed:
        raise RuntimeError(f"frozen files changed since freeze: {changed}")
    if expected["panel_sha256"] != now["panel_sha256"]:
        raise RuntimeError("the main panel changed since freeze")


def require_committed():
    """No call may happen before the frozen plan is in git."""
    names = [*FROZEN_FILES, "manifests/frozen_main.json"]
    for name in names:
        if subprocess.run(["git", "-C", str(paths.ROOT), "ls-files", "--error-unmatch", name], capture_output=True).returncode != 0:
            raise RuntimeError(f"{name} is not committed")
    if subprocess.run(["git", "-C", str(paths.ROOT), "diff", "--quiet", "HEAD", "--", *names]).returncode != 0:
        raise RuntimeError("frozen files have uncommitted changes")


# ---------- panel ----------


def extend_panel(test_positions, weights, gate_rows, n, seed):
    """The gate's rows plus a weighted draw without replacement from the rest of the test split."""
    keep = ~np.isin(test_positions, gate_rows)
    rest = test_positions[keep]
    rest_w = weights[keep]
    rng = np.random.default_rng(seed)
    extra = rng.choice(rest, size=n - len(gate_rows), replace=False, p=rest_w / rest_w.sum())
    return np.sort(np.concatenate([gate_rows, extra]))


def extension_inclusion(weights, first_n, total_n, draws, seed):
    """Monte Carlo inclusion probability of the two-stage draw, aligned with weights."""
    rng = np.random.default_rng(seed)
    m = len(weights)
    p = weights / weights.sum()
    hits = np.zeros(m)
    for _ in range(draws):
        first = rng.choice(m, size=first_n, replace=False, p=p)
        mask = np.ones(m, dtype=bool)
        mask[first] = False
        rest = np.flatnonzero(mask)
        second = rng.choice(rest, size=total_n - first_n, replace=False, p=weights[rest] / weights[rest].sum())
        hits[first] += 1
        hits[second] += 1
    return np.maximum(hits, 1) / draws


def gate_codes(gate_key):
    """{(condition, row_index): code} for the gate's C1 and C2 respondents."""
    sub = gate_key.loc[gate_key.condition.isin(["C1", "C2"])]
    return {(c, int(r)): code for c, r, code in zip(sub["condition"], sub["row_index"], sub["code"])}


def build_key(test_rows, calib_rows, analysis_weight, psfwt, gate_key, stability_rows):
    """One row per respondent and condition. Gate rows keep their gate code; new rows get unrelated codes."""
    known = gate_codes(gate_key)
    used = set(gate_key["code"])
    rows = []
    for cond_i, cond in enumerate(main_score.CONDITIONS, start=1):
        rng = np.random.default_rng([paths.SEED, 100 + cond_i])
        for split, group in (("test", test_rows), ("calibration", calib_rows)):
            fresh = [int(r) for r in group if (cond, int(r)) not in known]
            codes = dict(zip(fresh, batches.make_codes(len(fresh), rng, used)))
            for r in group.tolist():
                reused = (cond, r) in known
                rows.append(
                    {
                        "split": split,
                        "condition": cond,
                        "code": known[(cond, r)] if reused else codes[r],
                        "row_index": r,
                        "analysis_weight": float(analysis_weight[r]) if split == "test" else float(psfwt[r]),
                        "gate_code": int(reused),
                        "stability": int(split == "test" and cond == "C2" and r in stability_rows),
                    }
                )
    return pd.DataFrame(rows)


def render_persona(row, cond, templates, allowlist):
    forbidden = [row[c] for c in FORBIDDEN_COLS]
    if cond == "C1":
        return leakguard.scan_text(persona.render_c1(row, templates), forbidden)
    return persona.render_c2(row, allowlist, templates, forbidden)


def prepare():
    cfg, _ = load_config()
    plan = cfg["panel"]
    df, _meta = data.load_sav()
    mk = splits.masks(splits.load_manifest(df))
    test, calib = mk["test"], mk["calibration"]
    gate_key = score.load_key()
    psfwt = df[paths.WEIGHT].to_numpy()
    units = df[paths.PSU].to_numpy()
    gate_rows = np.sort(gate_key.loc[gate_key.condition == "C1", "row_index"].to_numpy())
    test_positions = np.flatnonzero(test)
    test_rows = extend_panel(test_positions, psfwt[test], gate_rows, plan["test_n"], plan["test_seed"])
    pi = extension_inclusion(psfwt[test], len(gate_rows), plan["test_n"], plan["pi_draws"], plan["pi_seed"])
    weight_of = np.zeros(len(df))
    weight_of[test_positions] = psfwt[test] / pi
    calib_rows = np.flatnonzero(calib)
    stability_rows = set(np.random.default_rng(plan["stability_seed"]).choice(test_rows, size=plan["stability_n"], replace=False).tolist())
    key = build_key(test_rows, calib_rows, weight_of, psfwt, gate_key, stability_rows)

    templates = persona.load_templates()
    allowlist = persona.load_final_allowlist()["items"]
    gate_text = {i["code"]: i["persona"] for i in panel_run.load_items()}
    MAIN.mkdir(parents=True, exist_ok=True)
    PERSONAS.parent.mkdir(parents=True, exist_ok=True)
    identical = differing = 0
    tmp = PERSONAS.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in key.itertuples():
            text = render_persona(df.iloc[row.row_index], row.condition, templates, allowlist)
            if row.gate_code:
                if gate_text[row.code] == text:
                    identical += 1
                else:
                    differing += 1
            fh.write(json.dumps({"code": row.code, "condition": row.condition, "persona": text}, ensure_ascii=False) + "\n")
    tmp.replace(PERSONAS)
    if differing:
        raise RuntimeError(f"{differing} gate personas no longer render to the same text")
    key.to_csv(KEY, index=False, encoding="utf-8")

    cells = data.cell_id(df)
    design = {
        "test_panel_n": int(len(test_rows)),
        "calibration_panel_n": int(len(calib_rows)),
        "test_split_n": int(test.sum()),
        "test_panel_units": int(len(set(units[test_rows]))),
        "test_split_units": int(len(set(units[test]))),
        "calibration_units": int(len(set(units[calib_rows]))),
        "units_crossing_splits": int(len(set(units[test_rows]) & set(units[calib_rows]))),
        "rows_crossing_splits": int(len(set(test_rows.tolist()) & set(calib_rows.tolist()))),
        "test_panel_all_in_test": bool(test[test_rows].all()),
        "gate_rows_kept": int(np.isin(gate_rows, test_rows).sum()),
        "test_panel_cells": int(len(set(cells[test_rows]))),
        "test_panel_min_cell_n": int(pd.Series(cells[test_rows]).value_counts().min()),
        "calibration_min_cell_n": int(pd.Series(cells[calib_rows]).value_counts().min()),
        "calibration_unit_size_min_median_max": [int(x) for x in pd.Series(units[calib_rows]).value_counts().agg(["min", "median", "max"]).tolist()],
        "analysis_weight_max_over_median": round(float(weight_of[test_rows].max() / np.median(weight_of[test_rows])), 2),
        "inclusion_probability_min_median_max": [round(float(x), 4) for x in (pi.min(), np.median(pi), pi.max())],
        "gate_personas_identical": identical,
        "gate_personas_differing": differing,
        "calls_needed": {
            cond: {
                "test_new": int(((key.condition == cond) & (key.split == "test") & (key.gate_code == 0)).sum()),
                "test_from_gate": int(((key.condition == cond) & (key.split == "test") & (key.gate_code == 1)).sum()),
                "calibration_new": int(((key.condition == cond) & (key.split == "calibration")).sum()),
            }
            for cond in main_score.CONDITIONS
        },
        "stability_rows": int(key.stability.sum()),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "panel_design.json").write_text(json.dumps(design, indent=2), encoding="utf-8")
    return design


def load_key():
    return pd.read_csv(KEY, dtype={"code": str})


def load_personas():
    with PERSONAS.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return {r["code"]: r["persona"] for r in rows}


# ---------- calling ----------


class MainRunner(panel_run.Runner):
    """Runner with this stage's cache and ledger, gate reuse on identical code and prompt, and a repeat index."""

    def __init__(self, *args, gate_cache_dir=panel_run.CACHE_DIR, repeat=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.gate_dir = Path(gate_cache_dir) / self.model
        self.repeat = repeat

    def cache_path(self, code, prompt):
        suffix = f"_r{self.repeat}" if self.repeat else ""
        return self.cache_dir / f"{code}_{panel_run.prompt_hash(prompt)[:16]}{suffix}.json"

    def log(self, **row):
        super().log(**row, repeat=self.repeat)

    def gate_record(self, code, prompt):
        return read_gate_record(self.gate_dir, code, prompt)

    def one_code(self, item):
        prompt = panel_run.render(self.template, item["persona"])
        if self.repeat == 0 and self.gate_record(item["code"], prompt) is not None:
            return "cached"
        return super().one_code(item)


def read_gate_record(gate_dir, code, prompt):
    """A gate answer, only when the cache file exists and states the same prompt hash."""
    full = panel_run.prompt_hash(prompt)
    path = Path(gate_dir) / f"{code}_{full[:16]}.json"
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    return record if record.get("prompt_sha256") == full and record.get("code") == code else None


def stage_items(key, personas, condition, only_stability=False):
    sub = key.loc[key.condition == condition]
    if only_stability:
        sub = sub.loc[sub.stability == 1]
    items = [{"condition": condition, "code": c, "persona": personas[c]} for c in sub["code"]]
    random.Random(paths.SEED).shuffle(items)
    return items


def projected_cost(cfg, key):
    """Measured gate cost per call times the calls that are new. Reused answers cost nothing here."""
    rates = cfg["cost_projection"]["usd_per_call"]
    out = {}
    total = 0.0
    for stage in cfg["run_order"]:
        n = int(((key.condition == stage["condition"]) & (key.gate_code == 0)).sum())
        cost = n * rates[stage["model"]][stage["condition"]]
        out[f"{stage['model']}|{stage['condition']}"] = {"new_calls": n, "usd": round(cost, 4)}
        total += cost
    stab = cfg["stability"]
    n = int(key.stability.sum()) * stab["extra_repeats"]
    cost = n * rates[stab["model"]][stab["condition"]]
    out["stability"] = {"new_calls": n, "usd": round(cost, 4)}
    out["total_usd"] = round(total + cost, 4)
    out["budget_usd"] = cfg["limits"]["budget_usd"]
    return out


def run_all(cfg, template, key, personas, api_key, client=None, sleep=None, log_path=CALL_LOG, cache_dir=CACHE_DIR, gate_cache_dir=panel_run.CACHE_DIR, progress=200):
    """All stages in the frozen order. Stops at the first stop reason or failed code."""
    ledger = panel_run.Ledger(cfg["limits"]["budget_usd"], panel_run.spent_from_log(log_path))
    summaries = []
    extra = {} if sleep is None else {"sleep": sleep}

    def go(model, items, repeat, name):
        runner = MainRunner(cfg, template, model, api_key, client=client, log_path=log_path, cache_dir=cache_dir, ledger=ledger, gate_cache_dir=gate_cache_dir, repeat=repeat, **extra)
        print(f"start {name} codes={len(items)} stage_spent_usd={ledger.spent:.4f}", flush=True)
        summary = {"stage": name, **runner.run(items, progress=progress)}
        print(json.dumps(summary), flush=True)
        summaries.append(summary)
        return not (summary["stop_reason"] or summary["counts"]["failed"])

    for stage in cfg["run_order"]:
        name = f"{stage['model']}|{stage['condition']}"
        if not go(stage["model"], stage_items(key, personas, stage["condition"]), 0, name):
            return summaries, False
    stab = cfg["stability"]
    for repeat in range(1, stab["extra_repeats"] + 1):
        if not go(stab["model"], stage_items(key, personas, stab["condition"], only_stability=True), repeat, f"stability_r{repeat}"):
            return summaries, False
    return summaries, True


# ---------- answers ----------


def answer_record(model, code, prompt, repeat=0, cache_dir=CACHE_DIR, gate_cache_dir=panel_run.CACHE_DIR):
    """The answer for one code from this stage's cache, or from the gate's when it is the same prompt."""
    full = panel_run.prompt_hash(prompt)
    suffix = f"_r{repeat}" if repeat else ""
    path = Path(cache_dir) / model / f"{code}_{full[:16]}{suffix}.json"
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        return record if record.get("prompt_sha256") == full else None
    if repeat == 0:
        return read_gate_record(Path(gate_cache_dir) / model, code, prompt)
    return None


def load_answer_arrays(model, condition, key, personas, template, cache_dir=CACHE_DIR, gate_cache_dir=panel_run.CACHE_DIR):
    """{split: {item: p aligned to sorted row_index}} or None when any answer is missing."""
    out = {}
    for split in ("test", "calibration"):
        sub = key.loc[(key.condition == condition) & (key.split == split)].sort_values("row_index")
        values = {t: [] for t in paths.TARGETS}
        for code in sub["code"]:
            record = answer_record(model, code, panel_run.render(template, personas[code]), 0, cache_dir, gate_cache_dir)
            if record is None:
                return None
            for t in paths.TARGETS:
                values[t].append(record["answer"][paths.ANSWER_COL[t]])
        out[split] = {t: np.array(v, dtype=float) for t, v in values.items()}
    return out


def load_stability(cfg, key, personas, template, cache_dir=CACHE_DIR, gate_cache_dir=panel_run.CACHE_DIR):
    """{item: array (respondents, 1 + extra repeats)} over respondents with every answer present."""
    stab = cfg["stability"]
    sub = key.loc[(key.stability == 1) & (key.condition == stab["condition"])].sort_values("row_index")
    rows = {t: [] for t in paths.TARGETS}
    missing = 0
    for code in sub["code"]:
        prompt = panel_run.render(template, personas[code])
        records = [answer_record(stab["model"], code, prompt, r, cache_dir, gate_cache_dir) for r in range(stab["extra_repeats"] + 1)]
        if any(r is None for r in records):
            missing += 1
            continue
        for t in paths.TARGETS:
            rows[t].append([r["answer"][paths.ANSWER_COL[t]] for r in records])
    if not rows[paths.TARGETS[0]]:
        return None, missing
    return {t: np.array(v, dtype=float) for t, v in rows.items()}, missing


def summarize_log(key, log_path=CALL_LOG):
    log_path = Path(log_path)
    rows = []
    if log_path.exists():
        with log_path.open(encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    split_of = dict(zip(key["code"], key["split"]))
    out = {}
    for row in rows:
        stage = "stability" if row.get("repeat") else row.get("condition")
        slot = out.setdefault(row["model"], {}).setdefault(stage, {"attempts": 0, "billed": 0, "statuses": {}, "by_split_ok": {}, "retried_attempts": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "cached_tokens": 0, "cost_usd": 0.0, "cost_assumed_usd": 0.0, "ts": []})
        slot["attempts"] += 1
        slot["statuses"][row["status"]] = slot["statuses"].get(row["status"], 0) + 1
        slot["retried_attempts"] += int((row.get("attempt") or 1) > 1)
        slot["cost_usd"] += row.get("cost_usd", 0.0)
        slot["ts"].append(row["ts"])
        if row.get("cost_assumed"):
            slot["cost_assumed_usd"] += row.get("cost_usd", 0.0)
        if row.get("http_status") == 200:
            slot["billed"] += 1
            for f in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens"):
                slot[f] += row.get(f) or 0
        if row["status"] == "ok":
            split = split_of.get(row.get("code"), "unknown")
            slot["by_split_ok"][split] = slot["by_split_ok"].get(split, 0) + 1
    total = 0.0
    for by_stage in out.values():
        for slot in by_stage.values():
            ts = slot.pop("ts")
            slot["wall_clock_s"] = round(max(ts) - min(ts), 1)
            total += slot["cost_usd"]
            slot["cost_usd"] = round(slot["cost_usd"], 6)
            slot["cost_assumed_usd"] = round(slot["cost_assumed_usd"], 6)
    return {"models": out, "stage_total_usd": round(total, 6)}


# ---------- commands ----------


def cmd_prepare(_args):
    print(json.dumps(prepare(), indent=2))


def cmd_freeze(_args):
    freeze()
    print(json.dumps(json.loads(FROZEN.read_text(encoding="utf-8")), indent=2))


def cmd_check(_args):
    cfg, template = load_config()
    key = load_key()
    check_frozen(key)
    require_committed()
    personas = load_personas()
    reused = {}
    for stage in cfg["run_order"]:
        sub = key.loc[(key.condition == stage["condition"]) & (key.gate_code == 1)]
        gate_dir = panel_run.CACHE_DIR / stage["model"]
        found = sum(read_gate_record(gate_dir, c, panel_run.render(template, personas[c])) is not None for c in sub["code"])
        reused[f"{stage['model']}|{stage['condition']}"] = {"gate_codes": int(len(sub)), "gate_answer_found_same_prompt": int(found)}
    print(json.dumps({"prompt_sha256": cfg["prompt_sha256"], "frozen": "ok", "committed": "ok", "gate_reuse": reused, "projected": projected_cost(cfg, key), "stage_spent_usd": round(panel_run.spent_from_log(CALL_LOG), 6)}, indent=2))


def cmd_run(_args):
    cfg, template = load_config()
    key = load_key()
    check_frozen(key)
    require_committed()
    personas = load_personas()
    print(json.dumps(projected_cost(cfg, key)), flush=True)
    _, complete = run_all(cfg, template, key, personas, panel_run.read_api_key(cfg["api_key_file"]))
    print(json.dumps({"complete": complete, "stage_spent_usd": round(panel_run.spent_from_log(CALL_LOG), 6)}), flush=True)
    if not complete:
        sys.exit(3)


def cmd_status(args):
    summary = summarize_log(load_key())
    print(json.dumps(summary, indent=2))
    if args.write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "main_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def cmd_score(_args):
    cfg, template = load_config()
    key = load_key()
    check_frozen(key)
    personas = load_personas()
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    b = prereg["B_calibration_study"]
    answers, incomplete = {}, []
    for stage in cfg["run_order"]:
        name = main_score.label(stage["model"], stage["condition"])
        got = load_answer_arrays(stage["model"], stage["condition"], key, personas, template)
        if got is None:
            incomplete.append(name)
        else:
            answers[name] = got
    if not answers:
        raise SystemExit("no complete model and condition to score")
    stability_answers, stability_missing = load_stability(cfg, key, personas, template)
    df, _ = data.load_sav()
    baseline_doc = json.loads((paths.RESULTS / "baselines.json").read_text(encoding="utf-8"))
    ctx = main_score.build_context(df, key, baseline_doc)
    plan = {"n": b["n"], "kinds": list(b["draw_kinds"]), "repeats": b["repeats"], "seed": b["seed"], "pi_draws": cfg["panel"]["pi_draws"], "pi_seed": cfg["panel"]["pi_seed"], "bootstrap": prereg["C_person_level_reps"]}
    result = main_score.score_main(ctx, answers, stability_answers, plan)
    result["incomplete"] = incomplete
    result["stability_respondents_missing"] = stability_missing
    result["frozen"] = json.loads(FROZEN.read_text(encoding="utf-8"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "main_score.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    text = main_score.to_markdown(result, ctx["items"])
    (RESULTS / "main_score.md").write_text(text, encoding="utf-8")
    print(text)
    print(json.dumps({"incomplete": incomplete, "stability_respondents_missing": stability_missing}))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in (("prepare", cmd_prepare), ("freeze", cmd_freeze), ("check", cmd_check), ("run", cmd_run), ("score", cmd_score)):
        sub.add_parser(name).set_defaults(func=fn)
    s = sub.add_parser("status")
    s.add_argument("--write", action="store_true")
    s.set_defaults(func=cmd_status)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
