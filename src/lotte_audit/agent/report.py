"""Verdict table, report and ledger entry, all rendered by code. The only model text in a report has passed the number rule."""
import json
import platform
import time
from importlib import metadata
from pathlib import Path

from . import narration, settings

OVERALL = "all"


def _dump(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def _sdk_versions():
    versions = {"python": platform.python_version()}
    for name in ("openai-agents", "openai"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


HIDDEN_NOTE = "No absolute panel value is stored in this file, only paired differences. The full values stay in the saved run under runs/."


def tracked_diagnostics(diag):
    """The diagnostics that go into git: paired differences and flags, with every absolute panel value left out.

    Differences stay, so with no absolute value in the file none can be worked back. The complete document stays in the saved context under runs/.
    """
    doc = json.loads(json.dumps(diag, default=str))
    doc["absolute_values"] = HIDDEN_NOTE
    for block in doc["by_model"].values():
        block.pop("internal", None)
        for seg in block.get("segments", {}).values():
            seg.pop("t2b_pp", None)
    if doc.get("c0"):
        doc["c0"].pop("c0_internal", None)
    return doc


def manifest(ctx):
    """Everything a result depends on. Its hash goes on the report's first line."""
    return {
        "run_id": ctx.run_id,
        "config_files": {name: settings.file_hash(name) for name in settings.FROZEN_FILES},
        "agent_text_sha256": settings.file_hash("config/agent_text.json"),
        "prompt_sha256": ctx.cfg["prompt_sha256"],
        "cards_sha256": settings.canonical_hash({c: v["clean_text"] for c, v in ctx.cards.items()}),
        "plan_hash": ctx.plan["plan_hash"] if ctx.plan else None,
        "panel_sha256": ctx.panel_sha256,
        "models": {k: m["id"] for k, m in ctx.cfg["models"].items()},
        "rule_version": ctx.verdict["rule_version"] if ctx.verdict else None,
        "versions": _sdk_versions(),
    }


def verdict_table(verdict, segments=True):
    head = "| card | model | segment | n | v2 base | run status | label | absolute shown | order allowed | flags |\n|---|---|---|---|---|---|---|---|---|---|"
    lines = [head]
    for r in verdict["rows"]:
        if not segments and r["segment"] != OVERALL:
            continue
        lines.append(f"| {r['card']} | {settings.short_model(r['model'])} | {r['segment']} | {r['n']} | {r['base_label_v2']} | {r['run_status']} | {r['label']} | {r['absolute_shown']} | {r['order_allowed']} | {', '.join(r['flags']) or '-'} |")
    return "\n".join(lines)


def fmt(c):
    if not c or c.get("mean") is None:
        return "n/a"
    return f"{c['mean']:+.2f} [{c['ci95'][0]:+.2f}, {c['ci95'][1]:+.2f}]"


def diagnostics_section(diag):
    lines = ["| diagnostic | " + " | ".join(settings.short_model(m) for m in diag["by_model"]) + " |", "|---|" + "---|" * len(diag["by_model"])]

    def row(name, fn):
        lines.append(f"| {name} | " + " | ".join(fn(d) for d in diag["by_model"].values()) + " |")

    row("paraphrase difference A minus A_para, pp", lambda d: fmt(d["noise"]))
    row("noise limit used by the rules, pp", lambda d: f"{d['noise_upper']}")
    keys = list(next(iter(diag["by_model"].values()))["gaps"])
    for key in keys:
        row(f"candidate gap {key}, pp", lambda d, k=key: f"{fmt(d['gaps'][k])} {'distinct' if d['gaps'][k]['distinguishable'] else 'indistinct'}")
    negs = list(next(iter(diag["by_model"].values()))["negative"])
    for card in negs:
        row(f"{card} minus negative control, pp", lambda d, c=card: f"{fmt(d['negative'][c])} {'separated' if d['negative'][c]['separated'] else 'NOT separated'}")
    row("brand effect A_brand minus A, pp", lambda d: f"{fmt(d['brand'])} {'exceeds noise' if d['brand'] and d['brand']['exceeds_noise'] else 'within noise'}")
    row("rank by panel internal value", lambda d: " > ".join(d["rank"]))
    row("missing share per card", lambda d: ", ".join(f"{c} {v['overall']}" for c, v in d["missing"].items()))
    out = "\n".join(lines)
    md = diag["model_disagreement"]
    out += f"\n\nModel disagreement pairs: {md['pairs'] or 'none'}. Ranks: {md['ranks']}."
    c0 = diag["c0"]
    if c0:
        out += f"\n\nNo-persona comparison on {settings.short_model(diag['c0_model'])}, calls per card {c0['calls_per_card']}. C0 rank {c0['c0_rank']}, C1 rank {c0['c1_rank']}, same rank {c0['same_rank']}, flag no personal information {c0['flag_no_personal_information']}."
        out += "\n\n| pair | C1 gap | C0 gap | C1 minus C0 | within noise |\n|---|---|---|---|---|\n"
        out += "\n".join(f"| {k} | {p['c1_gap']} | {p['c0_gap']} | {p['c1_minus_c0']} | {p['within_noise']} |" for k, p in c0["pairs"].items())
    return out


def scale_lines(ctx):
    """A gap can exceed this run's noise and still be far too small for the real sample to see."""
    out = []
    margin = ctx.allocation["overall"]["margin_pp"]
    template = ctx.text["report"]["scale_line"]
    for model, d in ctx.diagnostics["by_model"].items():
        gaps = [abs(g["mean"]) for g in d["gaps"].values() if g["mean"] is not None]
        if gaps:
            out.append(template.format(model=settings.short_model(model), largest=f"{max(gaps):.1f}", noise=d["noise_upper"], margin=margin))
    return out


def allocation_section(a):
    lines = [a["choose_note"], "", f"Target segment {a['target_segment']}: {a['target_n']} respondents. Rest: {a['rest_n']}.", "", "| group | n | margin pp | arithmetic |", "|---|---|---|---|"]
    named = [a["overall"], a["target"], *([a["rest"]] if a["rest"] else []), a["six_cells_even"], a["twelve_cells_even"], a["first_card_each"]]
    lines += [f"| {x['group']} | {x['n']} | {x['margin_pp']} | {x['arithmetic']} |" for x in named]
    lines += ["", "| cell | n | margin pp |", "|---|---|---|"]
    lines += [f"| {c['cell']} | {c['n']} | {c['margin_pp']} |" for c in a["cells"]]
    lines += ["", "Design effect = 1 + (m - 1) x ICC. ICC values are from the KREI data of this project.", "", "| item | m | ICC | design effect | effective n | margin pp | arithmetic |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {d['item']} | {d['unit_size']} | {d['icc']} | {d['design_effect']} | {d['effective_n']} | {d['margin_pp']} | {d['arithmetic']} |" for d in a["design_effects"]]
    lines += ["", "Cards proposed for the real sample:", ""]
    lines += [f"- {c['card']}: {c['use']}" for c in a["cards"]]
    lines += [f"- {a['benchmark_note']}", "", a["weighting"], a["does_not_answer"]]
    return "\n".join(lines)


def cost_summary(ctx):
    panel = settings.spent_in(settings.PANEL_LOG)
    model = settings.spent_in(settings.MODEL_LOG)
    return {"stage_panel_usd": round(panel, 6), "stage_agent_models_usd": round(model, 6), "stage_total_usd": round(panel + model, 6), "stage_budget_usd": ctx.budget.budget_usd, "this_run_panel_usd": (ctx.run_doc or {}).get("spent_this_run_usd")}


def render_report(ctx, manifest_sha):
    t = ctx.text["report"]
    guard = narration.Guard(ctx.text)
    lines = [f"manifest sha256: {manifest_sha}", ""]
    lines += [f"# {t['demo_banner']}" if ctx.demo else "# concept audit", ""]
    lines += [t["never_market"], ""]
    lines += [f"## {t['not_verified_title']}", ""] + [f"- {x}" for x in t["not_verified"]] + [""]
    lines += [f"## {t['excluded_title']}", ""]
    lines += [f"- {e['card_id']}: {e['class']}: {e['text']}" for e in ctx.excluded] or [t["excluded_none"]]
    lines += [""]
    if ctx.removed:
        lines += [f"## {t['removed_title']}", ""] + [f"- {e['card_id']} ({e['by']}): {e['text']}" for e in ctx.removed] + [""]
    if ctx.leading_log:
        lines += [f"## {t['leading_title']}", ""] + [f"- {e['card_id']} ({e['decision']}, {e['approver']}): {e['text']}" for e in ctx.leading_log] + [""]
        if any(e["decision"] == "keep" for e in ctx.leading_log):
            lines += [t["leading_keep_note"], ""]
    if ctx.anchor_reductions:
        lines += [f"## {t['anchor_title']}", "", t["anchor_note"], ""] + [f"- {e['card_id']}: {', '.join(e['anchor_items'])} (left out {', '.join(e['left_out'])})" for e in ctx.anchor_reductions] + [""]
    lines += ["## verdict", "", ctx.verdict["header"], ""]
    lines += [f"- {s}" for s in ctx.verdict["sentences"]] + [""]
    lines += [verdict_table(ctx.verdict, segments=False), ""]
    lines += ["### by segment", "", verdict_table(ctx.verdict, segments=True), ""]
    lines += [f"## {t['hypothesis_title']}", ""]
    accepted = ctx.narration.get("accepted")
    if accepted:
        lines += [f"- {s}" for s in guard.render(accepted, ctx.catalog)]
    else:
        lines += [guard.rejected_note if ctx.narration.get("rejections") else guard.not_called_note]
    lines += [""]
    lines += [f"## {t['reasons_title']}", "", t["reasons_note"], ""]
    for card, tokens in (ctx.reason_tokens or {}).items():
        lines += [f"- {card}: " + (", ".join(f"{w} {c}" for w, c in tokens) or "-")]
    lines += ["", "## diagnostics (panel internal, no truth)", "", t["diagnostics_note"], ""]
    lines += [f"- {x}" for x in scale_lines(ctx)] + [""]
    lines += [diagnostics_section(ctx.diagnostics), ""]
    lines += ["## real sample plan", "", allocation_section(ctx.allocation), ""]
    lines += ["## questionnaire", "", ctx.questionnaire["intro"], "", ctx.questionnaire["anchor_note"], ""]
    lines += [f"- {x['id']} ({x['kind']})" for x in ctx.questionnaire["items"]] + [""]
    lines += [f"- {x}" for x in ctx.questionnaire["fieldwork_rules"]] + [""]
    lines += [f"## {t['r1_title']}", ""] + [f"- {x}" for x in t["r1_lines"]] + [""]
    a = ctx.approval or {}
    lines += ["## approval and cost", "", f"Approved by: {a.get('approver')} at {a.get('at')}, plan {a.get('plan_hash')}.", ""]
    if ctx.demo:
        lines += [t["approval_note"], ""]
    lines += [f"Plan: {ctx.plan['calls_total']} calls, cost cap {ctx.plan['cost_cap_usd']} USD, formula {ctx.plan['formula']}.", "", f"Cost: {json.dumps(cost_summary(ctx))}", ""]
    return "\n".join(lines)


def ledger_entry(ctx, manifest_sha):
    rows = [{k: r[k] for k in ("card", "model", "segment", "label", "run_status")} for r in ctx.verdict["rows"] if r["segment"] == OVERALL]
    return {
        "ts": round(time.time(), 3),
        "run_id": ctx.run_id,
        "demo_only": ctx.demo,
        "marking": ctx.text["report"]["demo_banner"] if ctx.demo else None,
        "manifest_sha256": manifest_sha,
        "plan_hash": ctx.plan["plan_hash"],
        "approval": ctx.approval,
        "verdict_overall": rows,
        "excluded": ctx.excluded,
        "anchor_reductions": ctx.anchor_reductions,
        "leading_sentences": ctx.leading_log,
        "narration_status": "accepted" if ctx.narration.get("accepted") else "none",
        "narration_rejections": len(ctx.narration.get("rejections", [])),
        "real_sample": {"proposed_cards": ctx.allocation["cards"], "status": "not sent, the system does not send surveys"},
        "human_decision": None,
        "real_results": None,
        "launched": None,
        "pos": None,
        "cost": cost_summary(ctx),
    }


def write_outputs(ctx):
    out_dir = Path(ctx.results_dir or settings.RESULTS / ctx.run_id)
    man = manifest(ctx)
    sha = settings.canonical_hash(man)
    _dump(out_dir / "manifest.json", {**man, "manifest_sha256": sha})
    _dump(out_dir / "diagnostics.json", tracked_diagnostics(ctx.diagnostics))
    _dump(out_dir / "verdict.json", ctx.verdict)
    _dump(out_dir / "allocation.json", ctx.allocation)
    _dump(out_dir / "questionnaire.json", ctx.questionnaire)
    text = render_report(ctx, sha)
    report_path = out_dir / "report.md"
    report_path.write_text(text, encoding="utf-8")
    entry = ledger_entry(ctx, sha)
    ledger_path = Path(ctx.ledger_path or settings.LEDGER)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    try:
        shown = str(report_path.relative_to(settings.paths.ROOT)).replace(chr(92), "/")
    except ValueError:
        shown = str(report_path)
    return {"entry": entry, "report_path": shown}
