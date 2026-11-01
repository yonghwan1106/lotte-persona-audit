"""ingest_real: real answers on anchor items and a concept question, joined to panel probabilities for the same respondents, through the duel.

Row level files stay in an ignored folder. What leaves this module is aggregates: losses, intervals, keep or drop, and the reason, into the report and the ledger.
Nothing here can tell who is named as approver. A stand-in file says so in its label, and a stand-in is not a concept survey.
"""
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .. import duel, paths

ANCHORS = ("ever", "weekly", "carb")
AGE_BANDS = (4, 5, 6, 7, 8, 9)
SEXES = (1, 2)
REQUIRED = ("respondent_id", "age_band", "sex", "weight")
CONCEPT = re.compile(r"^concept_([A-Za-z0-9_]+)$")
MIN_N = 50
MARK_START = "<!-- real_results:start -->"
MARK_END = "<!-- real_results:end -->"
IGNORED = ("runs", "data")
STANDIN_LABEL = "\uc2e4\uce21 \ub300\uc6a9 KREI"
DEFAULT_SEED = (42, 5, 0)
DUEL_VALIDITY = paths.RESULTS / "stage4" / "duel_validity.json"
SEED_CHECK = paths.RESULTS / "stage4" / "duel_seed_sensitivity.json"


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


def grade(text, validity_path=DUEL_VALIDITY, seed_path=SEED_CHECK):
    """How far the rule itself may be trusted, from the validity study. It never changes keep or drop."""
    t = text["real"]
    validity_path, seed_path = Path(validity_path), Path(seed_path)
    if not validity_path.exists():
        return {"label": "unknown", "lines": [t["not_grade"]], "acceptance_passed": None}
    doc = json.loads(validity_path.read_text(encoding="utf-8"))
    a = doc["acceptance"]
    surrogate = max(a["surrogate_keep_rates"].values())
    lines = [(t["grade_passed"] if a["passed"] else t["grade_failed"]).format(surrogate=surrogate, positive=a["positive_keep_rate"])]
    failed = runs = 0
    if seed_path.exists():
        seeds = json.loads(seed_path.read_text(encoding="utf-8"))["runs"]
        runs = len(seeds)
        failed = sum(not v["acceptance_passed"] for v in seeds.values())
        if failed:
            lines.append(t["grade_fragile"].format(runs=runs, failed=failed))
    terra = doc["row"]["terra_C2"]["pooled"]["panel_excluded"]
    luna = doc["row"]["luna_C1"]["pooled"]["panel_excluded"]
    lines.append(t["grade_rate"].format(terra=_pct(terra["keep_rate"]), luna=_pct(luna["keep_rate"])))
    lines.append(t["grade_limit"].format(false_keep=_pct(terra["false_keep_rate"]), missed=_pct(terra["missed_keep_rate"])))
    return {"label": a["label"], "lines": lines, "acceptance_passed": a["passed"], "seed_runs": runs, "seed_runs_failed": failed}


def _pct(share):
    return "-" if share is None else f"{100 * share:.1f}%"


def _decision(block, text):
    return text["real"]["keep"] if block["keep"] else text["real"]["drop"]


def run_duel(real, joined, anchors, concepts, seed):
    index, cell_age, cell_sex = cell_table()
    cells = np.array([index[(int(a), int(s))] for a, s in zip(real["age_band"], real["sex"])])
    w = real["weight"].to_numpy(dtype=float)
    out = {"anchors": None, "concepts": {}}
    if anchors:
        answers = {a: (real[a].to_numpy(dtype=float), joined[f"p_{a}"].to_numpy(dtype=float)) for a in anchors}
        out["anchors"] = duel.duel(answers, cells, w, cell_age, cell_sex, list(seed))
    for c in concepts:
        y = (real[f"concept_{c}"].to_numpy() >= 4).astype(float)
        got = duel.duel({f"concept_{c}": (y, joined[f"p_concept_{c}"].to_numpy(dtype=float))}, cells, w, cell_age, cell_sex, list(seed))
        out["concepts"][c] = got["pooled"]
    return out


def summarise(result, real, anchors, concepts, source_label, approver, approver_note, text, grade_doc):
    t = text["real"]
    n = len(real)
    lines = []
    is_standin = source_label == STANDIN_LABEL
    headline = None
    if result["anchors"]:
        p = result["anchors"]["pooled"]
        headline = t["headline"].format(label=source_label, decision=_decision(p, text), mean=f"{p['mean_improvement']:+.4f}", lo=f"{p['interval'][0]:+.4f}", hi=f"{p['interval'][1]:+.4f}", items=len(anchors), n=n)
        lines += [headline, t["reason_keep"] if p["keep"] else t["reason_drop"]]
    if is_standin:
        lines.append(t["standin_warning"])
    if concepts:
        for c, block in result["concepts"].items():
            lines.append(t["concept_line"].format(card=c, decision=_decision(block, text), mean=f"{block['mean_improvement']:+.4f}", lo=f"{block['interval'][0]:+.4f}", hi=f"{block['interval'][1]:+.4f}"))
    else:
        lines.append(t["concept_not_run"])
    lines += grade_doc["lines"]
    lines.append(t["approver"].format(approver=approver))
    doc = {
        "source_label": source_label,
        "is_real_concept_survey": bool(concepts) and not is_standin,
        "n_respondents": n,
        "anchors_used": anchors,
        "concepts_used": concepts,
        "folds": duel.FOLDS,
        "metric": "out of fold weighted log loss, R1 minus calibrated panel, positive favours the panel",
        "decision": None if not result["anchors"] else ("keep" if result["anchors"]["pooled"]["keep"] else "drop"),
        "anchors": None if not result["anchors"] else {"pooled": duel.rounded(result["anchors"]["pooled"]), "per_item": {k: duel.rounded(v) for k, v in result["anchors"]["per_item"].items()}},
        "concepts": {k: duel.rounded(v) for k, v in result["concepts"].items()},
        "concept_duel": "ran" if concepts else "not_run_no_real_concept_answers",
        "duel_grade": {k: grade_doc[k] for k in ("label", "acceptance_passed") if k in grade_doc},
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


def ingest(real_csv, panel_csv, run_dir, ledger_path, source_label, approver, text, seed=DEFAULT_SEED, validity_path=DUEL_VALIDITY, seed_path=SEED_CHECK):
    """The whole path. Reads the two row level files, runs the duel, writes real_results.json, the report block and the ledger line."""
    if not approver or not str(approver).strip():
        raise IngestRefused("a person or a stated stand-in must be named as approver")
    if not source_label or not str(source_label).strip():
        raise IngestRefused("the source of the answers must be named")
    real, anchors, concepts = read_real(real_csv)
    joined, extra = read_panel(panel_csv, real, anchors, concepts)
    result = run_duel(real, joined, anchors, concepts, seed)
    doc = summarise(result, real, anchors, concepts, source_label, approver, "code cannot check who this is", text, grade(text, validity_path, seed_path))
    doc["panel_rows_not_used"] = extra
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    update_report(run_dir / "report.md", doc["lines"])
    (run_dir / "real_results.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    append_ledger(ledger_path, manifest.get("run_id"), manifest["manifest_sha256"], doc)
    return doc
