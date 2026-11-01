"""Load the KREI .sav and derive the three binary targets exactly as the comparator did.

Comparator (t1_check.py):
  ever    = A19_1 != 9      (zero drink: any answer other than never tried)
  weekly  = A19_1 == 1      (zero drink: at least once a week)
  fav_csd = A15_1 in {7, 8} (first-ranked favourite drink is sugared or zero carbonated)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

from . import paths


def load_sav(path=None):
    """Return (df, meta) for a .sav file. Row order is the file order, which the manifest relies on."""
    path = Path(path) if path is not None else paths.SAV_2025
    if not path.exists():
        raise FileNotFoundError(f"raw file missing: {path}. See README for the download URLs.")
    df, meta = pyreadstat.read_sav(str(path))
    return df, meta


def derive_targets(df):
    """Return a frame with ever, weekly, carb as 0/1 ints. Raises if the coded values are unexpected."""
    a19 = df["A19_1"]
    a15 = df["A15_1"]
    if a19.isna().any() or a15.isna().any():
        raise ValueError("A19_1 or A15_1 has missing values; the comparator assumed none")
    if not set(a19.unique()) <= {1.0, 2.0, 3.0, 4.0, 9.0}:
        raise ValueError(f"unexpected A19_1 codes: {sorted(a19.unique())}")
    return pd.DataFrame(
        {
            "ever": (a19 != 9).astype(int),
            "weekly": (a19 == 1).astype(int),
            "carb": a15.isin([7, 8]).astype(int),
        },
        index=df.index,
    )


def cell_id(df):
    """Age band by sex cell id, 12 cells for the adult file."""
    return (df[paths.AGE].astype(int) * 10 + df[paths.SEX].astype(int)).to_numpy()


def row_hashes(df):
    """Deterministic 16 hex char hash of each full row. Verifies the manifest against the file."""
    h = pd.util.hash_pandas_object(df, index=False)
    return np.array([format(int(x), "016x") for x in h.to_numpy()])


def value_labels(meta, var):
    """Cleaned value labels for a variable as {float code: str}."""
    return {k: str(v).strip() for k, v in (meta.variable_value_labels.get(var) or {}).items()}


def var_label(meta, var):
    return meta.column_names_to_labels.get(var) or ""
