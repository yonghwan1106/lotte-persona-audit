"""Option ranking test of stage 3: can the panel order the 17 A15 options better than real alternatives?

All shares are proportions and all reported errors and biases are percentage points. No answers are read here:
score_ranking works on arrays in a context dict, so synthetic answers run the whole path in tests.
Outputs are aggregates only.
"""
import numpy as np

from . import calibration as cal

N_OPTIONS = 17
OPTIONS = tuple(range(1, N_OPTIONS + 1))
EPS = 1e-12
GAP_BANDS = (("under_1pp", 0.0, 1.0), ("1_to_3pp", 1.0, 3.0), ("3_to_5pp", 3.0, 5.0), ("5pp_and_over", 5.0, float("inf")))
AGE_BANDS = {4: "19-29", 5: "30-39", 6: "40-49", 7: "50-59", 8: "60-69", 9: "70+"}
GROUPS = ("overall", *AGE_BANDS.values())
# Option sets. Each category is a tuple of option numbers; a set is renormalised to sum to 1 for every estimator and the truth.
OPTION_SETS = {
    "all_17": tuple((o,) for o in OPTIONS),
    "no_16": tuple((o,) for o in OPTIONS if o != 16),
    "merged_coffee_15": tuple((13, 14) if o == 13 else (o,) for o in OPTIONS if o not in (14, 16)),
}
# KREI 2024 is scored only where its coding compares. Option 16 is dropped because 2025 holds no respondent on it.
KREI_SETS = ("no_16", "merged_coffee_15")
PRIMARY_SET = "merged_coffee_15"


def category_name(category):
    return "+".join(str(o) for o in category)


def collapse(shares, categories):
    """Sum options into categories and renormalise. shares has the options on its last axis."""
    shares = np.asarray(shares, dtype=float)
    out = np.stack([shares[..., [o - 1 for o in cat]].sum(axis=-1) for cat in categories], axis=-1)
    total = out.sum(axis=-1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(total > 0, out / total, np.nan)


def normalise_answers(raw):
    """(respondents, 17) raw probabilities to shares of 1 per respondent, plus the raw sums."""
    raw = np.asarray(raw, dtype=float)
    sums = raw.sum(axis=1)
    if (sums <= 0).any():
        raise ValueError("an answer has a zero sum")
    return raw / sums[:, None], sums


def sum_check(sums):
    sums = np.asarray(sums, dtype=float)
    return {
        "respondents": int(len(sums)),
        "mean": round(float(sums.mean()), 4),
        "min": round(float(sums.min()), 4),
        "max": round(float(sums.max()), 4),
        "share_within_0_01_of_1": round(float((np.abs(sums - 1) <= 0.01).mean()), 4),
        "share_over_0_05_from_1": round(float((np.abs(sums - 1) > 0.05).mean()), 4),
    }


def one_hot(options):
    options = np.asarray(options).astype(int)
    out = np.zeros((len(options), N_OPTIONS))
    out[np.arange(len(options)), options - 1] = 1.0
    return out


def weighted_shares(matrix, weights):
    weights = np.asarray(weights, dtype=float)
    return (np.asarray(matrix, dtype=float) * weights[:, None]).sum(axis=0) / weights.sum()


def average_ranks(x):
    x = np.asarray(x, dtype=float)
    _, inverse, counts = np.unique(x, return_inverse=True, return_counts=True)
    upper = np.cumsum(counts)
    return (upper - (counts - 1) / 2.0)[inverse]


def spearman(estimate, truth):
    """Spearman across options, ties on average ranks. NaN when either side is constant."""
    a, b = average_ranks(estimate), average_ranks(truth)
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def pair_scores(estimate, truth):
    """Per pair of options: (true gap pp, estimated gap pp, score). Pairs with no true gap have nan score.

    Score is 1 when the estimate orders the pair as the truth does, 0.5 when the estimate ties them, 0 when it reverses them.
    """
    i, j = np.triu_indices(len(truth), 1)
    dt = np.asarray(truth)[i] - np.asarray(truth)[j]
    de = np.asarray(estimate)[i] - np.asarray(estimate)[j]
    has_gap = np.abs(dt) > EPS
    tied = np.abs(de) <= EPS
    score = np.where(np.sign(dt) == np.sign(de), 1.0, 0.0)
    score = np.where(tied, 0.5, score)
    score = np.where(has_gap, score, np.nan)
    return 100 * np.abs(dt), 100 * np.abs(de), score


def band_of(gaps, lo, hi):
    return (gaps >= lo) & (gaps < hi)


def top_k(shares, k=3):
    """Option positions of the k largest shares. Ties go to the lower option position."""
    order = np.lexsort((np.arange(len(shares)), -np.asarray(shares)))
    return set(order[:k].tolist())


def metrics_one(estimate, truth, categories):
    """Flat metrics of one estimate against one truth, on one option set."""
    t_gap, e_gap, score = pair_scores(estimate, truth)
    out = {
        "spearman": spearman(estimate, truth),
        "pair_accuracy": float(np.nanmean(score)) if np.isfinite(score).any() else float("nan"),
        "pairs_with_true_gap": int(np.isfinite(score).sum()),
        "top3_overlap": len(top_k(estimate) & top_k(truth)),
        "share_mae_pp": float(100 * np.mean(np.abs(np.asarray(estimate) - np.asarray(truth)))),
    }
    for name, lo, hi in GAP_BANDS:
        for prefix, gaps in (("true_gap", t_gap), ("estimated_gap", e_gap)):
            k = band_of(gaps, lo, hi) & np.isfinite(score)
            out[f"{prefix}|{name}|n_pairs"] = int(k.sum())
            out[f"{prefix}|{name}|accuracy"] = float(score[k].mean()) if k.any() else float("nan")
    for c, cat in enumerate(categories):
        out[f"bias|{category_name(cat)}"] = float(100 * (estimate[c] - truth[c]))
    return out


def group_masks(ages):
    ages = np.asarray(ages).astype(int)
    masks = {"overall": np.ones(len(ages), dtype=bool)}
    for code, name in AGE_BANDS.items():
        masks[name] = ages == code
    return masks


def group_shares(matrix, weights, ages):
    """{group: shares}. A group with no row in this sample takes the sample's overall shares, as E1 does for an empty cell."""
    overall = weighted_shares(matrix, weights)
    out = {}
    for name, mask in group_masks(ages).items():
        out[name] = weighted_shares(matrix[mask], weights[mask]) if mask.any() else overall
    return out


class UnitTable:
    """Per group and survey unit weighted sums, so a survey unit resample is a matrix product."""

    def __init__(self, matrix, weights, ages, unit_index, n_units):
        self.num = {}
        self.den = {}
        for name, mask in group_masks(ages).items():
            num = np.zeros((n_units, N_OPTIONS))
            np.add.at(num, unit_index[mask], matrix[mask] * weights[mask][:, None])
            self.num[name] = num
            self.den[name] = np.bincount(unit_index[mask], weights=weights[mask], minlength=n_units)

    def shares(self, counts, group):
        den = counts @ self.den[group]
        if den <= 0:
            return None
        return (counts @ self.num[group]) / den


def direct_draws(pool, kind, repeats, seed, pi_draws, pi_seed):
    """{group: array (draws, 17)} of weighted shares of real answers in repeated draws from the calibration pool."""
    m = one_hot(pool["options"])
    draws = cal.make_draws(pool["w"], pool["units"], 200, kind, repeats, seed, pi_draws, pi_seed)
    out = {g: np.zeros((repeats, N_OPTIONS)) for g in GROUPS}
    realised = []
    for d, (idx, wts) in enumerate(draws):
        realised.append(len(idx))
        got = group_shares(m[idx], wts, pool["ages"][idx])
        for g in GROUPS:
            out[g][d] = got[g]
    return out, realised


def percentile_ci(values, digits=4):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return [None, None]
    lo, hi = np.percentile(values, [2.5, 97.5])
    return [round(float(lo), digits), round(float(hi), digits)]


def _round(v, digits=4):
    if isinstance(v, int):
        return v
    return None if v is None or not np.isfinite(v) else round(float(v), digits)


def summarise_point(point, boots=None):
    """{metric: {"value", "ci95", "resamples_used"}} from the point metrics and the bootstrap lists."""
    out = {}
    for name, value in point.items():
        block = {"value": _round(value)}
        if boots is not None and name in boots and not (name.endswith("|n_pairs") or name == "pairs_with_true_gap"):
            arr = np.array(boots[name], dtype=float)
            block["ci95"] = percentile_ci(arr)
            block["resamples_used"] = int(np.isfinite(arr).sum())
        out[name] = block
    return out


def summarise_draws(rows):
    """Mean and percentile interval of a metric across draws against a fixed truth."""
    out = {}
    for name in rows[0]:
        arr = np.array([r[name] for r in rows], dtype=float)
        ok = arr[np.isfinite(arr)]
        out[name] = {"mean": None if len(ok) == 0 else round(float(ok.mean()), 4), "draw_ci95": percentile_ci(ok), "draws_used": int(len(ok))}
    return out


def difference_block(a, b):
    """Paired difference of metric lists, a minus b, resample by resample."""
    out = {}
    for name in a:
        if name.endswith("|n_pairs") or name == "pairs_with_true_gap" or name not in b:
            continue
        d = np.array(a[name], dtype=float) - np.array(b[name], dtype=float)
        ok = d[np.isfinite(d)]
        out[name] = {"mean_diff": None if len(ok) == 0 else round(float(ok.mean()), 4), "ci95": percentile_ci(ok), "resamples_used": int(len(ok))}
    return out


def score_ranking(ctx, answers, plan):
    """ctx holds truth, gate, pool, krei_2024 and train. answers is {condition: normalised array (gate respondents, 17)}."""
    truth, gate, pool = ctx["truth"], ctx["gate"], ctx["pool"]
    truth_m = one_hot(truth["options"])
    gate_real_m = one_hot(gate["options"])
    truth_g = group_shares(truth_m, truth["w"], truth["ages"])
    truth_ps = group_shares(truth_m, truth["w_poststratified"], truth["ages"])
    estimates = {f"panel_{cond}": group_shares(p, gate["w"], gate["ages"]) for cond, p in answers.items()}
    fixed = {"krei_2024": ctx["krei_2024"], "train_reference": ctx["train"], "gate_300_real_reference": group_shares(gate_real_m, gate["w"], gate["ages"])}
    direct = {}
    realised = {}
    for k_i, kind in enumerate(("row", "cluster")):
        direct[kind], realised[kind] = direct_draws(pool, kind, plan["draws"], [plan["seed"], 200, k_i], plan["pi_draws"], plan["pi_seed"])

    uniq = np.unique(np.concatenate([truth["units"], gate["units"]]))
    index = {u: i for i, u in enumerate(uniq.tolist())}
    n_units = len(uniq)
    truth_table = UnitTable(truth_m, truth["w"], truth["ages"], np.array([index[u] for u in truth["units"].tolist()]), n_units)
    gate_index = np.array([index[u] for u in gate["units"].tolist()])
    panel_tables = {f"panel_{cond}": UnitTable(p, gate["w"], gate["ages"], gate_index, n_units) for cond, p in answers.items()}
    real_table = UnitTable(gate_real_m, gate["w"], gate["ages"], gate_index, n_units)

    rng = np.random.default_rng([plan["seed"], 3])
    picks = rng.integers(0, n_units, size=(plan["bootstrap"], n_units))
    boots = {s: {g: {} for g in GROUPS} for s in OPTION_SETS}
    allowed = {s: list(panel_tables) + ["direct_row", "direct_cluster", "gate_300_real_reference", "train_reference"] + (["krei_2024"] if s in KREI_SETS else []) for s in OPTION_SETS}

    def push(store, name, metrics):
        slot = store.setdefault(name, {})
        for key, value in metrics.items():
            slot.setdefault(key, []).append(value)

    for r in range(plan["bootstrap"]):
        counts = np.bincount(picks[r], minlength=n_units).astype(float)
        for g in GROUPS:
            t = truth_table.shares(counts, g)
            current = {name: table.shares(counts, g) for name, table in panel_tables.items()}
            current["gate_300_real_reference"] = real_table.shares(counts, g)
            current["krei_2024"] = fixed["krei_2024"][g]
            current["train_reference"] = fixed["train_reference"][g]
            current["direct_row"] = direct["row"][g][r % plan["draws"]]
            current["direct_cluster"] = direct["cluster"][g][r % plan["draws"]]
            # A group empty in this resample is skipped for every estimator, so the differences stay paired.
            if t is None or any(v is None for v in current.values()):
                continue
            for s, cats in OPTION_SETS.items():
                ts = collapse(t, cats)
                for name in allowed[s]:
                    push(boots[s][g], name, metrics_one(collapse(current[name], cats), ts, cats))

    out = {"truth_shares_pct": {g: {str(o): round(100 * float(truth_g[g][o - 1]), 2) for o in OPTIONS} for g in GROUPS}, "direct_realised_n_mean": {k: round(float(np.mean(v)), 1) for k, v in realised.items()}, "sets": {}}
    for s, cats in OPTION_SETS.items():
        out["sets"][s] = {"categories": [category_name(c) for c in cats], "groups": {}}
        for g in GROUPS:
            ts = collapse(truth_g[g], cats)
            tps = collapse(truth_ps[g], cats)
            block = {"estimators": {}, "direct": {}, "differences": {}, "poststratified_truth_sensitivity": {}}
            for name in [*panel_tables, "gate_300_real_reference", "train_reference"] + (["krei_2024"] if s in KREI_SETS else []):
                vec = estimates.get(name, fixed.get(name))[g]
                est = collapse(vec, cats)
                block["estimators"][name] = summarise_point(metrics_one(est, ts, cats), boots[s][g].get(name))
                block["estimators"][name]["_shares_pct"] = {category_name(c): round(100 * float(v), 2) for c, v in zip(cats, est)}
                keep = ("spearman", "pair_accuracy", "top3_overlap", "share_mae_pp")
                m = metrics_one(est, tps, cats)
                block["poststratified_truth_sensitivity"][name] = {k: _round(m[k]) for k in keep}
            for kind in ("row", "cluster"):
                rows = [metrics_one(collapse(direct[kind][g][d], cats), ts, cats) for d in range(plan["draws"])]
                block["direct"][f"direct_{kind}"] = summarise_draws(rows)
                m_ps = [metrics_one(collapse(direct[kind][g][d], cats), tps, cats) for d in range(plan["draws"])]
                block["poststratified_truth_sensitivity"][f"direct_{kind}"] = {k: _round(float(np.nanmean([x[k] for x in m_ps]))) for k in ("spearman", "pair_accuracy", "top3_overlap", "share_mae_pp")}
            for name in panel_tables:
                for other in ["direct_row", "direct_cluster"] + (["krei_2024"] if s in KREI_SETS else []):
                    block["differences"][f"{name}_minus_{other}"] = difference_block(boots[s][g].get(name, {}), boots[s][g].get(other, {}))
            out["sets"][s]["groups"][g] = block
    out["operating_rule"] = operating_rule(out, list(panel_tables))
    return out


def operating_rule(result, panels):
    """The frozen reading of the gap bands, on the primary option set and the overall group. Nothing is chosen after the fact."""
    block = result["sets"][PRIMARY_SET]["groups"]["overall"]
    rows = []
    for panel in panels:
        for prefix in ("true_gap", "estimated_gap"):
            for name, _, _ in GAP_BANDS:
                acc = block["estimators"][panel][f"{prefix}|{name}|accuracy"]
                n_pairs = block["estimators"][panel][f"{prefix}|{name}|n_pairs"]["value"]
                row = {"panel": panel, "gap_kind": prefix, "band": name, "n_pairs": n_pairs, "accuracy": acc["value"], "ci95": acc.get("ci95")}
                lo = (acc.get("ci95") or [None])[0]
                row["above_chance"] = bool(lo is not None and lo > 0.5)
                for other in ("direct_row", "krei_2024"):
                    d = block["differences"][f"{panel}_minus_{other}"].get(f"{prefix}|{name}|accuracy")
                    row[f"minus_{other}"] = d
                    row[f"beats_{other}"] = bool(d and d["ci95"][0] is not None and d["ci95"][0] > 0)
                rows.append(row)
    return rows


# ---------- markdown ----------


def _fmt(block, key, digits=3):
    b = block.get(key) or {}
    v = b.get("value", b.get("mean"))
    if v is None:
        return "-"
    ci = b.get("ci95", b.get("draw_ci95"))
    text = f"{v:.{digits}f}"
    if ci and ci[0] is not None:
        text += f" [{ci[0]:.{digits}f},{ci[1]:.{digits}f}]"
    return text


def _estimators_in_order(block):
    names = [n for n in block["estimators"] if n.startswith("panel_")]
    out = [(n, block["estimators"][n]) for n in names]
    out += [(n, block["direct"][n]) for n in ("direct_row", "direct_cluster")]
    for n in ("krei_2024", "gate_300_real_reference", "train_reference"):
        if n in block["estimators"]:
            out.append((n, block["estimators"][n]))
    return out


def metric_table(block):
    lines = ["| estimator | Spearman | pair accuracy | top 3 overlap of 3 | share MAE pp |", "|---|---|---|---|---|"]
    for name, b in _estimators_in_order(block):
        lines.append(f"| {name} | {_fmt(b, 'spearman')} | {_fmt(b, 'pair_accuracy')} | {_fmt(b, 'top3_overlap', 2)} | {_fmt(b, 'share_mae_pp', 2)} |")
    return lines


def gap_table(block, prefix):
    head = " | ".join(f"{n} acc (pairs)" for n, _, _ in GAP_BANDS)
    lines = [f"| estimator | {head} |", "|---|" + "---|" * len(GAP_BANDS)]
    for name, b in _estimators_in_order(block):
        cells = []
        for n, _, _ in GAP_BANDS:
            pairs = b.get(f"{prefix}|{n}|n_pairs") or {}
            count = pairs.get("value", pairs.get("mean"))
            cells.append(f"{_fmt(b, f'{prefix}|{n}|accuracy')} ({count})")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return lines


def difference_table(block):
    keys = ["spearman", "pair_accuracy", "top3_overlap", "share_mae_pp"] + [f"true_gap|{n}|accuracy" for n, _, _ in GAP_BANDS]
    lines = ["| comparison | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for comp, d in block["differences"].items():
        cells = []
        for k in keys:
            v = d.get(k)
            cells.append("-" if not v or v["mean_diff"] is None else f"{v['mean_diff']:+.3f} [{v['ci95'][0]:+.3f},{v['ci95'][1]:+.3f}]")
        lines.append(f"| {comp} | " + " | ".join(cells) + " |")
    return lines


def to_markdown(result, labels, meta):
    lines = ["# Stage 3 option ranking", "", meta["frame"], "", f"Raw answer sums before normalising: {meta['sum_check']}", f"Direct draws realised n: {result['direct_realised_n_mean']}. Truth rows outside the 1000 panel: {meta['truth_rows']}, units {meta['truth_units']}. Scored: {meta['scored']}. Incomplete: {meta['incomplete']}.", ""]
    lines += ["## Truth shares pct, A15_1, test split outside the panel, psfwt", "", "| option | label | " + " | ".join(GROUPS) + " |", "|---|---|" + "---|" * len(GROUPS)]
    for o in OPTIONS:
        lines.append(f"| {o} | {labels[str(o)]} | " + " | ".join(str(result["truth_shares_pct"][g][str(o)]) for g in GROUPS) + " |")
    for s in OPTION_SETS:
        block = result["sets"][s]["groups"]["overall"]
        lines += ["", f"## Option set {s}, overall", "", f"Categories: {', '.join(result['sets'][s]['categories'])}", "", *metric_table(block), "", "### Pair accuracy by true gap band", "", *gap_table(block, "true_gap"), "", "### Pair accuracy by the estimate's own gap band, secondary", "", *gap_table(block, "estimated_gap"), "", "### Paired differences, survey unit bootstrap with direct draws cycled", "", *difference_table(block), "", "### Sensitivity: truth post-stratified to the whole test split's 12 cell psfwt totals", "", "| estimator | Spearman | pair accuracy | top 3 | share MAE pp |", "|---|---|---|---|---|"]
        for name, v in block["poststratified_truth_sensitivity"].items():
            lines.append(f"| {name} | {v['spearman']} | {v['pair_accuracy']} | {v['top3_overlap']} | {v['share_mae_pp']} |")
    for s in (PRIMARY_SET, "all_17"):
        lines += ["", f"## Per age band, option set {s}", ""]
        for g in GROUPS[1:]:
            block = result["sets"][s]["groups"][g]
            lines += [f"### {g}", "", *metric_table(block), "", *gap_table(block, "true_gap"), ""]
    lines += ["## Per option bias pp, overall, option set all_17", "", "| option | label | truth pct | " + " | ".join(n for n, _ in _estimators_in_order(result["sets"]["all_17"]["groups"]["overall"])) + " |", "|---|---|---|" + "---|" * len(_estimators_in_order(result["sets"]["all_17"]["groups"]["overall"]))]
    block = result["sets"]["all_17"]["groups"]["overall"]
    for o in OPTIONS:
        lines.append(f"| {o} | {labels[str(o)]} | {result['truth_shares_pct']['overall'][str(o)]} | " + " | ".join(_fmt(b, f"bias|{o}", 2) for _, b in _estimators_in_order(block)) + " |")
    lines += ["", "## Per option bias pp, overall, option set merged_coffee_15, with KREI 2024", ""]
    block = result["sets"][PRIMARY_SET]["groups"]["overall"]
    ests = _estimators_in_order(block)
    lines += ["| category | " + " | ".join(n for n, _ in ests) + " |", "|---|" + "---|" * len(ests)]
    for c in result["sets"][PRIMARY_SET]["categories"]:
        lines.append(f"| {c} | " + " | ".join(_fmt(b, f"bias|{c}", 2) for _, b in ests) + " |")
    lines += ["", "## Frozen operating rule reading, option set merged_coffee_15, overall", "", "above_chance: lower bound of the panel's pair accuracy over 0.5. beats_x: lower bound of the paired difference to x over 0. True gap bands are not knowable before a real survey; the estimated gap rows are what a user would see.", "", "| panel | gap kind | band | pairs | accuracy [95] | above chance | minus direct_row | beats direct_row | minus krei_2024 | beats krei_2024 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in result["operating_rule"]:
        ci = r["ci95"] or [None, None]
        acc = "-" if r["accuracy"] is None else f"{r['accuracy']:.3f} [{ci[0]},{ci[1]}]"
        def diff(d):
            return "-" if not d or d["mean_diff"] is None else f"{d['mean_diff']:+.3f} [{d['ci95'][0]:+.3f},{d['ci95'][1]:+.3f}]"
        lines.append(f"| {r['panel']} | {r['gap_kind']} | {r['band']} | {r['n_pairs']} | {acc} | {r['above_chance']} | {diff(r['minus_direct_row'])} | {r['beats_direct_row']} | {diff(r['minus_krei_2024'])} | {r['beats_krei_2024']} |")
    return "\n".join(lines) + "\n"
