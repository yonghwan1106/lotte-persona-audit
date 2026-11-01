"""Run the train-only leakage screen and write the final allowlist.

Allowlist candidates are chosen by content in config/persona_templates.json, not by their AUC.
This step can only remove candidates. It cannot add any.
"""
import json

from . import data, leakguard, paths, persona, splits


def run():
    df, meta = data.load_sav()
    manifest = splits.load_manifest(df)
    train = splits.masks(manifest)["train"]
    tdf = df.loc[train].reset_index(drop=True)
    targets = data.derive_targets(tdf)
    screen_df = leakguard.screen(tdf, meta, targets)
    templates = persona.load_templates()
    kept, rejected = leakguard.build_allowlist(templates["c2_candidates"], meta, screen_df)
    patterns = leakguard.load_patterns()
    final = {
        "source": "config/persona_templates.json c2_candidates, filtered by leakguard on the train split",
        "threshold": patterns["screen_auc_threshold"],
        "n_candidates": len(templates["c2_candidates"]),
        "n_kept": len(kept),
        "items": kept,
        "rejected": rejected,
    }
    (paths.CONFIG / "allowlist_final.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.RESULTS.mkdir(parents=True, exist_ok=True)
    screen_df.to_csv(paths.RESULTS / "leakage_screen_train.csv", index=False, encoding="utf-8")

    over = screen_df.loc[screen_df.over_threshold]
    summary = {
        "n_screened": int(len(screen_df)),
        "n_over_threshold": int(len(over)),
        "over_threshold_blocked_statically": int((over.static_block != "").sum()),
        "over_threshold_plain_demographic": int(over.plain_demographic.sum()),
        "over_threshold_other_blocked": over.loc[(over.static_block == "") & (~over.plain_demographic), ["var", "label", "peak_auc", "auc_ever", "auc_weekly", "auc_carb"]].to_dict("records"),
        "over_threshold_all": over[["var", "label", "static_block", "plain_demographic", "peak_auc", "auc_ever", "auc_weekly", "auc_carb"]].to_dict("records"),
        "allowlist_kept": [i["var"] for i in kept],
        "allowlist_rejected": rejected,
        "allowlist_top_remaining": {
            t: screen_df.loc[screen_df["var"].isin([i["var"] for i in kept])].sort_values(f"auc_{t}", ascending=False).head(5)[["var", "label", f"auc_{t}"]].to_dict("records")
            for t in paths.TARGETS
        },
    }
    (paths.RESULTS / "leakage_screen_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
