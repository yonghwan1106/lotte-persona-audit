"""Leak guard. Persona text may never reveal a target.

Three layers:
  1. Static block: target family, survey design ids, household-file items, label and value-label regex.
  2. Train-split screen: univariate AUC above the threshold gets blocked unless a plain demographic.
  3. Text scan: every rendered persona is scanned with the same regexes before it can be written.
"""
import json
import re

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from . import data, paths


class LeakError(Exception):
    """A persona or an allowlist item would reveal or bypass the target guard."""


def load_patterns():
    return json.loads((paths.CONFIG / "leak_patterns.json").read_text(encoding="utf-8"))


def compile_block(patterns):
    return {k: re.compile(v) for k, v in patterns["label_block"].items()}


def static_block_reason(var, label, value_label_texts, patterns, compiled):
    """Return a reason string if the variable is statically blocked, else None."""
    if var in patterns["plain_demographics"]:
        return None
    if any(var == p or var.startswith(p + "_") for p in patterns["target_family_prefix"]):
        return "target family"
    if var in patterns["design_block"]:
        return "survey design or id"
    if var.startswith(patterns["household_prefix_block"]):
        return "household file item"
    for cat, rx in compiled.items():
        if rx.search(label or ""):
            return f"label regex: {cat}"
    for text in value_label_texts:
        for cat, rx in compiled.items():
            if rx.search(text or ""):
                return f"value label regex: {cat}"
    return None


def univariate_auc(x, y, w):
    """Larger of ordered-code AUC and category-encoded AUC, both folded above 0.5.

    Categorical codes have no natural order, so the ordered AUC alone would miss a nominal leak.
    Missing is its own category.
    """
    s = pd.Series(np.asarray(x, dtype=float))
    filled = s.fillna(s.min() - 1 if s.notna().any() else -1).to_numpy()
    a = roc_auc_score(y, filled, sample_weight=w)
    best = max(a, 1 - a)
    if pd.Series(filled).nunique() <= 30:
        frame = pd.DataFrame({"x": filled, "y": y, "w": w})
        frame["yw"] = frame.y * frame.w
        g = frame.groupby("x")[["yw", "w"]].sum()
        rate = g.yw / g.w
        enc = frame.x.map(rate).to_numpy()
        e = roc_auc_score(y, enc, sample_weight=w)
        best = max(best, e, 1 - e)
    return float(best)


def screen(train_df, meta, targets, weight=paths.WEIGHT):
    """Screen every numeric variable on the frame given, which must be the train split only."""
    patterns = load_patterns()
    compiled = compile_block(patterns)
    threshold = patterns["screen_auc_threshold"]
    w = train_df[weight].to_numpy()
    rows = []
    for var in train_df.select_dtypes("number").columns:
        s = train_df[var]
        if s.nunique(dropna=True) < 2:
            continue
        label = data.var_label(meta, var)
        reason = static_block_reason(var, label, list(data.value_labels(meta, var).values()), patterns, compiled)
        row = {"var": var, "label": label[:80], "static_block": reason or "", "notna": round(float(s.notna().mean()), 3)}
        peak = 0.0
        for t in paths.TARGETS:
            a = univariate_auc(s.to_numpy(), targets[t].to_numpy(), w)
            row[f"auc_{t}"] = round(a, 3)
            peak = max(peak, a)
        row["peak_auc"] = round(peak, 3)
        row["over_threshold"] = bool(peak > threshold)
        row["plain_demographic"] = var in patterns["plain_demographics"]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("peak_auc", ascending=False).reset_index(drop=True)


def check_candidate(var, meta, screen_df=None):
    """Raise LeakError if a variable may not go into persona text."""
    patterns = load_patterns()
    compiled = compile_block(patterns)
    reason = static_block_reason(var, data.var_label(meta, var), list(data.value_labels(meta, var).values()), patterns, compiled)
    if reason:
        raise LeakError(f"{var}: {reason}")
    if screen_df is not None and var not in patterns["plain_demographics"]:
        hit = screen_df.loc[screen_df["var"] == var]
        if len(hit) and bool(hit.iloc[0]["over_threshold"]):
            raise LeakError(f"{var}: train univariate AUC {hit.iloc[0]['peak_auc']} above threshold")


def build_allowlist(candidates, meta, screen_df):
    """Split candidates into kept and rejected, with the reason for each rejection."""
    kept, rejected = [], []
    for item in candidates:
        var = item["var"]
        if var not in meta.column_names:
            rejected.append({"var": var, "reason": "not in file"})
            continue
        try:
            check_candidate(var, meta, screen_df)
        except LeakError as e:
            rejected.append({"var": var, "label": data.var_label(meta, var)[:80], "reason": str(e)})
            continue
        kept.append(item)
    return kept, rejected


def scan_text(text, forbidden_strings=()):
    """Raise LeakError if a rendered persona contains a blocked term or a forbidden literal such as an id."""
    compiled = compile_block(load_patterns())
    for cat, rx in compiled.items():
        m = rx.search(text)
        if m:
            raise LeakError(f"persona text hit {cat}: {m.group(0)!r}")
    for s in forbidden_strings:
        if s and str(s) in text:
            raise LeakError("persona text contains a row identifier")
    return text
