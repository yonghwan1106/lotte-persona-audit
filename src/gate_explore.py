"""EXPLORATORY additions to the gate score. Not part of the pre-registered rule and never read by score.

  python src/gate_explore.py --answers runs/gate/answers_<model> --out results/gate --name <name>

Writes aggregates only: mean prediction by age band, by sex and by age band and sex against the real
test-split means, the correlation of panel cell means with real cell means, and the share of rows
where p_zero_weekly is above p_zero_ever. Answers are read, not changed.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from lotte_audit import data, metrics, paths, score, splits  # noqa: E402


def explore(answers_dir):
    df, meta = data.load_sav()
    key = score.load_key()
    answers = score.read_answers(answers_dir)
    score.validate(answers, key)
    merged = key.merge(answers, on="code", how="left", validate="one_to_one")
    test = splits.masks(splits.load_manifest(df))["test"]
    targets = data.derive_targets(df)
    w = df[paths.WEIGHT].to_numpy()
    ages = df[paths.AGE].astype(int).to_numpy()
    sexes = df[paths.SEX].astype(int).to_numpy()
    cells = data.cell_id(df)
    age_labels = {int(k): v for k, v in data.value_labels(meta, paths.AGE).items()}
    out = {"_note": "EXPLORATORY. Does not alter the pre-registered switch rule.", "conditions": {}}
    for cond in ("C0", "C1", "C2"):
        sub = merged.loc[merged.condition == cond]
        ever = sub[paths.ANSWER_COL["ever"]].to_numpy()
        weekly = sub[paths.ANSWER_COL["weekly"]].to_numpy()
        share = float((weekly > ever + 1e-9).mean())
        c = {"n": int(len(sub)), "share_weekly_above_ever": round(share, 4), "items": {}}
        for t in paths.TARGETS:
            col = paths.ANSWER_COL[t]
            p = sub[col].to_numpy(dtype=float)
            y = targets[t].to_numpy()
            item = {"answer_sd_pct": round(100 * float(np.std(p, ddof=1)), 2), "answer_min_pct": round(100 * float(p.min()), 2), "answer_max_pct": round(100 * float(p.max()), 2)}
            if cond != "C0":
                rows = sub["row_index"].to_numpy()
                wp = sub["panel_weight"].to_numpy()
                item["by_age_band_pct"] = {
                    age_labels.get(int(a), str(int(a))): {
                        "panel": round(100 * float(np.average(p[ages[rows] == a], weights=wp[ages[rows] == a])), 2),
                        "real": round(100 * float(np.average(y[test & (ages == a)], weights=w[test & (ages == a)])), 2),
                    }
                    for a in sorted(set(ages[rows].tolist()))
                }
                item["by_sex_pct"] = {
                    {1: "male", 2: "female"}[s]: {
                        "panel": round(100 * float(np.average(p[sexes[rows] == s], weights=wp[sexes[rows] == s])), 2),
                        "real": round(100 * float(np.average(y[test & (sexes == s)], weights=w[test & (sexes == s)])), 2),
                    }
                    for s in (1, 2)
                }
                panel_cells = metrics.cell_means(p, wp, cells[rows])
                real_cells = metrics.cell_means(y[test], w[test], cells[test])
                item["cell_pearson_r"] = round(metrics.cell_pearson(panel_cells, real_cells), 3)
                item["cell_means_pct"] = {str(k): {"panel": round(100 * panel_cells[k], 2), "real": round(100 * real_cells[k], 2)} for k in sorted(panel_cells)}
            c["items"][t] = item
        out["conditions"][cond] = c
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--answers", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    result = explore(args.answers)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{args.name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
