"""Shared fixtures. Real-data fixtures skip when the raw file or the gate key is absent."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from lotte_audit import data, paths, score, splits  # noqa: E402


@pytest.fixture(scope="session")
def real():
    if not paths.SAV_2025.exists():
        pytest.skip("raw file not present")
    df, meta = data.load_sav()
    return {"df": df, "meta": meta, "targets": data.derive_targets(df)}


@pytest.fixture(scope="session")
def key():
    if not paths.GATE_KEY.exists():
        pytest.skip("gate key not present; run audit.py batches")
    return score.load_key()


@pytest.fixture(scope="session")
def baseline():
    return json.loads((paths.RESULTS / "baselines.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def manifest(real):
    return splits.load_manifest(real["df"])


def answers_from(key, fn_c12, c0_value=0.5):
    """Build a synthetic answer frame. fn_c12(row_index_array, target) gives probabilities."""
    rows = []
    for cond, sub in key.groupby("condition"):
        d = pd.DataFrame({"code": sub["code"].to_numpy()})
        for t in paths.TARGETS:
            col = paths.ANSWER_COL[t]
            if cond == "C0":
                d[col] = c0_value
            else:
                d[col] = fn_c12(sub["row_index"].to_numpy(), t)
        rows.append(d)
    return pd.concat(rows, ignore_index=True)
