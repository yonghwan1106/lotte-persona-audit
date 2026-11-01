"""The verdict table of a concept run. Deterministic. The LLM never reaches this file.

A base label per anchor item comes from rule v2 on the stored stage 2 aggregates. The run's own noise can only lower a cell,
hide a number or add a flag. No concept can reach the calibrated label before real answers exist, and v2 alone gives none.
"""
from .. import verdict_v2
from . import settings

LABEL_ORDER = {verdict_v2.REAL_ONLY: 0, verdict_v2.DIRECTION: 1, verdict_v2.CALIBRATED: 2}
OVERALL = "all"


def base_labels(stored_rows, model, condition, anchors):
    """Recompute v2 for each anchor item and return {item: result}. A stored label that does not reproduce is an error."""
    out = {}
    for row in stored_rows:
        if row["model"] != model or row["condition"] != condition or row["item"] not in anchors:
            continue
        inputs = row["v2_inputs"]
        result = verdict_v2.item_verdict(
            inputs["vs_r1_row"],
            inputs["vs_r1_cluster"],
            {},
            {},
            inputs["panel_age_slope"],
            inputs["real_age_slope_ci95"],
            inputs["cell_pearson_r"],
            inputs["underdispersion_ratio"],
            inputs["gap_minus_real_ci95"],
        )
        if result["verdict"] != row["v2"]["verdict"] or result["gender_gap_use_banned"] != row["v2"]["gender_gap_use_banned"]:
            raise RuntimeError(f"stored v2 row does not reproduce: {row['item']} {model} {condition}")
        out[row["item"]] = result
    missing = set(anchors) - set(out)
    if missing:
        raise RuntimeError(f"no stored v2 row for {sorted(missing)} on {model} {condition}")
    return out


def lowest_label(results):
    return min((r["verdict"] for r in results.values()), key=lambda v: LABEL_ORDER[v])


def card_base(stored_rows, model, condition, anchors):
    results = base_labels(stored_rows, model, condition, anchors)
    return {
        "label": lowest_label(results),
        "by_item": {item: r["verdict"] for item, r in results.items()},
        "gender_gap_banned": any(r["gender_gap_use_banned"] for r in results.values()),
        "estimators_beating_r1": sorted({e for r in results.values() for e in r["estimators_beating_r1"]}),
    }


def decide(diag, roles, stored_rows, condition, text):
    """The whole table: one row per candidate, model and segment, the pair sentences, and the metric catalog for the narrator."""
    labels = text["labels"]
    flags_text = text["verdict_text"]["flags"]
    vt = text["verdict_text"]
    candidates = [c for c, r in roles.items() if r["role"] == "candidate"]
    disagreement = diag["model_disagreement"]
    priority_cards = {c for key in disagreement["pairs"] for c in key.split("|")}
    no_personal = bool(diag["c0"] and diag["c0"]["flag_no_personal_information"])
    rows = []
    sentences = []
    for model, doc in diag["by_model"].items():
        short = settings.short_model(model)
        brand_hidden = bool(doc["brand"] and doc["brand"]["exceeds_noise"])
        sentences.append(vt["brand_hidden" if brand_hidden else "brand_ok"].format(model=short))
        indistinct_cards = set()
        for key, g in doc["gaps"].items():
            a, b = key.split("|")
            if not g["distinguishable"]:
                indistinct_cards.update([a, b])
                sentences.append(vt["indistinct_pair"].format(model=short, a=a, b=b))
            else:
                sentences.append(vt["distinct_pair"].format(model=short, a=a, b=b))
        for card in candidates:
            base = card_base(stored_rows, model, condition, roles[card]["anchor_items"])
            for segment in [OVERALL, *sorted(doc["segments"])]:
                seg_doc = doc["segments"].get(segment)
                n = doc["n_personas"] if segment == OVERALL else seg_doc["n"]
                determined = True if segment == OVERALL else seg_doc["determined"]
                flags = []
                if determined:
                    neg = doc["negative"].get(card) if segment == OVERALL else seg_doc["negative"].get(card)
                    separated = bool(neg and neg["separated"])
                    status = labels["valid"] if separated else labels["invalid"]
                    pair_source = doc["gaps"] if segment == OVERALL else seg_doc["gaps"]
                    pair_indistinct = any(card in key.split("|") and not g["distinguishable"] for key, g in pair_source.items())
                else:
                    separated = False
                    status = labels["undetermined"]
                    pair_indistinct = False
                    flags.append(flags_text["small_n"])
                if determined and not separated:
                    flags.append(flags_text["invalid"])
                    if segment == OVERALL:
                        sentences.append(vt["neg_fail"].format(model=short, card=card))
                # An invalid or undetermined cell goes to real measurement whatever its base label is.
                label = base["label"] if separated else verdict_v2.REAL_ONLY
                if pair_indistinct:
                    flags.append(flags_text["indistinct"])
                if brand_hidden:
                    flags.append(flags_text["hide_absolute"])
                if card in priority_cards:
                    flags.append(flags_text["real_priority"])
                if no_personal:
                    flags.append(flags_text["no_personal"])
                if base["gender_gap_banned"]:
                    flags.append(verdict_v2.GENDER_GAP_BAN)
                numbers_shown = label != verdict_v2.REAL_ONLY and not brand_hidden
                order_allowed = label == verdict_v2.DIRECTION
                rows.append(
                    {
                        "card": card,
                        "model": model,
                        "segment": segment,
                        "n": n,
                        "base_label_v2": base["label"],
                        "base_by_item": base["by_item"],
                        "run_status": status,
                        "label": label,
                        "flags": flags,
                        "absolute_shown": numbers_shown,
                        "order_allowed": order_allowed,
                        "distinct_from": [k for k, g in (doc["gaps"] if segment == OVERALL else (seg_doc["gaps"] if determined else {})).items() if card in k.split("|") and g["distinguishable"]],
                    }
                )
                if segment == OVERALL:
                    sentences.append(vt["overall"].format(card=card, model=short, segment=OVERALL, label=label))
    _limit_order_to_comparable(rows)
    for key in disagreement["pairs"]:
        a, b = key.split("|")
        sentences.append(vt["disagree"].format(a=a, b=b))
    if diag["c0"]:
        sentences.append(vt["no_personal" if no_personal else "personal_differs"])
    return {
        "rule_version": "agent-1 on v2",
        "header": vt["header"],
        "rows": rows,
        "sentences": sentences,
        "any_order_allowed": any(r["order_allowed"] and r["segment"] == OVERALL for r in rows),
        "raw_panel_number_as_market_number": False,
    }


def _limit_order_to_comparable(rows):
    """An order needs two cells that may both be ordered. A lone direction cell has nothing to be ordered against."""
    direction = {(r["model"], r["segment"], r["card"]) for r in rows if r["label"] == verdict_v2.DIRECTION}
    for r in rows:
        others = [k for k in r.pop("distinct_from") for c in k.split("|") if c != r["card"] and (r["model"], r["segment"], c) in direction]
        r["order_allowed"] = bool(r["order_allowed"] and others)


def fmt_pp(value):
    return f"{value:+.1f}pp"


def fmt_comparison(c):
    return f"{c['mean']:+.1f}pp [{c['ci95'][0]:+.1f}, {c['ci95'][1]:+.1f}]"


def metric_catalog(diag, verdict, text):
    """{metric id: {value, what}} for the renderer. Hidden values are simply not in the catalog, so nobody can cite them."""
    out = {}
    shown = {(r["card"], r["model"]): r["absolute_shown"] for r in verdict["rows"] if r["segment"] == OVERALL}
    usable = {(r["card"], r["model"]) for r in verdict["rows"] if r["segment"] == OVERALL and r["label"] != verdict_v2.REAL_ONLY}
    for model, doc in diag["by_model"].items():
        short = settings.short_model(model)
        if doc["noise"] and doc["noise"]["mean"] is not None:
            out[f"noise_{short}"] = {"value": fmt_comparison(doc["noise"]), "what": f"{short}: A minus its paraphrase, the noise of this run"}
            out[f"noise_upper_{short}"] = {"value": f"{doc['noise_upper']:.1f}pp", "what": f"{short}: noise limit used by the rules"}
        for key, g in doc["gaps"].items():
            if g["mean"] is None:
                continue
            a, b = key.split("|")
            if (a, model) not in usable or (b, model) not in usable:
                continue  # a real-only cell's number stays out of the narration
            out[f"gap_{a}_{b}_{short}"] = {"value": fmt_comparison(g), "what": f"{short}: candidate {a} minus {b}, panel internal"}
        for card, g in doc["negative"].items():
            if g["mean"] is not None and (card, model) in usable:
                out[f"negative_{card}_{short}"] = {"value": fmt_comparison(g), "what": f"{short}: candidate {card} minus the negative control"}
        if doc["brand"] and doc["brand"]["mean"] is not None:
            out[f"brand_{short}"] = {"value": fmt_comparison(doc["brand"]), "what": f"{short}: brand card minus the same text without the brand"}
        for card, values in doc["internal"].items():
            if shown.get((card, model)) and values["t2b_pp"]["mean"] is not None:
                out[f"internal_{card}_{short}"] = {"value": f"{values['t2b_pp']['mean']:.1f}pp", "what": f"{short}: panel internal top two box of {card}, not a market number"}
    if diag["c0"]:
        for key, p in diag["c0"]["pairs"].items():
            if p["c1_minus_c0"] is None:
                continue
            a, b = key.split("|")
            out[f"personagap_{a}_{b}"] = {"value": fmt_pp(p["c1_minus_c0"]), "what": f"{a} minus {b}: panel gap minus the gap without any persona"}
    return out
