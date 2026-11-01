"""Folds that keep survey units whole. Written after the frozen stage 4 result was seen.

duel.py is frozen and stays as it was. This module only gives its loss functions and its rule another fold column, so nothing about the rule itself differs.
"""
import numpy as np

from . import duel


def folds_by_unit(units, k, rng):
    """Fold number per row. All rows of a survey unit share a fold: units are shuffled and dealt in turn."""
    units = np.asarray(units)
    uniq = np.unique(units)
    uniq = uniq[rng.permutation(len(uniq))]
    table = {u: i % k for i, u in enumerate(uniq.tolist())}
    return np.array([table[u] for u in units.tolist()])


def duel_on_folds(answers_by_item, cells, w, cell_age, cell_sex, fold, k=duel.FOLDS):
    """duel.duel on a given fold column. Same losses, same rule, same output."""
    cells = np.asarray(cells)
    w = np.asarray(w, dtype=float)
    improvements, per_item = {}, {}
    for item, (y, p) in answers_by_item.items():
        y = np.asarray(y, dtype=float)
        p = np.asarray(p, dtype=float)
        r1 = duel.r1_fold_losses(y, w, cells, cell_age, cell_sex, fold, k)
        panel = duel.panel_fold_losses(y, w, p, fold, k)
        improvements[item] = r1 - panel
        per_item[item] = {**duel.decide(improvements[item]), "r1_loss": float(r1.mean()), "panel_loss": float(panel.mean())}
    pooled = duel.decide(np.mean([improvements[i] for i in improvements], axis=0))
    return {"folds": k, "pooled": pooled, "per_item": per_item}
