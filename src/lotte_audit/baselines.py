"""Baselines on the test split: constant, real sample direct and shrinkage, floor, ceiling.

Every model is fitted on the train split only and evaluated on the test split with psfwt.
Real samples are drawn from the train split, so the calibration pool stays unused and the truth is the
same test-split cell table for every estimator.
"""
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from . import data, metrics, paths, persona, splits

SAMPLE_SIZES = (100, 250, 500, 1000)
REPEATS = 100
K = 30


def design_matrix(df, cols, reference_columns=None):
    """One-hot design; missing becomes its own level. Align to reference columns when given."""
    x = pd.get_dummies(df[cols].fillna(-1).astype(int).astype(str)).astype(float)
    if reference_columns is not None:
        x = x.reindex(columns=reference_columns, fill_value=0.0)
    return x


def fit_logistic(df_train, y_train, w_train, cols):
    x = design_matrix(df_train, cols)
    x = x.loc[:, x.mean() > 0.01] if x.shape[1] > 60 else x
    model = LogisticRegression(max_iter=400, C=0.05)
    model.fit(x.to_numpy(), y_train, sample_weight=w_train)
    return model, list(x.columns)


def predict_logistic(model, columns, df, cols):
    return model.predict_proba(design_matrix(df, cols, columns).to_numpy())[:, 1]


def real_sample_curve(y_train, w_train, cell_train, truth, seed=paths.SEED, repeats=REPEATS, sizes=SAMPLE_SIZES, k=K):
    """Mean cell MAE of direct and shrunk estimates from n rows of the train split, against test truth."""
    rng = np.random.default_rng(seed)
    universe = sorted(truth)
    out = {}
    n_rows = len(y_train)
    for n in sizes:
        raw, shrunk, sample_constant = [], [], []
        for _ in range(repeats):
            idx = rng.choice(n_rows, size=n, replace=False)
            y, w, c = y_train[idx], w_train[idx], cell_train[idx]
            national = float(np.average(y, weights=w))
            direct = metrics.cell_means(y, w, c, universe)
            counts = {u: int((c == u).sum()) for u in universe}
            est_raw = {u: direct.get(u, national) for u in universe}
            est_shrunk = {u: (counts[u] * est_raw[u] + k * national) / (counts[u] + k) for u in universe}
            raw.append(metrics.cell_mae(est_raw, truth))
            shrunk.append(metrics.cell_mae(est_shrunk, truth))
            sample_constant.append(metrics.constant_mae(national, truth))
        out[n] = {
            "raw": float(np.mean(raw)),
            "shrunk": float(np.mean(shrunk)),
            "sample_national_mean_only": float(np.mean(sample_constant)),
        }
    return out


def unit_bootstrap_auc(y, p, w, units, seed=paths.SEED, reps=300):
    """Percentile 95% interval of weighted AUC, resampling survey units."""
    rng = np.random.default_rng(seed)
    uniq, inv = np.unique(units, return_inverse=True)
    groups = [np.flatnonzero(inv == i) for i in range(len(uniq))]
    vals = []
    for _ in range(reps):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([groups[i] for i in pick])
        a = metrics.weighted_auc(y[idx], p[idx], w[idx])
        if a is not None:
            vals.append(a)
    if not vals:
        return None
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return [round(float(lo), 3), round(float(hi), 3)]


def demographic_columns():
    t = persona.load_templates()
    return list(t["c1_vars"].values())


def allowlist_columns():
    return [item["var"] for item in persona.load_final_allowlist()["items"]]


def floor_columns():
    return [paths.AGE, paths.SEX]


def fit_reference_models(df, targets, train):
    """Fit floor models on the train split. Used by baselines and by scoring."""
    tdf = df.loc[train]
    w = tdf[paths.WEIGHT].to_numpy()
    models = {}
    for t in paths.TARGETS:
        y = targets[t].to_numpy()[train]
        models[t] = {
            "floor": (fit_logistic(tdf, y, w, floor_columns()), floor_columns()),
            "floor_demog": (fit_logistic(tdf, y, w, demographic_columns()), demographic_columns()),
        }
    return models


def score_prediction(y, p, w, units):
    auc = metrics.weighted_auc(y, p, w)
    within, used = metrics.within_group_auc(y, p, units, w)
    return {
        "auc": round(auc, 3),
        "auc_ci95_unit_bootstrap": unit_bootstrap_auc(y, p, w, units),
        "within_unit_auc": None if within is None else round(within, 3),
        "within_unit_groups": used,
    }


def compute():
    df, meta = data.load_sav()
    manifest = splits.load_manifest(df)
    mk = splits.masks(manifest)
    train, test = mk["train"], mk["test"]
    targets = data.derive_targets(df)
    cells = data.cell_id(df)
    w = df[paths.WEIGHT].to_numpy()
    units = df[paths.PSU].to_numpy()
    out = {
        "seed": paths.SEED,
        "rows": {k: int(v.sum()) for k, v in mk.items()},
        "items": {},
        "note": "AUC and truth are computed on the test split with psfwt. Models are fitted on train.",
    }
    cols_floor, cols_demog = floor_columns(), demographic_columns()
    cols_allow = allowlist_columns()
    cols_ceiling = cols_demog + cols_allow
    tdf, sdf = df.loc[train], df.loc[test]
    for t in paths.TARGETS:
        y = targets[t].to_numpy()
        truth = metrics.cell_means(y[test], w[test], cells[test])
        national_train = float(np.average(y[train], weights=w[train]))
        national_test = float(np.average(y[test], weights=w[test]))
        const = metrics.constant_mae(national_train, truth)
        curve = real_sample_curve(y[train], w[train], cells[train], truth)
        best = {n: min(v["raw"], v["shrunk"]) for n, v in curve.items()}
        full_train = metrics.cell_mae(metrics.cell_means(y[train], w[train], cells[train]), truth)

        m, c = fit_logistic(tdf, y[train], w[train], cols_floor)
        floor_p = predict_logistic(m, c, sdf, cols_floor)
        m, c = fit_logistic(tdf, y[train], w[train], cols_demog)
        demog_p = predict_logistic(m, c, sdf, cols_demog)
        m, c = fit_logistic(tdf, y[train], w[train], cols_ceiling)
        ceiling_p = predict_logistic(m, c, sdf, cols_ceiling)
        x_tr = design_matrix(tdf, cols_ceiling)
        x_te = design_matrix(sdf, cols_ceiling, list(x_tr.columns))
        gbm = HistGradientBoostingClassifier(random_state=paths.SEED)
        gbm.fit(x_tr.to_numpy(), y[train], sample_weight=w[train])
        gbm_p = gbm.predict_proba(x_te.to_numpy())[:, 1]

        yt, wt, ut = y[test], w[test], units[test]
        out["items"][t] = {
            "national_train_pct": round(100 * national_train, 2),
            "national_test_pct": round(100 * national_test, 2),
            "n_cells": len(truth),
            "constant_cell_mae": round(const, 2),
            "full_train_raw_cell_mae": round(full_train, 2),
            "real_sample": {str(n): {k: round(x, 2) for k, x in v.items()} for n, v in curve.items()},
            "best_of_raw_shrunk": {str(n): round(v, 2) for n, v in best.items()},
            "floor_age_sex": score_prediction(yt, floor_p, wt, ut),
            "floor_all_c1_demographics": score_prediction(yt, demog_p, wt, ut),
            "ceiling_allowlist_logistic": score_prediction(yt, ceiling_p, wt, ut),
            "ceiling_allowlist_gbm": score_prediction(yt, gbm_p, wt, ut),
        }
    items = out["items"]
    mean = lambda f: round(float(np.mean([f(items[t]) for t in paths.TARGETS])), 2)
    out["average_over_items"] = {
        "constant_cell_mae": mean(lambda v: v["constant_cell_mae"]),
        "full_train_raw_cell_mae": mean(lambda v: v["full_train_raw_cell_mae"]),
        "real_sample": {
            str(n): {
                "raw": mean(lambda v: v["real_sample"][str(n)]["raw"]),
                "shrunk": mean(lambda v: v["real_sample"][str(n)]["shrunk"]),
                "sample_national_mean_only": mean(lambda v: v["real_sample"][str(n)]["sample_national_mean_only"]),
            }
            for n in SAMPLE_SIZES
        },
    }
    out["average_over_items"]["best_of_raw_shrunk"] = {
        str(n): round(min(out["average_over_items"]["real_sample"][str(n)]["raw"], out["average_over_items"]["real_sample"][str(n)]["shrunk"]), 2)
        for n in SAMPLE_SIZES
    }
    out["allowlist_size"] = len(cols_allow)
    return out


def to_markdown(b):
    lines = ["# Baselines (test split, psfwt)", "", f"Rows: {b['rows']}. Seed {b['seed']}. Allowlist size {b['allowlist_size']}.", ""]
    lines += ["## Cell MAE, pp", "", "| item | constant | n=100 raw | n=100 shrunk | n=250 raw | n=250 shrunk | n=500 raw | n=500 shrunk | n=1000 raw | n=1000 shrunk | all train raw |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in paths.TARGETS:
        v = b["items"][t]
        rs = v["real_sample"]
        lines.append("| " + " | ".join([t, str(v["constant_cell_mae"])] + [str(rs[str(n)][k]) for n in SAMPLE_SIZES for k in ("raw", "shrunk")] + [str(v["full_train_raw_cell_mae"])]) + " |")
    a = b["average_over_items"]
    lines.append("| " + " | ".join(["average", str(a["constant_cell_mae"])] + [str(a["real_sample"][str(n)][k]) for n in SAMPLE_SIZES for k in ("raw", "shrunk")] + [str(a["full_train_raw_cell_mae"])]) + " |")
    lines += ["", "## AUC on the test split", "", "| item | model | AUC | 95% CI (unit bootstrap) | within-unit AUC | usable units |", "|---|---|---|---|---|---|"]
    for t in paths.TARGETS:
        v = b["items"][t]
        for name in ("floor_age_sex", "floor_all_c1_demographics", "ceiling_allowlist_logistic", "ceiling_allowlist_gbm"):
            r = v[name]
            lines.append(f"| {t} | {name} | {r['auc']} | {r['auc_ci95_unit_bootstrap']} | {r['within_unit_auc']} | {r['within_unit_groups']} |")
    return "\n".join(lines) + "\n"


def write(b):
    paths.RESULTS.mkdir(parents=True, exist_ok=True)
    (paths.RESULTS / "baselines.json").write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    (paths.RESULTS / "baselines.md").write_text(to_markdown(b), encoding="utf-8")
