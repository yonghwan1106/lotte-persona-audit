"""Why did the comparator's tabular model reach AUC 0.89~0.912 on the weekly item?

Runs on the TRAIN split only, with inner hold-outs, so the test split stays closed. Each experiment
changes one thing against the comparator's own recipe (feature filter, model, inner split type).
"""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from . import data, leakguard, metrics, paths, splits

COMPARATOR_LABEL_TERMS = ("\uc81c\ub85c", "\uc74c\ub8cc", "\ud0c4\uc0b0", "\uac00\uc911")


def comparator_features(df, meta):
    """The comparator's filter from t1_check2.py: prefix drop plus label terms on the variable label only."""
    labels = meta.column_names_to_labels
    num = df.select_dtypes("number")
    drop = {k for k in num.columns if k.startswith("A15") or k.startswith("A19") or k.startswith("F13")}
    drop |= {"psfwt", "ever", "weekly", "carb"}
    for k in num.columns:
        lab = labels.get(k) or ""
        if any(t in lab for t in COMPARATOR_LABEL_TERMS):
            drop.add(k)
    return [k for k in num.columns if k not in drop and df[k].notna().mean() > 0.95 and 1 < df[k].nunique() <= 12]


def one_hot(df, cols):
    x = pd.get_dummies(df[cols].fillna(-1).astype(int).astype(str)).astype(float)
    return x.loc[:, x.mean() > 0.01]


def inner_groups(df, kind, seed):
    """Boolean inner-train mask for 70/30 inner hold-out by row, household or survey unit."""
    rng = np.random.default_rng(seed)
    if kind == "row":
        order = rng.permutation(len(df))
        cut = int(0.7 * len(df))
        mask = np.zeros(len(df), dtype=bool)
        mask[order[:cut]] = True
        return mask
    key = {"household": paths.HOUSEHOLD, "unit": paths.PSU}[kind]
    uniq = df[key].unique()
    rng.shuffle(uniq)
    return df[key].isin(set(uniq[: int(0.7 * len(uniq))])).to_numpy()


def fit_auc(x, y, w, mask):
    m = LogisticRegression(max_iter=300, C=0.05)
    m.fit(x[mask], y[mask], sample_weight=w[mask])
    return float(roc_auc_score(y[~mask], m.predict_proba(x[~mask])[:, 1], sample_weight=w[~mask])), m


def unit_icc(flag, units):
    """One-way ANOVA intraclass correlation of a binary flag across survey units."""
    d = pd.DataFrame({"y": np.asarray(flag, dtype=float), "u": units})
    g = d.groupby("u").y
    sizes, means = g.size(), g.mean()
    p = d.y.mean()
    k = sizes.mean()
    msb = (sizes * (means - p) ** 2).sum() / (len(sizes) - 1)
    msw = (sizes * means * (1 - means)).sum() / (sizes.sum() - len(sizes))
    return float((msb - msw) / (msb + (k - 1) * msw))


def decomposition(tdf, y_all, w, good, seeds):
    """Pooled AUC against AUC inside one survey unit. Inside a unit, unit-level effects cancel."""
    own = [c for c in good if not c.startswith("J_")]
    design = ("STR", "division", paths.REGION, "\uad8c\uc5ed", "DONG", "\uac00\uad6c\uc6d0no", paths.AGE, paths.SEX)
    own_items = [c for c in own if not c.startswith("JJ_") and c not in design]
    units = tdf[paths.PSU].to_numpy()
    rows = []
    for name, cols in [("own items, no demographics", own_items), ("age and sex only", [paths.AGE, paths.SEX]), ("all comparator features", good)]:
        x = one_hot(tdf, cols).to_numpy()
        for t in paths.TARGETS:
            y = y_all[t].to_numpy()
            pooled, within, usable, unit_r = [], [], [], []
            for s in seeds:
                mask = inner_groups(tdf, "unit", s)
                a, m = fit_auc(x, y, w, mask)
                p = m.predict_proba(x[~mask])[:, 1]
                inner, used = metrics.within_group_auc(y[~mask], p, units[~mask], w[~mask])
                by_unit = pd.DataFrame({"u": units[~mask], "p": p, "y": y[~mask]}).groupby("u").mean()
                pooled.append(a)
                within.append(inner)
                usable.append(used)
                unit_r.append(np.corrcoef(by_unit.p, by_unit.y)[0, 1])
            rows.append(
                {
                    "features": name,
                    "target": t,
                    "pooled_auc": round(float(np.mean(pooled)), 3),
                    "within_unit_auc": round(float(np.mean(within)), 3),
                    "usable_units": int(np.mean(usable)),
                    "unit_level_r_pred_actual": round(float(np.mean(unit_r)), 3),
                }
            )
    return rows


def cluster_facts(tdf, y_all, w):
    units = tdf[paths.PSU].to_numpy()
    out = {"unit_icc": {}, "leave_self_out_unit_rate_auc": {}, "household_concordance": {}}
    for t in paths.TARGETS:
        y = y_all[t].astype(float)
        out["unit_icc"][t] = round(unit_icc(y, units), 3)
        s = y.groupby(units).transform("sum")
        n = y.groupby(units).transform("size")
        other = ((s - y) / (n - 1).replace(0, np.nan)).fillna(0.0)
        out["leave_self_out_unit_rate_auc"][t] = round(float(roc_auc_score(y, other, sample_weight=w)), 3)
        hh = tdf[paths.HOUSEHOLD].to_numpy()
        keep = pd.Series(hh).groupby(hh).transform("size").to_numpy() > 1
        yk = y[keep]
        g = yk.groupby(hh[keep])
        other_rate = (g.transform("sum") - yk) / (g.transform("size") - 1)
        out["household_concordance"][t] = {
            "other_member_positive_if_self_positive": round(float(other_rate[yk == 1].mean()), 3),
            "other_member_positive_if_self_negative": round(float(other_rate[yk == 0].mean()), 3),
        }
    flags = {
        "female": tdf[paths.SEX] == 2,
        "age_under_40": tdf[paths.AGE] <= 5,
        "regular_meals_A4": tdf["A4"] == 1,
        "uses_sns_often_D4": tdf["D4"] == 3,
        "exercise_BA4": tdf["BA4"] == 1,
    }
    out["unit_icc_reference_items"] = {k: round(unit_icc(v, units), 3) for k, v in flags.items()}
    rates = y_all["weekly"].groupby(units).mean()
    out["units_with_no_weekly_respondent"] = {"units": int((rates == 0).sum()), "of": int(len(rates))}
    by_stratum = pd.DataFrame({"s": tdf[paths.STRATUM].astype(int), "y": y_all["weekly"], "w": w})
    by_stratum["yw"] = by_stratum.y * by_stratum.w
    agg = by_stratum.groupby("s")[["yw", "w"]].sum()
    out["weekly_pct_by_stratum"] = {str(k): round(100 * float(v), 1) for k, v in (agg.yw / agg.w).items()}
    return out


def run(seeds=(1, 2, 3)):
    df, meta = data.load_sav()
    manifest = splits.load_manifest(df)
    train = splits.masks(manifest)["train"]
    tdf = df.loc[train].reset_index(drop=True)
    y_all = data.derive_targets(tdf)
    w = tdf[paths.WEIGHT].to_numpy()
    good = comparator_features(tdf, meta)
    groups = {
        "J_ household-level": [c for c in good if c.startswith("J_")],
        "JJ_ own demographics": [c for c in good if c.startswith("JJ_")],
        "design ids": [
            c
            for c in good
            if c in ("STR", "division", "urban", "RG", "AREA", paths.REGION, "\uad8c\uc5ed", "DONG", "\uac00\uad6c\uc6d0no")
        ],
    }
    own = [c for c in good if not c.startswith("J_")]
    sets = {
        "all comparator features": good,
        "without J_": own,
        "only J_": groups["J_ household-level"],
        "own items, no demographics": [
            c for c in own if not c.startswith("JJ_") and c not in groups["design ids"] and c not in (paths.AGE, paths.SEX)
        ],
    }
    compiled = leakguard.compile_block(leakguard.load_patterns())
    regex_hits = []
    for c in good:
        texts = [data.var_label(meta, c)] + list(data.value_labels(meta, c).values())
        if any(rx.search(t or "") for rx in compiled.values() for t in texts):
            regex_hits.append(c)
    sets["all comparator features minus leak-guard regex hits"] = [c for c in good if c not in regex_hits]
    out = {"n_train": int(train.sum()), "n_features": {k: len(v) for k, v in sets.items()}, "comparator_features_hit_by_leak_regex": len(regex_hits), "experiments": []}
    for name, cols in sets.items():
        x = one_hot(tdf, cols).to_numpy()
        for kind in ("row", "household", "unit"):
            row = {"features": name, "inner_split": kind, "n_dummies": int(x.shape[1])}
            for t in paths.TARGETS:
                aucs = [fit_auc(x, y_all[t].to_numpy(), w, inner_groups(tdf, kind, s))[0] for s in seeds]
                row[t] = round(float(np.mean(aucs)), 3)
                row[t + "_sd"] = round(float(np.std(aucs)), 3)
            out["experiments"].append(row)
    out["decomposition"] = decomposition(tdf, y_all, w, good, seeds)
    out["cluster_facts"] = cluster_facts(tdf, y_all, w)
    # Top weekly coefficients on all comparator features, inner split by survey unit.
    xdf = one_hot(tdf, good)
    _, model = fit_auc(xdf.to_numpy(), y_all["weekly"].to_numpy(), w, inner_groups(tdf, "unit", seeds[0]))
    top = np.argsort(-np.abs(model.coef_[0]))[:25]
    out["top_weekly_coefficients"] = [
        {
            "dummy": str(xdf.columns[i]),
            "coef": round(float(model.coef_[0][i]), 3),
            "label": data.var_label(meta, str(xdf.columns[i]).rsplit("_", 1)[0])[:80],
        }
        for i in top
    ]
    return out


def write(out):
    paths.RESULTS.mkdir(parents=True, exist_ok=True)
    (paths.RESULTS / "leakage_hunt.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
