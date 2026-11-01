"""ingest_real: real answers on anchor items and a concept question, joined to panel probabilities for the same respondents, through the duel.

The duel is a health check. Every run is recorded in the ledger, and panel values stay out of reports by default: config/panel_value_policy.json, a post hoc
decision made after the frozen pass. A single keep never puts a panel value in a report. Only a project-agreed run of consecutive keeps under unit-intact folds
can allow it, and no code here puts one in. The frozen label stays in the records with its caveat.

Row level files stay in an ignored folder. What leaves this module is aggregates: losses, intervals, the rule's outcome, and the reason, into the report and the ledger.
Nothing here can tell who is named as approver. A stand-in file says so in its label, and a stand-in is not a concept survey.
"""
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .. import duel, duel_units, paths

ANCHORS = ("ever", "weekly", "carb")
AGE_BANDS = (4, 5, 6, 7, 8, 9)
SEXES = (1, 2)
REQUIRED = ("respondent_id", "age_band", "sex", "weight")
UNIT = "unit_id"
CONCEPT = re.compile(r"^concept_([A-Za-z0-9_]+)$")
CONDITION = re.compile(r"^C[0-9]+$")
MIN_N = 50
MARK_START = "<!-- real_results:start -->"
MARK_END = "<!-- real_results:end -->"
IGNORED = ("runs", "data")
STANDIN_LABEL = "\uc2e4\uce21 \ub300\uc6a9 KREI"
DEFAULT_SEED = (42, 5, 0)
DUEL_VALIDITY = paths.RESULTS / "stage4" / "duel_validity.json"
SEED_CHECK = paths.RESULTS / "stage4" / "duel_seed_sensitivity.json"
POST_HOC = paths.RESULTS / "stage4" / "duel_post_hoc.json"
POLICY = paths.CONFIG / "panel_value_policy.json"
UNIT_INTACT, CELL_STRATIFIED = "unit_intact", "cell_stratified"
LLM_SLOTS = ("terra_", "luna_")


class IngestRefused(ValueError):
    """The files cannot be read as stated. Nothing was written."""


def check_location(path):
    """A row level file inside the repo must sit in a folder git ignores."""
    path = Path(path).resolve()
    if not path.exists():
        raise IngestRefused(f"file not found: {path.name}")
    try:
        parts = path.relative_to(paths.ROOT).parts
    except ValueError:
        return path
    if parts[0] not in IGNORED:
        raise IngestRefused(f"row level file must not sit in a tracked folder: {parts[0]}")
    return path


def read_real(path):
    df = pd.read_csv(check_location(path), dtype={"respondent_id": str})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise IngestRefused(f"real file lacks columns {missing}")
    if df["respondent_id"].duplicated().any():
        raise IngestRefused("a respondent appears twice in the real file")
    if df[list(REQUIRED)].isna().any().any():
        raise IngestRefused("missing values in the required columns")
    if len(df) < MIN_N:
        raise IngestRefused(f"at least {MIN_N} respondents are needed for 5 folds, got {len(df)}")
    if not df["age_band"].astype(int).isin(AGE_BANDS).all() or not df["sex"].astype(int).isin(SEXES).all():
        raise IngestRefused("age band or sex outside the known codes")
    if not (df["weight"].astype(float) > 0).all():
        raise IngestRefused("a weight is not positive")
    if UNIT in df.columns:
        if df[UNIT].isna().any():
            raise IngestRefused("a respondent has no survey unit")
        if df[UNIT].nunique() < duel.FOLDS:
            raise IngestRefused(f"at least {duel.FOLDS} survey units are needed for unit-intact folds, got {df[UNIT].nunique()}")
    anchors = [a for a in ANCHORS if a in df.columns]
    concepts = [m.group(1) for c in df.columns if (m := CONCEPT.match(c))]
    if not anchors and not concepts:
        raise IngestRefused("no anchor item and no concept question in the real file")
    for a in anchors:
        if not df[a].isin([0, 1]).all():
            raise IngestRefused(f"anchor {a} must be 0 or 1 for every respondent")
    for c in concepts:
        if not df[f"concept_{c}"].isin([1, 2, 3, 4, 5]).all():
            raise IngestRefused(f"concept {c} must be 1 to 5 for every respondent")
    return df, anchors, concepts


def read_panel(path, real, anchors, concepts):
    """Panel probabilities in the real file's row order. A respondent without one stops the run; nothing is dropped quietly."""
    p = pd.read_csv(check_location(path), dtype={"respondent_id": str})
    if "respondent_id" not in p.columns or p["respondent_id"].duplicated().any():
        raise IngestRefused("panel file needs one row per respondent_id")
    wanted = [f"p_{a}" for a in anchors] + [f"p_concept_{c}" for c in concepts]
    missing = [c for c in wanted if c not in p.columns]
    if missing:
        raise IngestRefused(f"panel file lacks columns {missing}")
    joined = real[["respondent_id"]].merge(p, on="respondent_id", how="left")
    if joined[wanted].isna().any().any():
        raise IngestRefused(f"{int(joined[wanted].isna().any(axis=1).sum())} real respondents have no panel value")
    for c in wanted:
        if not joined[c].between(0, 1).all():
            raise IngestRefused(f"{c} is outside 0 to 1")
    return joined, int(len(p) - len(joined))


def cell_table():
    pairs = [(a, s) for a in AGE_BANDS for s in SEXES]
    index = {pair: i for i, pair in enumerate(pairs)}
    cell_age = np.array([AGE_BANDS.index(a) for a, _ in pairs], dtype=float)
    cell_sex = np.array([SEXES.index(s) for _, s in pairs], dtype=float)
    return index, cell_age, cell_sex


def load_policy(path=POLICY):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def panel_slot(model, condition):
    return f"{model.rsplit('-', 1)[-1]}_{condition}"


def slot_name(slot):
    short, condition = slot.split("_", 1)
    return f"{short.capitalize()} {condition}"


def demo_condition():
    return json.loads((paths.CONFIG / "agent_run.json").read_text(encoding="utf-8"))["panel"]["condition"]


def read_optional(path):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _rate(value):
    return "-" if value is None else f"{value:g}"


def grade_rate_lines(t, doc, posthoc, slot):
    """Keep rate and cell error mismatch of the panel named as input, from the frozen file or the post hoc file. Never a fixed panel."""
    rows = {name: b["pooled"]["panel_excluded"] for name, b in doc["row"].items()}
    if posthoc:
        rows.update({name: b["pooled"]["panel_excluded"] for name, b in posthoc.get("row", {}).items() if name not in rows})
    others = ", ".join(f"{slot_name(n)} {_pct(r['keep_rate'])}" for n, r in sorted(rows.items()) if n.startswith(LLM_SLOTS) and n != slot)
    if slot not in rows:
        return [t["grade_rate_unknown"].format(panel=slot_name(slot), others=others or "-")]
    r = rows[slot]
    lines = [t["grade_rate"].format(panel=slot_name(slot), rate=_pct(r["keep_rate"]), others=others or "-")]
    lines.append(t["grade_limit"].format(panel=slot_name(slot), false_keep=_pct(r["false_keep_rate"]), missed=_pct(r["missed_keep_rate"])))
    return lines


def post_hoc_lines(t, posthoc, slot):
    """Fold seed instability and unit-intact folds. Absent when the post hoc file is absent; the report then says nothing it has no source for."""
    if not posthoc:
        return []
    lines = []
    same = posthoc.get("same_sample")
    if same:
        name = slot if slot in same["draw0"] else "terra_C2"
        d0, flip = same["draw0"][name], same["all_draws"][name]
        lines.append(t["grade_unstable"].format(panel=slot_name(name), seeds=d0["fold_seeds"], draw0=_pct(d0["pooled_keep_share"]), per_draw=flip["fold_seeds_per_draw"], draws=flip["draws"], changes=_pct(flip["share_draws_decision_changes"])))
    unit = posthoc.get("unit_intact", {}).get("row")
    if unit:
        k = unit["keep_rate"]
        lines.append(t["grade_unit"].format(seeds=len(unit["fold_seeds"]), terra2=_rate(k["terra_C2"]["mean"]), terra1=_rate(k["terra_C1"]["mean"]), surrogate=_rate(k["surrogate_terra_slot"]["mean"]), floor=_rate(k["floor_no_llm"]["mean"]), positive=_rate(k["control_s1.0"]["mean"])))
    floor = posthoc.get("row", {}).get("floor_no_llm")
    if floor:
        r = floor["pooled"]["panel_excluded"]
        lines.append(t["grade_floor"].format(keep=_pct(r["keep_rate"]), beats=_pct(r["beats_rate"])))
    return lines


def grade(text, slot, validity_path=DUEL_VALIDITY, seed_path=SEED_CHECK, post_hoc_path=POST_HOC, policy=None):
    """How far the rule may be trusted, from the frozen study and the post hoc checks. It never changes the rule's outcome, and the frozen label stays a record."""
    t = text["real"]
    policy = policy or load_policy()
    doc = read_optional(validity_path)
    if doc is None:
        return {"label": "unknown", "lines": [t["not_grade"]], "acceptance_passed": None, "label_caveat": None}
    a = doc["acceptance"]
    surrogate = max(a["surrogate_keep_rates"].values())
    lines = [(t["grade_passed"] if a["passed"] else t["grade_failed"]).format(surrogate=surrogate, positive=a["positive_keep_rate"], label=a["label"])]
    failed = runs = 0
    seeds = read_optional(seed_path)
    if seeds:
        seeds = seeds["runs"]
        runs = len(seeds)
        failed = sum(not v["acceptance_passed"] for v in seeds.values())
        if failed:
            lines.append(t["grade_fragile"].format(runs=runs, failed=failed))
    posthoc = read_optional(post_hoc_path)
    lines += grade_rate_lines(t, doc, posthoc, slot)
    lines += post_hoc_lines(t, posthoc, slot)
    return {"label": a["label"], "lines": lines, "acceptance_passed": a["passed"], "seed_runs": runs, "seed_runs_failed": failed, "label_caveat": policy["frozen_label_caveat"], "post_hoc": posthoc}


def consecutive_keeps(ledger_path, model, condition):
    """Keeps in a row, newest first, on this panel among the runs that count: unit-intact folds, no stand-in. A counted drop ends the run."""
    path = Path(ledger_path)
    if not path.exists():
        return 0
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    count = 0
    for row in reversed(rows):
        block = (row.get("real_results") or {}) if row.get("kind") == "real_results" else {}
        check = block.get("health_check")
        if not check or not check["counts_toward_run"] or block.get("panel") != {"model": model, "condition": condition}:
            continue
        if check["outcome"] != "keep":
            break
        count += 1
    return count


def may_enter(policy, count):
    """True only when the project has agreed a run length and it has been reached. The default is no."""
    required = policy["consecutive_keeps_required"]
    return required is not None and count >= required


def _pct(share):
    return "-" if share is None else f"{100 * share:.1f}%"


def _outcome(block):
    return "keep" if block["keep"] else "drop"


def run_duel(real, joined, anchors, concepts, seed):
    index, cell_age, cell_sex = cell_table()
    cells = np.array([index[(int(a), int(s))] for a, s in zip(real["age_band"], real["sex"])])
    w = real["weight"].to_numpy(dtype=float)
    fold = None
    if UNIT in real.columns:
        fold = duel_units.folds_by_unit(real[UNIT].astype(str).to_numpy(), duel.FOLDS, np.random.default_rng(list(seed)))

    def one(answers):
        if fold is None:
            return duel.duel(answers, cells, w, cell_age, cell_sex, list(seed))
        return duel_units.duel_on_folds(answers, cells, w, cell_age, cell_sex, fold)

    out = {"anchors": None, "concepts": {}, "fold_kind": CELL_STRATIFIED if fold is None else UNIT_INTACT}
    if anchors:
        out["anchors"] = one({a: (real[a].to_numpy(dtype=float), joined[f"p_{a}"].to_numpy(dtype=float)) for a in anchors})
    for c in concepts:
        y = (real[f"concept_{c}"].to_numpy() >= 4).astype(float)
        out["concepts"][c] = one({f"concept_{c}": (y, joined[f"p_concept_{c}"].to_numpy(dtype=float))})["pooled"]
    return out


def summarise(result, real, anchors, concepts, source_label, approver, approver_note, text, grade_doc, panel_model, panel_condition, policy, prior_keeps=0):
    t = text["real"]
    n = len(real)
    lines = []
    is_standin = source_label == STANDIN_LABEL
    slot = panel_slot(panel_model, panel_condition)
    panel_text = f"{panel_model} {panel_condition}"
    fold_kind = result["fold_kind"]
    outcome = None
    if result["anchors"]:
        p = result["anchors"]["pooled"]
        outcome = _outcome(p)
        lines += [t["headline"].format(label=source_label, status=t["status_excluded"], outcome=outcome, mean=f"{p['mean_improvement']:+.4f}", lo=f"{p['interval'][0]:+.4f}", hi=f"{p['interval'][1]:+.4f}", fold=t[f"fold_{fold_kind}"], items=len(anchors), n=n, panel=panel_text), t["reason_keep"] if p["keep"] else t["reason_drop"]]
    else:
        lines.append(t["status_only"].format(label=source_label, status=t["status_excluded"], panel=panel_text, fold=t[f"fold_{fold_kind}"], n=n))
    if is_standin:
        lines.append(t["standin_warning"])
        demo = demo_condition()
        other = panel_slot(panel_model, demo)
        known = ((grade_doc.get("post_hoc") or {}).get("frozen_draw0_keep") or {}).get(other)
        if panel_condition != demo and known is not None:
            lines.append(t["standin_condition"].format(panel=slot_name(slot), demo=demo, other="keep" if known else "drop"))
    if concepts:
        for c, block in result["concepts"].items():
            lines.append(t["concept_line"].format(card=c, outcome=_outcome(block), mean=f"{block['mean_improvement']:+.4f}", lo=f"{block['interval'][0]:+.4f}", hi=f"{block['interval'][1]:+.4f}"))
    else:
        lines.append(t["concept_not_run"])
    counts = fold_kind == UNIT_INTACT and not is_standin and outcome is not None
    keeps = prior_keeps + 1 if counts and outcome == "keep" else (0 if counts else prior_keeps)
    required = policy["consecutive_keeps_required"]
    allowed = may_enter(policy, keeps)
    lines.append(t["policy_run"].format(count=keeps, required=t["required_not_agreed"] if required is None else required))
    if allowed:
        lines.append(t["policy_run_met"].format(required=required))
    lines.append(t["policy_post_hoc"].format(label=policy["frozen_label"]))
    lines += grade_doc["lines"]
    lines.append(t["approver"].format(approver=approver))
    doc = {
        "source_label": source_label,
        "is_real_concept_survey": bool(concepts) and not is_standin,
        "panel": {"model": panel_model, "condition": panel_condition},
        "n_respondents": n,
        "anchors_used": anchors,
        "concepts_used": concepts,
        "folds": duel.FOLDS,
        "fold_kind": fold_kind,
        "metric": "out of fold weighted log loss, R1 minus calibrated panel, positive favours the panel",
        "duel_outcome": outcome,
        "health_check": {"recorded": True, "outcome": outcome, "fold_kind": fold_kind, "counts_toward_run": counts, "consecutive_keeps": keeps, "consecutive_keeps_required": required},
        "panel_values_in_report": False,
        "panel_values_may_enter": allowed,
        "report_status": t["status_excluded"],
        "policy": {"file": "config/panel_value_policy.json", "post_hoc": policy["post_hoc"], "decided_on": policy["decided_on"]},
        "anchors": None if not result["anchors"] else {"pooled": duel.rounded(result["anchors"]["pooled"]), "per_item": {k: duel.rounded(v) for k, v in result["anchors"]["per_item"].items()}},
        "concepts": {k: duel.rounded(v) for k, v in result["concepts"].items()},
        "concept_duel": "ran" if concepts else "not_run_no_real_concept_answers",
        "duel_grade": {"label": grade_doc.get("label"), "acceptance_passed": grade_doc.get("acceptance_passed"), "label_caveat": grade_doc.get("label_caveat")},
        "seed_runs": grade_doc.get("seed_runs"),
        "seed_runs_failed": grade_doc.get("seed_runs_failed"),
        "approver": approver,
        "approver_note": approver_note,
        "lines": lines,
    }
    return doc


def update_report(report_path, lines):
    """Replace the block between the two markers of a report. A report with no markers is left alone and the call says so."""
    path = Path(report_path)
    text = path.read_text(encoding="utf-8")
    if MARK_START not in text or MARK_END not in text:
        raise IngestRefused(f"no real results block in {path.name}")
    head, rest = text.split(MARK_START, 1)
    _, tail = rest.split(MARK_END, 1)
    body = "\n".join(["", *[f"- {x}" for x in lines], ""])
    path.write_text(head + MARK_START + "\n" + body + "\n" + MARK_END + tail, encoding="utf-8")


def append_ledger(ledger_path, run_id, manifest_sha, doc):
    entry = {"ts": round(time.time(), 3), "kind": "real_results", "run_id": run_id, "manifest_sha256": manifest_sha, "approver": doc["approver"], "real_results": {k: v for k, v in doc.items() if k != "lines"}, "human_decision": None}
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return entry


def ingest(real_csv, panel_csv, run_dir, ledger_path, source_label, approver, text, panel_model, panel_condition, seed=DEFAULT_SEED, validity_path=DUEL_VALIDITY, seed_path=SEED_CHECK, post_hoc_path=POST_HOC, policy_path=POLICY):
    """The whole path. Reads the two row level files, runs the duel, writes real_results.json, the report block and the ledger line. The panel is named by the caller and recorded."""
    if not approver or not str(approver).strip():
        raise IngestRefused("a person or a stated stand-in must be named as approver")
    if not source_label or not str(source_label).strip():
        raise IngestRefused("the source of the answers must be named")
    if not panel_model or not str(panel_model).strip():
        raise IngestRefused("the panel model must be named")
    if not panel_condition or not CONDITION.match(str(panel_condition)):
        raise IngestRefused("the panel condition must be named, such as C1")
    real, anchors, concepts = read_real(real_csv)
    joined, extra = read_panel(panel_csv, real, anchors, concepts)
    policy = load_policy(policy_path)
    result = run_duel(real, joined, anchors, concepts, seed)
    grade_doc = grade(text, panel_slot(panel_model, panel_condition), validity_path, seed_path, post_hoc_path, policy)
    doc = summarise(result, real, anchors, concepts, source_label, approver, "code cannot check who this is", text, grade_doc, panel_model, panel_condition, policy, consecutive_keeps(ledger_path, panel_model, panel_condition))
    doc["panel_rows_not_used"] = extra
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    update_report(run_dir / "report.md", doc["lines"])
    (run_dir / "real_results.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    append_ledger(ledger_path, manifest.get("run_id"), manifest["manifest_sha256"], doc)
    return doc
