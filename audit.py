"""Command line for the consumer panel auditor harness. No LLM calls and no API key.

  python audit.py prepare      check targets and write the split manifest
  python audit.py reproduce    whole-file reproduction of the scout and comparator numbers
  python audit.py hunt         train-only hunt for the high weekly AUC
  python audit.py screen       train-only leakage screen, writes config/allowlist_final.json
  python audit.py baselines    baselines on the test split
  python audit.py batches      gate panel input batches and the git-ignored key
  python audit.py gate-reference  floors and real answers on the same 300, no answers needed
  python audit.py freeze       hash the pre-registered config
  python audit.py score        score runs/gate/answers/*.csv
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from lotte_audit import baselines, batches, data, hunt, paths, reproduce, score, screening, splits  # noqa: E402


def cmd_prepare(_):
    df, meta = data.load_sav()
    t = data.derive_targets(df)
    print("rows", len(df), "columns", df.shape[1], "weight", paths.WEIGHT in df.columns)
    print("A19_1 label:", data.var_label(meta, "A19_1"), data.value_labels(meta, "A19_1"))
    print("A15_1 label:", data.var_label(meta, "A15_1"), {k: v for k, v in data.value_labels(meta, "A15_1").items() if k in (7.0, 8.0, 12.0)})
    print("unweighted positives", {k: int(t[k].sum()) for k in paths.TARGETS})
    meta_out = splits.write_manifest(df)
    print(json.dumps(meta_out, indent=2))
    splits.load_manifest(df)
    print("split manifest regenerated from the seed and its whole hash verified")


def cmd_reproduce(_):
    r = reproduce.run()
    reproduce.write(r)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_hunt(_):
    r = hunt.run()
    hunt.write(r)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_screen(_):
    s = screening.run()
    print(json.dumps(s, ensure_ascii=False, indent=2))


def cmd_baselines(_):
    b = baselines.compute()
    baselines.write(b)
    print(baselines.to_markdown(b))


def cmd_batches(_):
    r = batches.build()
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_gate_reference(_):
    print(json.dumps(score.gate_reference(), ensure_ascii=False, indent=2))


def cmd_freeze(_):
    score.freeze()
    print(json.dumps(score.config_hashes(), indent=2))


def cmd_score(args):
    answers = score.read_answers(args.answers or paths.GATE_ANSWERS)
    r = score.score(answers)
    score.write(r, args.out, args.name)
    print(score.to_markdown(r))
    print(r["switch_rule"]["decision"])


def main():
    warnings.filterwarnings("ignore", category=FutureWarning)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in [
        ("prepare", cmd_prepare),
        ("reproduce", cmd_reproduce),
        ("hunt", cmd_hunt),
        ("screen", cmd_screen),
        ("baselines", cmd_baselines),
        ("batches", cmd_batches),
        ("gate-reference", cmd_gate_reference),
        ("freeze", cmd_freeze),
    ]:
        sub.add_parser(name).set_defaults(func=fn)
    s = sub.add_parser("score")
    s.add_argument("--answers", default=None)
    s.add_argument("--out", default=None)
    s.add_argument("--name", default="gate_score")
    s.set_defaults(func=cmd_score)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
