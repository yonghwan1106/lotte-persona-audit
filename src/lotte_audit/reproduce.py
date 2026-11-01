"""Reproduce the scout and comparator numbers on the WHOLE file with their own recipes.

These runs ignore the fixed splits on purpose. They exist only to check the numbers in compare.md and
scout_task1.md. Nothing here feeds the gate. Logic follows t1_check.py and t1_check2.py line by line.
"""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from . import data, paths
from .hunt import COMPARATOR_LABEL_TERMS


def weighted_shares(df, var, w="psfwt"):
    s = df[[var, w]].dropna(subset=[var])
    total = s[w].sum()
    return {str(int(k)): round(100 * float(v) / total, 1) for k, v in s.groupby(var)[w].sum().items()}, int(len(s))


def t1_check(df, meta):
    """t1_check.py: 70/30 row split with rng 7, floor and tabular model."""
    labels = meta.column_names_to_labels
    d = df.copy()
    d["ever"] = (d["A19_1"] != 9).astype(float)
    d["weekly"] = (d["A19_1"] == 1).astype(float)
    d["fav_csd"] = d["A15_1"].isin([7, 8]).astype(float)
    rng = np.random.default_rng(7)
    idx = rng.permutation(len(d))
    cut = int(len(d) * 0.7)
    num = d.select_dtypes("number")
    drop = [k for k in num.columns if k.startswith("A15") or k.startswith("A19") or k.startswith("F13") or k in ("ever", "weekly", "fav_csd", "psfwt")]
    for k in num.columns:
        lab = labels.get(k) or ""
        if any(t in lab for t in COMPARATOR_LABEL_TERMS):
            drop.append(k)
    cand = [k for k in num.columns if k not in set(drop)]
    good = [k for k in cand if d[k].notna().mean() > 0.95 and d[k].nunique() > 1 and d[k].nunique() <= 12]
    xd = pd.get_dummies(d[["SQ2_range", "SQ1"]].astype(int).astype(str))
    xa = pd.get_dummies(d[good].fillna(-1).astype(int).astype(str)).astype(float)
    xall = pd.concat([xd.astype(float), xa], axis=1)
    xall = xall.loc[:, xall.mean() > 0.01]
    tri, tei = idx[:cut], idx[cut:]
    res = {"n_candidate_features": len(good)}
    w = d["psfwt"].to_numpy()
    for name, x in [("floor_demog", xd.astype(float)), ("ceiling_all_items", xall)]:
        res[name] = {}
        for c, key in [("ever", "ever"), ("weekly", "weekly"), ("fav_csd", "carb")]:
            m = LogisticRegression(max_iter=400, C=0.05)
            y = d[c].to_numpy()
            m.fit(x.to_numpy()[tri], y[tri], sample_weight=w[tri])
            res[name][key] = round(float(roc_auc_score(y[tei], m.predict_proba(x.to_numpy()[tei])[:, 1], sample_weight=w[tei])), 3)
    return res


def t1_check2(df, meta):
    """t1_check2.py: real-sample ladder with rng 42 on whole-file row splits, then weekly tabular AUC."""
    labels = meta.column_names_to_labels
    w = df["psfwt"].to_numpy()
    items = {
        "ever": (df["A19_1"] != 9).astype(float).to_numpy(),
        "weekly": (df["A19_1"] == 1).astype(float).to_numpy(),
        "carb": df["A15_1"].isin([7, 8]).astype(float).to_numpy(),
    }
    cell = (df["SQ2_range"].astype(int) * 10 + df["SQ1"].astype(int)).to_numpy()
    ucell = np.unique(cell)
    rng = np.random.default_rng(42)

    def cm(y, ww, c):
        out = {}
        for u in ucell:
            m = c == u
            if m.sum() > 0:
                out[u] = np.average(y[m], weights=ww[m])
        return out

    ladder = {}
    for n in [100, 250, 500, 1000]:
        acc = {"raw": [], "const": [], "shrunk": []}
        for _ in range(100):
            idx = rng.permutation(len(df))
            tr, te = idx[:n], idx[n:]
            for y in items.values():
                a = cm(y[te], w[te], cell[te])
                b = cm(y[tr], w[tr], cell[tr])
                g = np.average(y[tr], weights=w[tr])
                cnt = {u: (cell[tr] == u).sum() for u in ucell}
                for u in a:
                    if u in b:
                        acc["raw"].append(abs(a[u] - b[u]))
                        acc["shrunk"].append(abs(a[u] - (cnt[u] * b[u] + 30 * g) / (cnt[u] + 30)))
                    acc["const"].append(abs(a[u] - g))
        ladder[str(n)] = {k: round(100 * float(np.mean(v)), 2) for k, v in acc.items()}
    full_constant = {}
    for name, y in items.items():
        a = cm(y, w, cell)
        g = np.average(y, weights=w)
        full_constant[name] = round(100 * float(np.mean([abs(v - g) for v in a.values()])), 2)
    num = df.select_dtypes("number")
    drop = set(k for k in num.columns if k.startswith("A15") or k.startswith("A19") or k.startswith("F13") or k == "psfwt")
    for k in num.columns:
        lab = labels.get(k) or ""
        if any(t in lab for t in COMPARATOR_LABEL_TERMS):
            drop.add(k)
    good = [k for k in num.columns if k not in drop and df[k].notna().mean() > 0.95 and 1 < df[k].nunique() <= 12]
    xa = pd.get_dummies(df[good].fillna(-1).astype(int).astype(str)).astype(float)
    xa = xa.loc[:, xa.mean() > 0.01]
    idx = rng.permutation(len(df))
    cut = int(0.7 * len(df))
    tri, tei = idx[:cut], idx[cut:]
    y = items["weekly"]
    m = LogisticRegression(max_iter=300, C=0.05).fit(xa.to_numpy()[tri], y[tri], sample_weight=w[tri])
    weekly_auc = round(float(roc_auc_score(y[tei], m.predict_proba(xa.to_numpy()[tei])[:, 1], sample_weight=w[tei])), 3)
    return {
        "ladder": ladder,
        "full_file_constant": full_constant,
        "full_file_constant_average": round(float(np.mean(list(full_constant.values()))), 2),
        "weekly_tabular_auc": weekly_auc,
    }


def descriptive(df, meta):
    t = data.derive_targets(df)
    w = df["psfwt"].to_numpy()
    avg = lambda c, m=None: round(100 * float(np.average(t[c][m] if m is not None else t[c], weights=w[m] if m is not None else w)), 2)
    out = {
        "weighted_ever": avg("ever"),
        "weighted_weekly": avg("weekly"),
        "ever_male": avg("ever", (df.SQ1 == 1).to_numpy()),
        "ever_female": avg("ever", (df.SQ1 == 2).to_numpy()),
        "ever_age_19_29": avg("ever", (df.SQ2_range == 4).to_numpy()),
        "ever_age_70_plus": avg("ever", (df.SQ2_range == 9).to_numpy()),
        "weekly_age_19_29": avg("weekly", (df.SQ2_range == 4).to_numpy()),
        "weekly_age_70_plus": avg("weekly", (df.SQ2_range == 9).to_numpy()),
    }
    labels = data.value_labels(meta, "A19_1_1")
    shares, n = weighted_shares(df, "A19_1_1")
    out["zero_food_reason_first_rank"] = {"n": n, "shares_pct": {labels.get(float(k), k): v for k, v in shares.items()}}
    labels = data.value_labels(meta, "A19_2_1")
    shares, n = weighted_shares(df, "A19_2_1")
    out["zero_food_non_eater_reason_first_rank"] = {"n": n, "shares_pct": {labels.get(float(k), k): v for k, v in shares.items()}}
    return out


def carbonated_trend():
    out = {}
    for year, path in [("2023", paths.SAV_2023), ("2024", paths.SAV_2024), ("2025", paths.SAV_2025)]:
        df, meta = data.load_sav(path)
        labels = data.value_labels(meta, "A15_1")
        zero = [k for k, v in labels.items() if "\ubb34\uac00\ub2f9" in v and "\ud0c4\uc0b0" in v]
        sugared = [k for k, v in labels.items() if "\uac00\ub2f9 \ud0c4\uc0b0" in v and "\ubb34\uac00\ub2f9" not in v]
        if len(zero) != 1 or len(sugared) != 1:
            raise ValueError(f"{year}: could not identify A15 carbonated codes")
        w = df["psfwt"].to_numpy()
        out[year] = {
            "rows": len(df),
            "zero_code": int(zero[0]),
            "sugared_code": int(sugared[0]),
            "zero_pct": round(100 * float(np.average(df.A15_1 == zero[0], weights=w)), 2),
            "sugared_pct": round(100 * float(np.average(df.A15_1 == sugared[0], weights=w)), 2),
        }
    return out


def run():
    df, meta = data.load_sav()
    return {
        "scope": "whole 2025 adult file with the comparator's own random row splits. Not the fixed splits.",
        "rows": len(df),
        "descriptive": descriptive(df, meta),
        "t1_check": t1_check(df, meta),
        "t1_check2": t1_check2(df, meta),
        "a15_trend": carbonated_trend(),
    }


def write(r):
    paths.RESULTS.mkdir(parents=True, exist_ok=True)
    (paths.RESULTS / "reproduce_whole_file.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
