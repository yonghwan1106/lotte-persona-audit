"""Draw the gate panel from the test split and write plain-text batches plus a git-ignored key.

C1 and C2 use the same 300 respondents under unrelated codes. C0 is a single generic respondent repeated
100 times and is not linked to any row. Codes are random strings and carry no row information.
"""
import json

import numpy as np
import pandas as pd

from . import data, leakguard, paths, persona, splits

PANEL_N = 300
BATCH_SIZE = 100
C0_N = 100
ALPHABET = np.array(list("ABCDEFGHJKMNPQRSTUVWXYZ23456789"))
PI_DRAWS = 5000


def draw_panel(test_positions, weights, n=PANEL_N, seed=paths.SEED):
    """Weighted draw without replacement. Returns selected row positions in file coordinates."""
    rng = np.random.default_rng(seed)
    p = weights / weights.sum()
    return np.sort(rng.choice(test_positions, size=n, replace=False, p=p))


def inclusion_probabilities(test_positions, weights, n=PANEL_N, draws=PI_DRAWS, seed=paths.SEED + 1):
    """Monte Carlo inclusion probability of each test row under the same draw."""
    rng = np.random.default_rng(seed)
    p = weights / weights.sum()
    hits = np.zeros(len(test_positions))
    for _ in range(draws):
        hits[rng.choice(len(test_positions), size=n, replace=False, p=p)] += 1
    return np.maximum(hits, 1) / draws


def make_codes(n, rng, used):
    codes = []
    while len(codes) < n:
        c = "".join(rng.choice(ALPHABET, size=8))
        if c not in used:
            used.add(c)
            codes.append(c)
    return codes


def header(prompt, label):
    return "\n".join(
        [
            f"# batch {label}",
            "",
            prompt["instruction"],
            "",
            prompt["question_a19"],
            prompt["question_a15"],
            "",
            prompt["output_spec"],
            "",
            "----",
            "",
        ]
    )


def respondent_block(code, text):
    return f"code: {code}\n{text}\n"


def build(out_dir=None, key_path=None):
    out_dir = out_dir or paths.GATE_INPUTS
    key_path = key_path or paths.GATE_KEY
    df, meta = data.load_sav()
    manifest = splits.load_manifest(df)
    test = splits.masks(manifest)["test"]
    test_positions = np.flatnonzero(test)
    weights = df[paths.WEIGHT].to_numpy()[test]
    panel = draw_panel(test_positions, weights)
    pi_all = inclusion_probabilities(test_positions, weights)
    pi = dict(zip(test_positions.tolist(), pi_all.tolist()))
    psfwt = df[paths.WEIGHT].to_numpy()
    prompt = json.loads((paths.CONFIG / "batch_prompt.json").read_text(encoding="utf-8"))
    templates = persona.load_templates()
    allowlist = persona.load_final_allowlist()["items"]
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.txt"):
        old.unlink()
    used = set()
    key_rows = []
    forbidden_cols = [paths.HOUSEHOLD, "id", "FID", "\uc8fc\uad6c\uc785\uc790id", paths.PSU]
    samples = {}

    rng = np.random.default_rng([paths.SEED, 0])
    codes = make_codes(C0_N, rng, used)
    c0_text = persona.render_c0(templates)
    samples["C0"] = c0_text
    body = header(prompt, "C0-01") + "\n".join(respondent_block(c, c0_text) for c in codes)
    (out_dir / "C0_batch01.txt").write_text(body, encoding="utf-8")
    (out_dir / "C0_DESIGN_NOTE.txt").write_text(prompt["c0_design_note"] + "\n", encoding="utf-8")
    for i, c in enumerate(codes):
        key_rows.append({"condition": "C0", "code": c, "batch": 1, "row_index": -1, "panel_weight": 1.0})

    for cond_idx, cond in enumerate(("C1", "C2"), start=1):
        rng = np.random.default_rng([paths.SEED, cond_idx])
        order = rng.permutation(panel)
        codes = make_codes(len(order), rng, used)
        code_of = dict(zip(order.tolist(), codes))
        for b, start in enumerate(range(0, len(order), BATCH_SIZE), start=1):
            batch_rows = rng.permutation(order[start : start + BATCH_SIZE])
            blocks = []
            for row_index in batch_rows.tolist():
                row = df.iloc[row_index]
                forbidden = [row[c] for c in forbidden_cols]
                if cond == "C1":
                    text = persona.render_c1(row, templates)
                    leakguard.scan_text(text, forbidden)
                else:
                    text = persona.render_c2(row, allowlist, templates, forbidden)
                samples.setdefault(cond, text)
                code = code_of[row_index]
                blocks.append(respondent_block(code, text))
                key_rows.append(
                    {
                        "condition": cond,
                        "code": code,
                        "batch": b,
                        "row_index": row_index,
                        "panel_weight": psfwt[row_index] / pi[row_index],
                    }
                )
            body = header(prompt, f"{cond}-{b:02d}") + "\n".join(blocks)
            (out_dir / f"{cond}_batch{b:02d}.txt").write_text(body, encoding="utf-8")

    key_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(key_rows).to_csv(key_path, index=False, encoding="utf-8")
    t = data.derive_targets(df)
    return {
        "panel_n": int(len(panel)),
        "all_in_test": bool(test[panel].all()),
        "unique_units": int(df[paths.PSU].iloc[panel].nunique()),
        "unique_households": int(df[paths.HOUSEHOLD].iloc[panel].nunique()),
        "positives_in_panel": {k: int(t[k].to_numpy()[panel].sum()) for k in paths.TARGETS},
        "files": sorted(p.name for p in out_dir.glob("*.txt")),
        "samples": samples,
    }
