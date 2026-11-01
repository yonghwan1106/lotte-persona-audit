"""Fixed splits, seed 42. Whole sampling units (vuid) go to one split, inside each stratum (STR).

Respondents of one household, and of one survey unit, never straddle splits. A household split alone
would still let unit-level effects cross over. The comparators used plain row splits, so their AUCs
can differ for that reason.
"""
import hashlib
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


def build_manifest(df):
    """Row index, full-row hash and split per row, regenerated from the raw file and the seed. It is not stored: it is one row per respondent."""
    return pd.DataFrame({"row_index": np.arange(len(df)), "row_hash": data.row_hashes(df), "split": assign_units(df)})


def manifest_sha256(manifest):
    """Hash of the whole manifest as text, with LF line ends. Row hashes hold the file's content, so this also pins the raw file and row order."""
    lines = ["row_index,row_hash,split"] + [f"{i},{h},{s}" for i, h, s in zip(manifest.row_index, manifest.row_hash, manifest.split)]
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def write_manifest(df):
    """Write the split summary and the whole-file hash. Aggregates only. The per-row manifest is never written to disk."""
    paths.MANIFESTS.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(df)
    split = manifest.split.to_numpy()
    groups = pd.DataFrame({"s": split, "u": df[paths.PSU].to_numpy(), "h": df[paths.HOUSEHOLD].to_numpy()})
    meta = {
        "manifest_sha256": manifest_sha256(manifest),
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
    """Regenerate the manifest from the raw file and the seed, and refuse unless its whole hash equals the one in the split summary.

    A changed raw file, a changed row order or a library that shuffles differently all stop here. requirements.txt pins numpy and pandas for this.
    """
    if df is None:
        df, _ = data.load_sav()
    manifest = build_manifest(df)
    expected = json.loads(paths.SPLIT_META.read_text(encoding="utf-8"))["manifest_sha256"]
    got = manifest_sha256(manifest)
    if got != expected:
        raise ValueError(f"regenerated split manifest hash {got} differs from {expected}: raw file, row order or library versions changed")
    return manifest


def masks(manifest):
    """Boolean arrays per split, positional against the file order."""
    s = manifest.split.to_numpy()
    return {name: s == name for name in paths.SPLIT_FRACTIONS}
