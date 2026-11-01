"""No-truth diagnostics of one concept run. Pure functions on arrays, no I/O, no randomness outside the fixed seed.

Answers arrive as an array per card, one row per persona in a fixed order, columns p1 to p5, NaN where a call gave no valid
answer. A missing answer stays missing: it is never filled, and missing rates are reported per card and segment.

Every comparison is paired by persona. Intervals come from one bootstrap of survey units, shared by all comparisons in a call.
All values are panel internal. None of them is a market number.
"""
import numpy as np

CANDIDATE = "candidate"
PARAPHRASE = "paraphrase"
BRAND = "brand"
NEGATIVE = "negative_control"


def t2b_pp(answers):
    """100 x (p4 + p5) per row after normalising the five values. NaN stays NaN."""
    a = np.asarray(answers, dtype=float)
    total = a.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100.0 * (a[:, 3] + a[:, 4]) / total


def mean_score(answers):
    a = np.asarray(answers, dtype=float)
    total = a.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (a * np.arange(1, 6)).sum(axis=1) / total


def unit_weights(units, draws, seed):
    """(inverse index, draws by units matrix of resampled unit counts)."""
    uniq, inv = np.unique(np.asarray(units), return_inverse=True)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(uniq), size=(draws, len(uniq)))
    weights = np.zeros((draws, len(uniq)))
    for i in range(draws):
        weights[i] = np.bincount(picks[i], minlength=len(uniq))
    return inv, weights


def boot_means(values, inv, weights):
    """Mean of values over each resample, skipping NaN pairs. Empty resamples give NaN."""
    v = np.asarray(values, dtype=float)
    ok = ~np.isnan(v)
    m = weights.shape[1]
    sums = np.bincount(inv[ok], weights=v[ok], minlength=m)
    counts = np.bincount(inv[ok], minlength=m)
    den = weights @ counts
    with np.errstate(invalid="ignore", divide="ignore"):
        return (weights @ sums) / den


def summary(values, inv, weights):
    """Mean with the percentile 95 interval, or Nones when nothing is valid."""
    v = np.asarray(values, dtype=float)
    ok = ~np.isnan(v)
    n = int(ok.sum())
    if n == 0:
        return {"mean": None, "ci95": [None, None], "n": 0}
    boots = boot_means(v, inv, weights)
    boots = boots[~np.isnan(boots)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"mean": round(float(v[ok].mean()), 3), "ci95": [round(float(lo), 3), round(float(hi), 3)], "n": n}


def noise_upper(comparison):
    """The larger absolute limit of the interval of a difference between two wordings of one concept."""
    lo, hi = comparison["ci95"]
    return None if lo is None else round(max(abs(lo), abs(hi)), 3)


def excludes_zero(comparison):
    lo, hi = comparison["ci95"]
    return lo is not None and (lo > 0 or hi < 0)


def exceeds_noise(comparison, noise):
    """Mean beyond the noise and interval away from zero. No noise estimate means nothing can exceed it."""
    if comparison["mean"] is None or noise is None:
        return False
    return bool(abs(comparison["mean"]) > noise and excludes_zero(comparison))


def separated(comparison, noise):
    """Candidate minus negative control is above the noise and wholly above zero."""
    if comparison["mean"] is None or noise is None:
        return False
    return bool(comparison["mean"] > noise and comparison["ci95"][0] > 0)


def missing_rates(answers_by_card, masks):
    out = {}
    for card, a in answers_by_card.items():
        missing = np.isnan(np.asarray(a, dtype=float)).any(axis=1)
        out[card] = {"overall": round(float(missing.mean()), 4), **{s: round(float(missing[m].mean()), 4) for s, m in masks.items() if m.any()}}
    return out


def pair_key(a, b):
    return f"{a}|{b}"


def model_diagnostics(answers_by_card, units, segments, roles, rules):
    """All diagnostics of one model. segments is one label per persona."""
    boot = rules["bootstrap"]
    units = np.asarray(units)
    segments = np.asarray(segments)
    t2b = {c: t2b_pp(a) for c, a in answers_by_card.items()}
    score = {c: mean_score(a) for c, a in answers_by_card.items()}
    candidates = [c for c, r in roles.items() if r["role"] == CANDIDATE and c in t2b]
    negative = next((c for c, r in roles.items() if r["role"] == NEGATIVE and c in t2b), None)
    paraphrase = next((c for c, r in roles.items() if r["role"] == PARAPHRASE and c in t2b), None)
    brand = next((c for c, r in roles.items() if r["role"] == BRAND and c in t2b), None)
    inv, weights = unit_weights(units, boot["draws"], boot["seed"])

    def diff(a, b, mask=None, use_inv=inv, use_w=weights):
        d = t2b[a] - t2b[b]
        if mask is not None:
            d = d[mask]
        return summary(d, use_inv, use_w)

    noise = None
    noise_doc = None
    if paraphrase:
        source = roles[paraphrase]["paraphrase_of"]
        noise_doc = diff(source, paraphrase)
        noise = noise_upper(noise_doc)
    internal = {c: {"t2b_pp": summary(t2b[c], inv, weights), "mean_score": round(float(np.nanmean(score[c])), 3) if np.any(~np.isnan(score[c])) else None} for c in t2b}
    gaps = {}
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            g = diff(a, b)
            gaps[pair_key(a, b)] = {**g, "distinguishable": exceeds_noise(g, noise)}
    rank = sorted(candidates, key=lambda c: -(internal[c]["t2b_pp"]["mean"] if internal[c]["t2b_pp"]["mean"] is not None else float("-inf")))
    neg = {}
    if negative:
        for c in candidates:
            g = diff(c, negative)
            neg[c] = {**g, "separated": separated(g, noise)}
    brand_doc = None
    if brand:
        source = roles[brand]["brand_of"]
        g = diff(brand, source)
        brand_doc = {**g, "exceeds_noise": exceeds_noise(g, noise), "source": source}

    seg_docs = {}
    masks = {}
    for seg in sorted(set(segments.tolist())):
        mask = segments == seg
        masks[seg] = mask
        n = int(mask.sum())
        doc = {"n": n}
        if n >= rules["min_segment_n"]:
            seg_inv, seg_w = unit_weights(units[mask], boot["draws"], boot["seed"])
            doc["determined"] = True
            doc["t2b_pp"] = {c: summary(t2b[c][mask], seg_inv, seg_w) for c in t2b}
            doc["negative"] = {}
            if negative:
                for c in candidates:
                    g = diff(c, negative, mask, seg_inv, seg_w)
                    doc["negative"][c] = {**g, "separated": separated(g, noise)}
            doc["gaps"] = {}
            for i, a in enumerate(candidates):
                for b in candidates[i + 1 :]:
                    g = diff(a, b, mask, seg_inv, seg_w)
                    doc["gaps"][pair_key(a, b)] = {**g, "distinguishable": exceeds_noise(g, noise)}
        else:
            doc["determined"] = False
        seg_docs[seg] = doc

    return {
        "n_personas": int(len(units)),
        "noise": noise_doc,
        "noise_upper": noise,
        "internal": internal,
        "gaps": gaps,
        "rank": rank,
        "negative": neg,
        "brand": brand_doc,
        "segments": seg_docs,
        "missing": missing_rates(answers_by_card, masks),
    }


def model_disagreement(by_model):
    """Candidate pairs whose paired difference has opposite signs in two models."""
    models = list(by_model)
    if len(models) < 2:
        return {"models": models, "pairs": [], "ranks": {m: by_model[m]["rank"] for m in models}, "flag": False}
    a, b = models[0], models[1]
    pairs = []
    for key, g in by_model[a]["gaps"].items():
        other = by_model[b]["gaps"].get(key)
        if other and g["mean"] is not None and other["mean"] is not None and g["mean"] * other["mean"] < 0:
            pairs.append(key)
    return {"models": [a, b], "pairs": pairs, "ranks": {m: by_model[m]["rank"] for m in models}, "flag": bool(pairs)}


def c0_compare(main_doc, c0_answers, roles, rules):
    """Does a call without any persona give the same order and the same gaps as the panel on the main model?"""
    boot = rules["bootstrap"]
    candidates = [c for c, r in roles.items() if r["role"] == CANDIDATE and c in c0_answers]
    values = {c: t2b_pp(a) for c, a in c0_answers.items()}
    internal = {}
    for c, v in values.items():
        inv, w = unit_weights(np.arange(len(v)), boot["draws"], boot["seed"])
        internal[c] = summary(v, inv, w)
    noise = main_doc["noise_upper"]
    pairs = {}
    within = True
    for key, g in main_doc["gaps"].items():
        a, b = key.split("|")
        if a not in values or b not in values or internal[a]["mean"] is None or internal[b]["mean"] is None:
            within = False
            continue
        c0_gap = round(internal[a]["mean"] - internal[b]["mean"], 3)
        delta = None if g["mean"] is None else round(g["mean"] - c0_gap, 3)
        ok = delta is not None and noise is not None and abs(delta) <= noise
        within = within and ok
        pairs[key] = {"c1_gap": g["mean"], "c0_gap": c0_gap, "c1_minus_c0": delta, "within_noise": ok}
    c0_rank = sorted(candidates, key=lambda c: -(internal[c]["mean"] if internal[c]["mean"] is not None else float("-inf")))
    c1_rank = [c for c in main_doc["rank"] if c in candidates]
    same_rank = c0_rank == c1_rank
    return {
        "calls_per_card": {c: int(np.sum(~np.isnan(v))) for c, v in values.items()},
        "c0_internal": internal,
        "c0_rank": c0_rank,
        "c1_rank": c1_rank,
        "same_rank": same_rank,
        "pairs": pairs,
        "flag_no_personal_information": bool(same_rank and within and pairs),
    }


def compute(answers, c0_answers, c0_model, units, segments, roles, rules):
    """answers is {model: {card: array}}, c0_answers is {card: array} for c0_model."""
    by_model = {m: model_diagnostics(a, units, segments, roles, rules) for m, a in answers.items()}
    c0_doc = c0_compare(by_model[c0_model], c0_answers, roles, rules) if c0_answers and c0_model in by_model else None
    return {
        "by_model": by_model,
        "model_disagreement": model_disagreement(by_model),
        "c0": c0_doc,
        "c0_model": c0_model,
        "note": "panel internal values, no truth, not market numbers",
    }


def pilot_gate(answers_candidate, answers_negative, units, rules):
    """The pilot's stop rule: the interval of candidate minus negative must lie wholly above zero."""
    boot = rules["bootstrap"]
    inv, w = unit_weights(units, boot["draws"], boot["seed"])
    g = summary(t2b_pp(answers_candidate) - t2b_pp(answers_negative), inv, w)
    return {**g, "passed": bool(g["mean"] is not None and g["ci95"][0] > 0)}
