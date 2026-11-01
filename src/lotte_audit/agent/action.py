"""The action table in manager language and the detectable difference arithmetic. Pure functions, all values from code.

Rules are in config/prereg_stage4.json, block B_rules. The demo values were seen when they were written, and the demo has no truth to score them.
"""
import json
import math
from statistics import NormalDist

from .. import paths

CANDIDATE = "candidate"
DROP, KEEP, CANT_TELL = "drop", "keep", "cant_tell"
BANDS = ((1.0, "under_1pp", "1pp \ubbf8\ub9cc"), (3.0, "1_to_3pp", "1~3pp"), (5.0, "3_to_5pp", "3~5pp"), (float("inf"), "5pp_and_over", "5pp \uc774\uc0c1"))
SENSITIVITY_LIMITS = (5.0, 4.5, 4.0, 3.0, 2.0)
JOINED_BANDS = ("1_to_3pp", "3_to_5pp")
RANKING_SOURCE = "results/stage3/option_ranking.json"


def load_rules():
    return json.loads((paths.CONFIG / "prereg_stage4.json").read_text(encoding="utf-8"))["B_rules"]


def load_text():
    return json.loads((paths.CONFIG / "stage4_text.json").read_text(encoding="utf-8"))


def gap(block, a, b):
    """(a minus b in pp, distinguishable) from the pair table, whichever way the pair was stored."""
    g = block["gaps"].get(f"{a}|{b}")
    if g is not None:
        return g["mean"], g["distinguishable"]
    g = block["gaps"][f"{b}|{a}"]
    return (None if g["mean"] is None else -g["mean"]), g["distinguishable"]


def short(model):
    return model.rsplit("-", 1)[-1]


def _gaps_text(pairs):
    return ", ".join(f"{short(m)} {abs(v):.1f}pp" for m, v in pairs)


def decide_card(card, candidates, diagnostics, limit, run_complete, leading_kept, text):
    """(label, reason sentence) for one candidate. Order of the checks is the rule."""
    t = text["action"]["reasons"]
    by_model = diagnostics["by_model"]
    models = list(by_model)
    if not run_complete:
        return CANT_TELL, t["run_incomplete"]
    for m in models:
        if by_model[m]["negative"] and not any(by_model[m]["negative"][c]["separated"] for c in candidates):
            return CANT_TELL, t["run_cannot_separate"].format(model=short(m))
    if card in leading_kept:
        return CANT_TELL, t["leading_kept"]
    # Every model's top candidate is a reference, so the answer does not depend on which model is listed first.
    for reference in sorted({by_model[m]["rank"][0] for m in models}):
        if card == reference or len(models) < 2:
            continue
        pairs = [(m, *gap(by_model[m], card, reference)) for m in models]
        beyond = [abs(v) > by_model[m]["noise_upper"] for m, v, _ in pairs if v is not None and by_model[m]["noise_upper"] is not None]
        signs = {v > 0 for _, v, _ in pairs if v is not None}
        if len(signs) > 1 and len(beyond) == len(pairs) and all(beyond):
            return CANT_TELL, t["models_oppose"].format(reference=reference, gaps=_gaps_text([(m, v) for m, v, _ in pairs]))
    has_negative = all(by_model[m]["negative"] for m in models)
    if has_negative and all(not by_model[m]["negative"][card]["separated"] for m in models):
        if any(by_model[m]["negative"][c]["separated"] for m in models for c in candidates if c != card):
            return DROP, t["drop_negative"]
    tops = {m: by_model[m]["rank"][0] for m in models}
    below = {m: (0.0, False) if tops[m] == card else gap(by_model[m], tops[m], card) for m in models}
    if all(tops[m] != card and below[m][0] is not None and below[m][0] >= limit and below[m][1] for m in models):
        return DROP, t["drop_gap"].format(gaps=_gaps_text([(m, below[m][0]) for m in models]), limit=f"{limit:g}")
    if all(tops[m] == card for m in models):
        return KEEP, t["keep_top"]
    return KEEP, t["keep_gap"].format(gaps=_gaps_text([(m, below[m][0]) for m in models if tops[m] != card]), limit=f"{limit:g}")


def ranking_accuracy(band_key):
    """(pair accuracy, its interval, pairs in the band) of the concept condition's panel on existing drinks, for the band of the panel's own gap."""
    doc = json.loads((paths.ROOT / RANKING_SOURCE).read_text(encoding="utf-8"))
    panel = doc["sets"]["merged_coffee_15"]["groups"]["overall"]["estimators"]["panel_C1"]
    e = panel[f"estimated_gap|{band_key}|accuracy"]
    return e["value"], e.get("ci95"), panel[f"estimated_gap|{band_key}|n_pairs"]["value"]


def pair_counts(value, n):
    """Pairs right out of pairs in the band. The stored accuracy is that share, rounded."""
    return round(value * n), n


def threshold_sensitivity(card_ids, diagnostics, run_complete, leading_kept, text, limits=SENSITIVITY_LIMITS):
    """The labels of this run with the drop gap at other values. Same rule, same diagnostics, nothing fitted. The limit in force is one of the rows."""
    rows = []
    for limit in limits:
        drops = [c for c in card_ids if decide_card(c, card_ids, diagnostics, limit, run_complete, leading_kept, text)[0] == DROP]
        rows.append({"limit_pp": limit, "drop_proposed": drops})
    return rows


def sensitivity_line(rows, text):
    """Limits that give the same result are named together, so the sentence is the code's reading of the rows."""
    t = text["action"]
    groups = []
    for row in rows:
        if groups and groups[-1][1] == row["drop_proposed"]:
            groups[-1][0].append(row["limit_pp"])
        else:
            groups.append(([row["limit_pp"]], row["drop_proposed"]))
    parts = []
    for limits, drops in groups:
        names = ", ".join(f"{x:g}pp" for x in limits)
        parts.append(t["sensitivity_keep_all"].format(limits=names) if not drops else t["sensitivity_drop"].format(limits=names, cards=", ".join(drops)))
    return t["sensitivity"].format(parts="; ".join(parts))


def band_of(value):
    for top, key, label in BANDS:
        if abs(value) < top:
            return key, label
    raise ValueError(value)


def order_lines(candidates, diagnostics, text, accuracy=ranking_accuracy):
    """An order appears only when the gap exceeds noise and keeps its sign in both models, and it is marked a hypothesis."""
    t = text["action"]
    by_model = diagnostics["by_model"]
    models = list(by_model)
    shown, hidden = [], []
    joined = [accuracy(k) for k in JOINED_BANDS]
    right = sum(pair_counts(v, n)[0] for v, _, n in joined)
    pairs_total = sum(n for _, _, n in joined)
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            pairs = [(m, *gap(by_model[m], a, b)) for m in models]
            signs = {v > 0 for _, v, _ in pairs if v is not None}
            if len(models) < 2 or len(signs) != 1 or not all(d for _, _, d in pairs):
                hidden.append(f"{a}, {b}")
                continue
            hi, lo = (a, b) if signs == {True} else (b, a)
            key, label = band_of(pairs[0][1])
            value, ci, n = accuracy(key)
            good, _ = pair_counts(value, n)
            shown.append(t["order_line"].format(hi=hi, lo=lo, gaps=_gaps_text([(m, v) for m, v, _ in pairs]), band=label, good=good, n=n, accuracy=f"{value:.3f}", ci=f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else ""))
    notes = [t["order_note"].format(right=right, total=pairs_total, source=RANKING_SOURCE)] if shown else []
    return {"lines": shown or [t["order_none"]], "hidden_pairs": hidden, "notes": notes}


def action_table(diagnostics, roles, run_complete, leading_log, rules, text, accuracy=ranking_accuracy):
    candidates = sorted(c for c, r in roles.items() if r["role"] == CANDIDATE)
    limit = rules["action_table"]["drop_gap_pp"]
    kept = {e["card_id"] for e in leading_log if e.get("decision") == "keep"}
    labels = text["action"]["labels"]
    rows = []
    for card in candidates:
        code, reason = decide_card(card, candidates, diagnostics, limit, run_complete, kept, text)
        rows.append({"card": card, "action": code, "label": labels[code], "reason": reason})
    order = order_lines(candidates, diagnostics, text, accuracy) if run_complete else {"lines": [text["action"]["order_none"]], "hidden_pairs": [], "notes": []}
    sensitivity = threshold_sensitivity(candidates, diagnostics, run_complete, kept, text)
    notes = [n.format(limit=f"{limit:g}") for n in text["action"]["notes"]] + [sensitivity_line(sensitivity, text)]
    return {"rows": rows, "order": order["lines"], "order_hidden_pairs": order["hidden_pairs"], "order_notes": order["notes"], "notes": notes, "drop_gap_pp": limit, "threshold_sensitivity": sensitivity}


def detectable(rules):
    """The smallest gap a sample can see and the sample a gap needs, for a two sided test at the rule's power. Pure arithmetic."""
    d = rules["detectable"]
    z = NormalDist().inv_cdf
    za, zb = z(1 - d["alpha_two_sided"] / 2), z(d["power"])
    total = za + zb
    p = d["p"]
    pq = p * (1 - p)
    n_total = d["n_total"]
    n_arm = n_total // 2
    rhos = [0.0, 0.3, 0.5]
    needed = []
    for pp in d["n_needed_gaps_pp"]:
        g = pp / 100.0
        arm = math.ceil(2 * pq * total**2 / g**2)
        needed.append({"gap_pp": pp, "between_per_arm": arm, "between_total": 2 * arm, "within": {str(r): math.ceil(2 * pq * (1 - r) * total**2 / g**2) for r in rhos}})
    return {
        "alpha_two_sided": d["alpha_two_sided"],
        "power": d["power"],
        "p": p,
        "n_total": n_total,
        "n_arm": n_arm,
        "z_alpha": round(za, 4),
        "z_power": round(zb, 4),
        "between_mde_pp": round(100 * total * math.sqrt(2 * pq / n_arm), 1),
        "within_mde_pp": {str(r): round(100 * total * math.sqrt(2 * pq * (1 - r) / n_total), 1) for r in rhos},
        "needed": needed,
        "arithmetic": f"({za:.3f} + {zb:.3f}) x sqrt(2 x {p} x {1 - p} / {n_arm}) x 100",
    }


def detectable_lines(doc, diagnostics, text):
    t = text["detectable"]
    w = doc["within_mde_pp"]
    lines = [t["between"].format(n_arm=doc["n_arm"], p=doc["p"], mde=doc["between_mde_pp"]), t["within"].format(rho0="0", mde0=w["0.0"], rho1="0.3", mde1=w["0.3"], rho2="0.5", mde2=w["0.5"], mde=doc["between_mde_pp"]), t["unit"]]
    gaps = []
    for model, block in diagnostics["by_model"].items():
        values = [abs(g["mean"]) for g in block["gaps"].values() if g["mean"] is not None]
        if values:
            gaps.append(f"{short(model)} {max(values):.1f}pp")
    if gaps:
        lines.append(t["gap_note"].format(gaps=", ".join(gaps)))
    return lines


def detectable_table(doc, text):
    t = text["detectable"]
    head = t["table_head"]
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for row in doc["needed"]:
        rows.append(f"| {row['gap_pp']}pp | {row['between_per_arm']} | {row['between_total']} | {row['within']['0.0']} | {row['within']['0.3']} | {row['within']['0.5']} |")
    return rows
