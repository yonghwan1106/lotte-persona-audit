"""Stage 4 measures: allocation, pre-flagging wrong cells, and the validity of the duel. Stored answers only, no API.

Every function works on a main_score context and answer arrays, so synthetic answers can run the whole path in tests. Outputs are aggregates.
The plan is config/prereg_stage4.json.
"""
import numpy as np
from scipy import stats

from . import calibration as cal, duel, verdict_study

ITEMS = ("ever", "weekly", "carb")
AVERAGE = "average"
CANON_ALLOCATIONS = ("equal", "proportional", "panel_neyman", "reference_neyman")
BY_ITEM_ALLOCATIONS = ("panel_neyman_by_item", "reference_neyman_by_item")


# ---------- A1 allocation ----------


def neyman_shares(cell_share, p):
    """Share proportional to W_h * sqrt(p_h (1 - p_h))."""
    raw = np.asarray(cell_share, dtype=float) * np.sqrt(np.clip(p, 0.0, 1.0) * (1.0 - np.clip(p, 0.0, 1.0)))
    if raw.sum() <= 0:
        raise ValueError("every cell has zero spread")
    return raw / raw.sum()


def capped_targets(shares, n, caps):
    """Unrounded targets. A cell past its cap is fixed there and its surplus goes to the free cells by share, until none is past."""
    shares = np.asarray(shares, dtype=float)
    caps = np.asarray(caps, dtype=float)
    if caps.sum() < n:
        raise ValueError("the pool holds fewer rows than the sample")
    target = np.zeros(len(shares))
    fixed = np.zeros(len(shares), dtype=bool)
    while True:
        free = ~fixed
        left = n - caps[fixed].sum()
        if shares[free].sum() > 0:
            target[free] = shares[free] / shares[free].sum() * left
        else:
            target[free] = 0.0
        over = free & (target > caps)
        target[fixed] = caps[fixed]
        if not over.any():
            return target
        target[over] = caps[over]
        fixed |= over


def round_targets(target, n, caps):
    """Largest remainder, ties to the lower cell index, never past a cap."""
    base = np.floor(np.asarray(target, dtype=float) + 1e-12).astype(int)
    rest = np.asarray(target, dtype=float) - base
    order = sorted(range(len(base)), key=lambda i: (-round(float(rest[i]), 12), i))
    left = int(n - base.sum())
    while left > 0:
        moved = False
        for i in order:
            if left and base[i] < caps[i]:
                base[i] += 1
                left -= 1
                moved = True
        if not moved:
            raise ValueError("no room under the caps")
    return base


def allocate(shares, n, caps):
    return round_targets(capped_targets(shares, n, caps), n, caps)


def build_allocations(cell_share, panel_p, reference_p, n, caps):
    """{allocation: {item: n per cell}}. Canonical allocations hold one vector for every item."""
    cell_share = np.asarray(cell_share, dtype=float)
    m = len(cell_share)
    panel_by_item = {t: neyman_shares(cell_share, panel_p[t]) for t in ITEMS}
    ref_by_item = {t: neyman_shares(cell_share, reference_p[t]) for t in ITEMS}
    one = {
        "equal": np.full(m, 1.0 / m),
        "proportional": cell_share / cell_share.sum(),
        "panel_neyman": np.mean([panel_by_item[t] for t in ITEMS], axis=0),
        "reference_neyman": np.mean([ref_by_item[t] for t in ITEMS], axis=0),
    }
    out = {name: {t: allocate(s, n, caps) for t in ITEMS} for name, s in one.items()}
    out["panel_neyman_by_item"] = {t: allocate(panel_by_item[t], n, caps) for t in ITEMS}
    out["reference_neyman_by_item"] = {t: allocate(ref_by_item[t], n, caps) for t in ITEMS}
    return out


def draw_orders(pool_cells, m, draws, seed):
    """One random order of the pool rows inside each cell per draw, from one Generator. All allocations read the same orders."""
    rng = np.random.default_rng(seed)
    where = [np.flatnonzero(pool_cells == h) for h in range(m)]
    return [[rng.permutation(w) for w in where] for _ in range(draws)]


def stratified_sample(orders, n_per_cell, pool_w, pool_cells, cell_share):
    """Row positions and weights of one draw. Within a cell the weights keep psfwt and add up to the cell's share."""
    idx = np.concatenate([orders[h][: n_per_cell[h]] for h in range(len(orders))])
    w = pool_w[idx].astype(float).copy()
    cells = pool_cells[idx]
    totals = np.bincount(cells, weights=w, minlength=len(orders))
    scale = np.where(totals > 0, cell_share / np.where(totals > 0, totals, 1.0), 0.0)
    return idx, w * scale[cells]


def national(cell_share, values):
    return float(np.sum(cell_share * values) / np.sum(cell_share))


def allocation_study(ctx, allocations, cell_share, draws, seed):
    """Per draw errors, keyed allocation -> estimator -> truth -> metric -> item -> array over draws."""
    pool, m = ctx["pool"], ctx["m"]
    orders = draw_orders(pool["cells"], m, draws, seed)
    truths = {
        "panel_excluded": ctx["truth_outside_panel"],
        "whole_test": ctx["truth"],
        "pool_own": {t: cal.cell_mean(pool["y"][t], pool["w"], pool["cells"], m) for t in ITEMS},
    }
    store = {}
    for name, by_item in allocations.items():
        for t in ITEMS:
            for orders_r in orders:
                idx, w = stratified_sample(orders_r, by_item[t], pool["w"], pool["cells"], cell_share)
                cells = pool["cells"][idx]
                y = pool["y"][t][idx]
                direct, shrunk = cal.direct_and_shrunk(y, w, cells, m)
                r1 = cal.age_sex_model_cells(y, w, cells, ctx["cell_age"], ctx["cell_sex"])
                for est, value in (("direct", direct), ("shrink", shrunk), ("R1", r1)):
                    for truth_name, truth in truths.items():
                        slot = store.setdefault(name, {}).setdefault(est, {}).setdefault(truth_name, {"cell_mae": {}, "national_error": {}})
                        slot["cell_mae"].setdefault(t, []).append(cal.cell_mae(value, truth[t]))
                        slot["national_error"].setdefault(t, []).append(100.0 * abs(national(cell_share, value) - national(cell_share, truth[t])))
    return store


def with_average(by_item):
    arrays = {t: np.asarray(v, dtype=float) for t, v in by_item.items()}
    arrays[AVERAGE] = np.mean([arrays[t] for t in ITEMS], axis=0)
    return arrays


def summarise_allocation(store, allocations, caps, draws):
    """Means and paired differences, against proportional and between the two Neyman allocations."""
    out = {"allocations": {}, "caps": [int(c) for c in caps], "estimators": {}}
    for name, by_item in allocations.items():
        out["allocations"][name] = {t: [int(x) for x in by_item[t]] for t in ITEMS} if name in BY_ITEM_ALLOCATIONS else [int(x) for x in by_item[ITEMS[0]]]
    for est in ("direct", "shrink", "R1"):
        out["estimators"][est] = {}
        for truth in ("panel_excluded", "whole_test", "pool_own"):
            block = {}
            for metric in ("cell_mae", "national_error"):
                arrays = {name: with_average(store[name][est][truth][metric]) for name in allocations}
                block[metric] = {
                    "mean": {name: {t: round(float(a.mean()), 3) for t, a in arr.items()} for name, arr in arrays.items()},
                    "minus_proportional": {name: {t: cal.difference_summary(arr[t], arrays["proportional"][t]) for t in arr} for name, arr in arrays.items() if name != "proportional"},
                    "panel_minus_reference": {t: cal.difference_summary(arrays["panel_neyman"][t], arrays["reference_neyman"][t]) for t in arrays["panel_neyman"]},
                }
            out["estimators"][est][truth] = block
    r = out["estimators"]["R1"]["panel_excluded"]["cell_mae"]
    panel = r["minus_proportional"]["panel_neyman"][AVERAGE]
    ref = r["panel_minus_reference"][AVERAGE]
    out["reading"] = {
        "panel_helps_over_proportional": bool(panel["ci95"][1] < 0),
        "panel_adds_over_reference": bool(ref["ci95"][1] < 0),
        "panel_minus_proportional_r1_average": panel,
        "panel_minus_reference_r1_average": ref,
    }
    return out


# ---------- A2 flags ----------


def spearman(a, b):
    """Spearman over the finite pairs, None when fewer than 3 or no spread."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return None
    ra, rb = stats.rankdata(a[ok]), stats.rankdata(b[ok])
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def within_item_spearman(signal, error, m):
    """Mean of Spearman values inside each item block. Arrays are items times m long, item first."""
    vals = []
    for i in range(len(signal) // m):
        s = spearman(signal[i * m : (i + 1) * m], error[i * m : (i + 1) * m])
        if s is not None:
            vals.append(s)
    return float(np.mean(vals)) if vals else None


def top_k(values, k):
    """Positions of the k largest finite values, ties to the lower position."""
    values = np.asarray(values, dtype=float)
    ok = np.flatnonzero(np.isfinite(values))
    order = sorted(ok.tolist(), key=lambda i: (-values[i], i))
    return set(order[:k])


def overlap_stats(signal, error, k, perms, seed):
    """Observed overlap of the top k lists and the random expectation over usable units."""
    signal, error = np.asarray(signal, dtype=float), np.asarray(error, dtype=float)
    usable = np.flatnonzero(np.isfinite(signal) & np.isfinite(error))
    sig, err = signal[usable], error[usable]
    observed = len(top_k(sig, k) & top_k(err, k))
    worst = top_k(err, k)
    mask = np.zeros(len(usable), dtype=bool)
    mask[list(worst)] = True
    rng = np.random.default_rng(seed)
    counts = np.zeros(perms, dtype=int)
    for j in range(perms):
        counts[j] = int(mask[rng.permutation(len(usable))[:k]].sum())
    return {
        "usable_units": int(len(usable)),
        "k": k,
        "observed": observed,
        "random_mean": round(float(counts.mean()), 3),
        "random_95": [int(x) for x in np.percentile(counts, [2.5, 97.5])],
        "p_one_sided": round(float((1 + np.sum(counts >= observed)) / (perms + 1)), 5),
    }


class UnitGrid:
    """Per unit and per cell sums, so that a resample of survey units is one matrix product."""

    def __init__(self, units, unit_index, cells, m):
        self.index = np.array([unit_index[u] for u in np.asarray(units).tolist()])
        self.cells = np.asarray(cells)
        self.u = len(unit_index)
        self.m = m

    def sums(self, values):
        grid = np.zeros((self.u, self.m))
        np.add.at(grid, (self.index, self.cells), values)
        return grid


def ratio(num, den):
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def flag_study(ctx, answers, stability, stability_positions, plan, draws):
    """Errors and signals on 36 units, and their relation with a survey unit bootstrap. answers holds terra_C2, terra_C1, luna_C2 sets."""
    items, m = list(ctx["items"]), ctx["m"]
    panel, test, pool = ctx["panel"], ctx["test"], ctx["pool"]
    keep_out = verdict_study.outside_mask(ctx)
    uniq = np.unique(test["units"])
    unit_index = {u: i for i, u in enumerate(uniq.tolist())}
    panel_grid = UnitGrid(panel["units"], unit_index, panel["cells"], m)
    outside_grid = UnitGrid(test["units"][keep_out], unit_index, test["cells"][keep_out], m)
    whole_grid = UnitGrid(test["units"], unit_index, test["cells"], m)
    stab_grid = UnitGrid(panel["units"][stability_positions], unit_index, panel["cells"][stability_positions], m)
    w_panel = panel["w"]
    panel_den = panel_grid.sums(w_panel)
    outside_den = outside_grid.sums(test["w"][keep_out])
    whole_den = whole_grid.sums(test["w"])
    stab_den = stab_grid.sums(np.ones(len(stability_positions)))

    def panel_num(sets, t):
        return panel_grid.sums(w_panel * cal.clip(sets["test"][t]))

    terra2, terra1, luna2 = answers["terra_C2"], answers["terra_C1"], answers["luna_C2"]
    nums = {t: {"terra2": panel_num(terra2, t), "terra1": panel_num(terra1, t), "luna2": panel_num(luna2, t)} for t in items}
    sd = {t: stab_grid.sums(100.0 * stability[t].std(axis=1, ddof=1)) for t in items}
    truth_out = {t: outside_grid.sums(test["w"][keep_out] * test["y"][t][keep_out]) for t in items}
    truth_whole = {t: whole_grid.sums(test["w"] * test["y"][t]) for t in items}
    # One offset per draw and item, from the n=200 pool draw. The pool is not resampled.
    offsets = {t: [] for t in items}
    e4_num = {t: [] for t in items}
    for idx, wts in draws:
        for t in items:
            d = cal.fit_offset(terra2["calibration"][t][idx], pool["y"][t][idx], wts)
            offsets[t].append(float(d))
            e4_num[t].append(panel_grid.sums(w_panel * cal.expit(cal.logit(terra2["test"][t]) + d)))

    def assemble(counts):
        """(errors on the outside truth, errors on the whole truth, signals) for one resample as counts per unit, item first."""
        cnt = counts[None, :]
        pd_ = (cnt @ panel_den)[0]
        od, wd = (cnt @ outside_den)[0], (cnt @ whole_den)[0]
        sdn = (cnt @ stab_den)[0]
        err_out, err_whole, s_tl, s_c, s_sd, s_lvl = [], [], [], [], [], []
        for t in items:
            to = ratio((cnt @ truth_out[t])[0], od)
            tw = ratio((cnt @ truth_whole[t])[0], wd)
            eo, ew = np.zeros(m), np.zeros(m)
            for num in e4_num[t]:
                est = ratio((cnt @ num)[0], pd_)
                eo += np.abs(est - to)
                ew += np.abs(est - tw)
            err_out.append(100.0 * eo / len(e4_num[t]))
            err_whole.append(100.0 * ew / len(e4_num[t]))
            t2 = ratio((cnt @ nums[t]["terra2"])[0], pd_)
            t1 = ratio((cnt @ nums[t]["terra1"])[0], pd_)
            l2 = ratio((cnt @ nums[t]["luna2"])[0], pd_)
            s_tl.append(100.0 * np.abs(t2 - l2))
            s_c.append(100.0 * np.abs(t1 - t2))
            s_sd.append(ratio((cnt @ sd[t])[0], sdn))
            s_lvl.append(100.0 * np.sqrt(np.clip(t2, 0, 1) * (1 - np.clip(t2, 0, 1))))
        return (np.concatenate(err_out), np.concatenate(err_whole), {"terra_minus_luna": np.concatenate(s_tl), "c1_minus_c2": np.concatenate(s_c), "repeat_sd": np.concatenate(s_sd), "panel_level": np.concatenate(s_lvl)})

    base = np.ones(len(uniq))
    err, err_whole, signals = assemble(base)
    rng = np.random.default_rng(plan["seed"])
    picks = rng.integers(0, len(uniq), size=(plan["bootstrap"], len(uniq)))
    names = list(signals)
    boots = {n: {"spearman": [], "within": [], "minus_level": []} for n in names}
    for r in range(plan["bootstrap"]):
        counts = np.bincount(picks[r], minlength=len(uniq)).astype(float)
        e, _, sig = assemble(counts)
        level = spearman(sig["panel_level"], e)
        for n in names:
            s = spearman(sig[n], e)
            boots[n]["spearman"].append(np.nan if s is None else s)
            wi = within_item_spearman(sig[n], e, m)
            boots[n]["within"].append(np.nan if wi is None else wi)
            boots[n]["minus_level"].append(np.nan if (s is None or level is None) else s - level)

    def ci(values):
        v = np.asarray(values, dtype=float)
        v = v[np.isfinite(v)]
        lo, hi = np.percentile(v, [2.5, 97.5])
        return {"ci95": [round(float(lo), 3), round(float(hi), 3)], "resamples_used": int(len(v))}

    out = {"bootstrap": plan["bootstrap"], "permutations": plan["permutations"], "units_per_item": m, "signals": {}, "error": {t: {"mean_pp": round(float(err[i * m : (i + 1) * m].mean()), 3), "max_pp": round(float(err[i * m : (i + 1) * m].max()), 3)} for i, t in enumerate(items)}}
    for n in names:
        sig = signals[n]
        sp = spearman(sig, err)
        wi = within_item_spearman(sig, err, m)
        out["signals"][n] = {
            "usable_units": int(np.isfinite(sig).sum()),
            "spearman": round(sp, 3),
            "spearman_ci": ci(boots[n]["spearman"]),
            "within_item_spearman": None if wi is None else round(wi, 3),
            "within_item_ci": ci(boots[n]["within"]),
            "overlap_top9": overlap_stats(sig, err, plan["top_k"], plan["permutations"], plan["seed"]),
            "whole_test_truth": {"spearman": round(spearman(sig, err_whole), 3), "overlap_top9": overlap_stats(sig, err_whole, plan["top_k"], plan["permutations"], plan["seed"])},
        }
        if n != "panel_level":
            out["signals"][n]["minus_level_ci"] = ci(boots[n]["minus_level"])
        d = out["signals"][n]
        d["names_wrong_cells"] = None if n == "panel_level" else bool(d["spearman_ci"]["ci95"][0] > 0 and d["overlap_top9"]["p_one_sided"] < 0.05 and d["within_item_ci"]["ci95"][0] > 0 and d["minus_level_ci"]["ci95"][0] > 0)
    return out


# ---------- A3 duel validity ----------


def draw_truth_mae(ctx, sets, y_s, wts, p_s, cells_s, item):
    """(E4 cell MAE, R1 cell MAE) on both truths for one draw and item, both fit on all n."""
    panel, m = ctx["panel"], ctx["m"]
    d = cal.fit_offset(p_s, y_s, wts)
    e4 = cal.offset_estimate(d, sets["test"][item], panel["w"], panel["cells"], m)
    r1 = cal.age_sex_model_cells(y_s, wts, cells_s, ctx["cell_age"], ctx["cell_sex"])
    return {
        "panel_excluded": (cal.cell_mae(e4, ctx["truth_outside_panel"][item]), cal.cell_mae(r1, ctx["truth_outside_panel"][item])),
        "whole_test": (cal.cell_mae(e4, ctx["truth"][item]), cal.cell_mae(r1, ctx["truth"][item])),
    }


def duel_study(ctx, slots, draws, seed_base):
    """Per draw decisions and truth checks. slots maps a name to answer sets {test: {item}, calibration: {item}}."""
    items = list(ctx["items"])
    pool = ctx["pool"]
    n_draws = len(draws)
    raw = {s: {"pooled": {"keep": np.zeros(n_draws, dtype=bool), "beats": {"panel_excluded": np.zeros(n_draws, dtype=bool), "whole_test": np.zeros(n_draws, dtype=bool)}, "improvement": np.zeros(n_draws)}, **{t: {"keep": np.zeros(n_draws, dtype=bool), "beats": {"panel_excluded": np.zeros(n_draws, dtype=bool), "whole_test": np.zeros(n_draws, dtype=bool)}, "improvement": np.zeros(n_draws)} for t in items}} for s in slots}
    for r, (idx, wts) in enumerate(draws):
        cells_s = pool["cells"][idx]
        fold = duel.folds_by_cell(cells_s, duel.FOLDS, np.random.default_rng([*seed_base, r]))
        y_by_item = {t: pool["y"][t][idx] for t in items}
        r1_losses = {t: duel.r1_fold_losses(y_by_item[t], wts, cells_s, ctx["cell_age"], ctx["cell_sex"], fold) for t in items}
        for name, sets in slots.items():
            improvements = {}
            maes = {}
            for t in items:
                p_s = sets["calibration"][t][idx]
                improvements[t] = r1_losses[t] - duel.panel_fold_losses(y_by_item[t], wts, p_s, fold)
                dec = duel.decide(improvements[t])
                maes[t] = draw_truth_mae(ctx, sets, y_by_item[t], wts, p_s, cells_s, t)
                slot = raw[name][t]
                slot["keep"][r] = dec["keep"]
                slot["improvement"][r] = dec["mean_improvement"]
                for truth in ("panel_excluded", "whole_test"):
                    slot["beats"][truth][r] = maes[t][truth][0] < maes[t][truth][1]
            dec = duel.decide(np.mean([improvements[t] for t in items], axis=0))
            slot = raw[name]["pooled"]
            slot["keep"][r] = dec["keep"]
            slot["improvement"][r] = dec["mean_improvement"]
            for truth in ("panel_excluded", "whole_test"):
                slot["beats"][truth][r] = float(np.mean([maes[t][truth][0] for t in items])) < float(np.mean([maes[t][truth][1] for t in items]))
    return raw


def rates(keep, beats, reps, seed):
    """Counts and rates of one panel, one unit of decision, one truth."""
    n = len(keep)
    kept = int(keep.sum())
    beat = int(beats.sum())
    kb = int((keep & beats).sum())
    kn = int((keep & ~beats).sum())
    db = int((~keep & beats).sum())
    dn = int((~keep & ~beats).sum())
    picks = np.random.default_rng(seed).integers(0, n, size=(reps, n))
    boot = keep[picks].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])

    def share(a, b):
        return None if b == 0 else round(a / b, 4)

    return {
        "draws": n,
        "keep_rate": round(kept / n, 4),
        "keep_rate_ci95": [round(float(lo), 4), round(float(hi), 4)],
        "beats_rate": round(beat / n, 4),
        "counts": {"kept_and_beats": kb, "kept_not_beats": kn, "dropped_and_beats": db, "dropped_not_beats": dn},
        "false_keep_rate": share(kn, kept),
        "false_keep_over_not_beating": share(kn, n - beat),
        "false_keep_over_all_draws": share(kn, n),
        "missed_keep_rate": share(db, beat),
        "missed_keep_over_all_draws": share(db, n),
    }


def summarise_duel(raw, items, reps, seed):
    out = {}
    for name, blocks in raw.items():
        out[name] = {}
        for unit, slot in blocks.items():
            out[name][unit] = {
                "mean_improvement": round(float(slot["improvement"].mean()), 5),
                **{truth: rates(slot["keep"], slot["beats"][truth], reps, seed) for truth in ("panel_excluded", "whole_test")},
            }
    return out


def acceptance(raw, bar, positive, surrogates, reps, seed):
    """The bar stated in advance, on the pooled decision of the row draws."""
    keep = {s: raw[s]["pooled"]["keep"] for s in [positive, *surrogates]}
    surrogate_rates = {s: float(keep[s].mean()) for s in surrogates}
    worst = max(surrogates, key=lambda s: surrogate_rates[s])
    pos = float(keep[positive].mean())
    n = len(keep[positive])
    picks = np.random.default_rng(seed).integers(0, n, size=(reps, n))
    diff = keep[positive][picks].mean(axis=1) - keep[worst][picks].mean(axis=1)
    lo, hi = np.percentile(diff, [2.5, 97.5])
    surrogate_ok = all(v <= bar["surrogate_max_keep"] for v in surrogate_rates.values())
    positive_ok = (pos - surrogate_rates[worst]) >= bar["positive_min_margin"] and lo > 0
    passed = bool(surrogate_ok and positive_ok)
    return {
        "bar": bar,
        "positive_control": positive,
        "positive_keep_rate": round(pos, 4),
        "surrogate_keep_rates": {k: round(v, 4) for k, v in surrogate_rates.items()},
        "margin": round(pos - surrogate_rates[worst], 4),
        "margin_ci95": [round(float(lo), 4), round(float(hi), 4)],
        "surrogate_bar_met": bool(surrogate_ok),
        "positive_bar_met": bool(positive_ok),
        "passed": passed,
        "label": "decision_rule" if passed else "health_check",
    }
