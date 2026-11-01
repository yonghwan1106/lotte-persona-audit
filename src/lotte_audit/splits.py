"""Fixed splits, seed 42. Whole sampling units (vuid) go to one split, inside each stratum (STR).

Respondents of one household, and of one survey unit, never straddle splits. A household split alone
would still let unit-level effects cross over. The comparators used plain row splits, so their AUCs
can differ for that reason.
"""
import csv
import json

import numpy as np
import pandas as pd

from . import data, paths


def assign_units(df, seed=paths.SEED, fractions=None):
    """Return an array of split names aligned with df rows."""
    fractions = fractions or paths.SPLIT_FRACTIONS
    names = list(fractions)
    target = np.array([fractions[n] for n in names], dtype=float)
    rng = np.random.default_rng(seed)
    counts = np.zeros(len(names), dtype=float)
    unit_split = {}
    sizes = df.groupby(paths.PSU).size()
    strata = df.groupby(paths.STRATUM)[paths.PSU].unique()
    for stratum in sorted(strata.index):
        units = np.sort(strata[stratum])
        rng.shuffle(units)
        local = np.zeros(len(names), dtype=float)
        for u in units:
            # Give the unit to the split furthest below its target, within the stratum and overall.
            total_local = local.sum() + 1.0
            total_all = counts.sum() + 1.0
            deficit = (target - local / total_local) + 0.5 * (target - counts / total_all)
            j = int(np.argmax(deficit))
            unit_split[u] = names[j]
            local[j] += sizes[u]
            counts[j] += sizes[u]
    return df[paths.PSU].map(unit_split).to_numpy()


def write_manifest(df):
    """Write the committed manifest: row index, full-row hash, split. Contains no answers or ids."""
    paths.MANIFESTS.mkdir(parents=True, exist_ok=True)
    split = assign_units(df)
    hashes = data.row_hashes(df)
    with open(paths.SPLIT_MANIFEST, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row_index", "row_hash", "split"])
        for i, (h, s) in enumerate(zip(hashes, split)):
            w.writerow([i, h, s])
    groups = pd.DataFrame({"s": split, "u": df[paths.PSU].to_numpy(), "h": df[paths.HOUSEHOLD].to_numpy()})
    meta = {
        "seed": paths.SEED,
        "unit": "vuid inside STR",
        "fractions_target": paths.SPLIT_FRACTIONS,
        "rows": {k: int(v) for k, v in groups.s.value_counts().items()},
        "units": {k: int(v) for k, v in groups.groupby("s").u.nunique().items()},
        "households": {k: int(v) for k, v in groups.groupby("s").h.nunique().items()},
    }
    paths.SPLIT_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_manifest(df=None):
    """Read the manifest and, when df is given, verify every row hash against the file."""
    m = pd.read_csv(paths.SPLIT_MANIFEST, dtype={"row_hash": str})
    if df is not None:
        if len(df) != len(m):
            raise ValueError(f"manifest has {len(m)} rows, data has {len(df)}")
        if not (data.row_hashes(df) == m.row_hash.to_numpy()).all():
            raise ValueError("row hashes differ from the manifest: raw file changed or row order differs")
    return m


def masks(manifest):
    """Boolean arrays per split, positional against the file order."""
    s = manifest.split.to_numpy()
    return {name: s == name for name in paths.SPLIT_FRACTIONS}
