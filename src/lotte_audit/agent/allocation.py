"""The real sample plan: 200 respondents, margin of error arithmetic, and which cards go out. Deterministic.

The arithmetic is shown, not only its result, so a reader can check every line by hand.
"""
import math

from . import settings


def margin_pp(n, p=0.5, z=1.96):
    """Half width of the 95 percent interval of a share, in percentage points, for a simple random sample of n."""
    if n <= 0:
        return None
    return round(100.0 * z * math.sqrt(p * (1 - p) / n), 1)


def design_effect(m, icc):
    return 1.0 + (m - 1) * icc


def line(label, n, p, z):
    return {"group": label, "n": n, "margin_pp": margin_pp(n, p, z), "arithmetic": f"1.96 x sqrt({p} x {round(1 - p, 3)} / {n}) x 100 = {margin_pp(n, p, z)}pp"}


def largest_remainder(total, parts):
    """Integer shares of total across equal parts, summing exactly to total."""
    base = total // parts
    extra = total - base * parts
    return [base + (1 if i < extra else 0) for i in range(parts)]


def cells(age_groups, sex):
    return [f"{age}_{s}" for age in age_groups for s in sex.values()]


def target_cells(target, age_groups, sex):
    if target == "all":
        return cells(age_groups, sex)
    ages = [a for a in age_groups if a == target]
    if not ages and target == "19-59":
        ages = ["19-39", "40-59"]
    if not ages:
        raise ValueError(f"unknown target segment {target}")
    return cells(ages, sex)


def pick_cards(verdict, roles, diag, max_cards, text):
    """Which cards go to the real 200: a suggestion for the human to confirm. A panel drop is only ever a proposal."""
    candidates = [c for c, r in roles.items() if r["role"] == "candidate"]
    words = text["allocation_text"]
    main = next(iter(diag["by_model"]))
    rank = diag["by_model"][main]["rank"]
    overall = [r for r in verdict["rows"] if r["segment"] == "all" and r["model"] == main]
    usable = {r["card"]: r["order_allowed"] for r in overall}
    picks = []
    if all(usable.get(c) for c in rank) and len(rank) >= 2:
        picks.append({"card": rank[0], "use": words["survivor"]})
        if len(rank) > 2:
            picks.append({"card": rank[1], "use": words["survivor"]})
        picks.append({"card": rank[-1], "use": words["revive"]})
    else:
        # Panel order is not usable for some candidate, so every candidate stays on the list for the human to choose from.
        for c in candidates:
            picks.append({"card": c, "use": words["manual"]})
    keep = max_cards - 1  # one seat is held for the existing product benchmark
    return picks[:keep], words["benchmark_missing"]


def allocate(verdict, roles, diag, cfg, text):
    a = cfg["allocation"]
    seg = cfg["segments"]
    z, p, total = a["z"], a["p"], a["total"]
    target_n, rest_n = a["target_n"], a["rest_n"]
    if target_n + rest_n != total:
        raise ValueError("target and rest must add up to the total")
    picks, benchmark_note = pick_cards(verdict, roles, diag, a["max_real_cards"], text)
    targets = [roles[c["card"]]["target_segment"] for c in picks]
    target = max(set(targets), key=targets.count) if targets else "all"
    in_target = target_cells(target, seg["age_groups"], seg["sex"])
    every = cells(seg["age_groups"], seg["sex"])
    outside = [c for c in every if c not in in_target]
    if not outside:
        target_n, rest_n = total, 0
    rows = []
    for name, n in zip(in_target, largest_remainder(target_n, len(in_target))):
        rows.append({"cell": name, "group": "target", **line(name, n, p, z)})
    if outside:
        for name, n in zip(outside, largest_remainder(rest_n, len(outside))):
            rows.append({"cell": name, "group": "rest", **line(name, n, p, z)})
    n_cards = len(picks) + 1
    first_card_n = total // n_cards
    effects = []
    for item, icc in a["icc_from_krei"].items():
        for m in a["unit_size_examples"]:
            d = design_effect(m, icc)
            eff = round(total / d, 1)
            effects.append(
                {
                    "item": item,
                    "unit_size": m,
                    "icc": icc,
                    "design_effect": round(d, 2),
                    "effective_n": eff,
                    "margin_pp": margin_pp(eff, p, z),
                    "arithmetic": f"1 + ({m} - 1) x {icc} = {round(d, 2)}; {total} / {round(d, 2)} = {eff}; 1.96 x sqrt({p} x {round(1 - p, 3)} / {eff}) x 100 = {margin_pp(eff, p, z)}pp",
                }
            )
    return {
        "total": total,
        "target_segment": target,
        "target_n": target_n,
        "rest_n": rest_n,
        "cards": picks,
        "benchmark_note": benchmark_note,
        "choose_note": text["allocation_text"]["choose_note"],
        "overall": line("total", total, p, z),
        "target": line("target", target_n, p, z),
        "rest": line("rest", rest_n, p, z) if rest_n else None,
        "cells": rows,
        "six_cells_even": line("6 cells even", total // 6, p, z),
        "twelve_cells_even": line("12 cells even", total // 12, p, z),
        "first_card_each": line(f"first card only, {n_cards} cards", first_card_n, p, z),
        "design_effects": effects,
        "weighting": "Weight the sample to read a national value. The target and rest split is a design choice, not a population share.",
        "does_not_answer": "This plan answers whether a large gap has the right direction and where the panel is wrong. It does not measure 12 cells.",
    }


def plan_hash_of(doc):
    return settings.canonical_hash(doc)
