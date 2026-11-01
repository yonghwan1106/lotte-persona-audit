"""Seed sensitivity of the duel acceptance. Written after the frozen result was seen, because the surrogate keep rate landed close to its bar.

It changes no rule, no label and no frozen file. The label stays what the frozen seeds gave. Stored answers only, no API.

  python src/stage4_sensitivity.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stage4_measures as sm  # noqa: E402
from lotte_audit import calibration as cal, stage4  # noqa: E402

RUNS = {
    "fold_seed_99": {"draw_seed": 42, "pi_seed": 43, "fold_seed": [99, 5]},
    "fold_seed_20261102": {"draw_seed": 42, "pi_seed": 43, "fold_seed": [20261102, 5]},
    "draw_seed_99": {"draw_seed": 99, "pi_seed": 4321, "fold_seed": [42, 5]},
    "draw_seed_20261102": {"draw_seed": 20261102, "pi_seed": 777, "fold_seed": [42, 5]},
}
SHOWN = ("terra_C2", "luna_C1", "control_s1.0", "surrogate_terra_slot", "surrogate_luna_slot")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sm.guard()
    s = sm.setup()
    ctx = s["ctx"]
    slots = {k: v for k, v in sm.duel_slots(s).items() if k in SHOWN}
    out = {}
    for name, run in RUNS.items():
        pool = ctx["pool"]
        draws = cal.make_draws(pool["w"], pool["units"], sm.DRAWS["n"], "row", sm.DRAWS["repeats"], [run["draw_seed"], sm.DRAWS["n"], 0], sm.DRAWS["pi_draws"], run["pi_seed"])
        raw = stage4.duel_study(ctx, slots, draws, run["fold_seed"])
        summary = stage4.summarise_duel(raw, stage4.ITEMS, sm.A3_PLAN["resamples"], sm.A3_PLAN["seed"])
        accept = stage4.acceptance(raw, sm.BAR, sm.POSITIVE, sm.SURROGATES, sm.A3_PLAN["resamples"], sm.A3_PLAN["seed"])
        out[name] = {"run": run, "acceptance_passed": accept["passed"], "keep_rate": {k: summary[k]["pooled"]["panel_excluded"]["keep_rate"] for k in SHOWN}, "beats_rate": {k: summary[k]["pooled"]["panel_excluded"]["beats_rate"] for k in SHOWN}, "false_keep_rate": {k: summary[k]["pooled"]["panel_excluded"]["false_keep_rate"] for k in SHOWN}, "missed_keep_rate": {k: summary[k]["pooled"]["panel_excluded"]["missed_keep_rate"] for k in SHOWN}}
    doc = {"written_after_seeing_the_frozen_result": True, "note": "The acceptance and the label come from the frozen seeds in duel_validity.json. This file only shows how far they move with other seeds. It changes nothing.", "bar": sm.BAR, "runs": out}
    (sm.RESULTS / "duel_seed_sensitivity.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
