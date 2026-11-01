"""The stage 4 report: the action table first, in manager language, with the rule labels moved to an appendix. Rendered by code.

Only model text in it: narrator sentences that passed the number rule and exploration sentences that passed the filter, both marked as hypotheses.
"""
import json

from .. import paths
from . import action, explore, ingest, narration, report


def measure_lines(text):
    """One line per stage 4 measure, read from the result files. A missing file gives no line."""
    t = text["measures"]
    root = paths.RESULTS / "stage4"
    lines = []
    if (root / "allocation.json").exists():
        r = json.loads((root / "allocation.json").read_text(encoding="utf-8"))["reading"]
        p, q = r["panel_minus_proportional_r1_average"], r["panel_minus_reference_r1_average"]
        lines.append(t["allocation"].format(panel=f"{p['mean_diff']:+.2f}", panel_lo=f"{p['ci95'][0]:+.2f}", panel_hi=f"{p['ci95'][1]:+.2f}", ref=f"{q['mean_diff']:+.2f}", ref_lo=f"{q['ci95'][0]:+.2f}", ref_hi=f"{q['ci95'][1]:+.2f}", helps=r["panel_helps_over_proportional"], adds=r["panel_adds_over_reference"]))
    if (root / "flags.json").exists():
        s = json.loads((root / "flags.json").read_text(encoding="utf-8"))["signals"]
        names = ("terra_minus_luna", "c1_minus_c2", "repeat_sd")
        lines.append(t["flags"].format(count=sum(bool(s[n]["names_wrong_cells"]) for n in names), tl=f"{s[names[0]]['spearman']:+.2f}", cc=f"{s[names[1]]['spearman']:+.2f}", sd=f"{s[names[2]]['spearman']:+.2f}"))
    if (root / "duel_validity.json").exists():
        d = json.loads((root / "duel_validity.json").read_text(encoding="utf-8"))
        a = d["acceptance"]
        rows = d["row"]
        lines.append(t["duel"].format(positive=a["positive_keep_rate"], surrogate=max(a["surrogate_keep_rates"].values()), terra=rows["terra_C2"]["pooled"]["panel_excluded"]["keep_rate"], luna=rows["luna_C1"]["pooled"]["panel_excluded"]["keep_rate"]))
    if lines:
        lines.append(t["source"])
    return lines


def action_doc(ctx):
    rules = action.load_rules()
    roles = {c: {"role": v["role"]} for c, v in ctx.cards.items()}
    complete = bool(ctx.run_doc and ctx.run_doc.get("complete"))
    table = action.action_table(ctx.diagnostics, roles, complete, ctx.leading_log, rules, ctx.text["stage4"])
    return {"rules_version": "config/prereg_stage4.json B_rules", "action": table, "detectable": action.detectable(rules)}


def render(ctx, manifest_sha, doc):
    agent = ctx.text["report"]
    text = ctx.text["stage4"]
    guard = narration.Guard(ctx.text)
    lines = [f"manifest sha256: {manifest_sha}", ""]
    lines += [f"# {agent['demo_banner']}" if ctx.demo else "# concept audit", "", agent["never_market"], ""]
    t = text["action"]
    table = doc["action"]
    lines += [f"## {t['title']}", "", t["intro"], "", "| " + " | ".join(t["columns"]) + " |", "|---|---|---|"]
    lines += [f"| {r['card']} | {r['label']} | {r['reason']} |" for r in table["rows"]]
    lines += ["", f"### {t['order_title']}", ""] + [f"- {x}" for x in table["order"]]
    if table["order_hidden_pairs"]:
        lines.append("- " + t["order_hidden"].format(pairs="; ".join(table["order_hidden_pairs"])))
    lines += [""] + [f"- {n}" for n in table["notes"]] + [""]
    d = text["detectable"]
    lines += [f"## {d['title']}", ""] + [f"- {x}" for x in action.detectable_lines(doc["detectable"], ctx.diagnostics, text)]
    lines += ["", f"### {d['below_title']}", ""] + [f"- {x}" for x in d["below"]] + [""] + action.detectable_table(doc["detectable"], text) + [""]
    e = text["explore"]
    lines += [f"## {e['title']}", "", e["banner"], ""]
    for card, block in (ctx.explore or {}).items():
        lines += [f"### {card}", ""]
        for section, label in e["sections"].items():
            lines += [f"**{label}**", ""] + ([f"- {s}" for s in block["sections"][section]] or ["- -"]) + [""]
    r = text["real"]
    lines += [f"## {r['title']}", "", ingest.MARK_START, "", f"- {r['none']}", "", ingest.MARK_END, ""]
    lines += [f"## {text['report']['plan_title']}", "", report.allocation_section(ctx.allocation), ""]
    lines += [ctx.questionnaire["intro"], "", ctx.questionnaire["anchor_note"], ""]
    lines += [f"- {x['id']} ({x['kind']})" for x in ctx.questionnaire["items"]] + [""]
    lines += [f"- {x}" for x in ctx.questionnaire["fieldwork_rules"]] + [""]
    lines += [f"## {agent['r1_title']}", ""] + [f"- {x}" for x in text["report"]["r1_lines"]] + [""]
    m = measure_lines(text)
    if m:
        lines += [f"## {text['measures']['title']}", ""] + [f"- {x}" for x in m] + [""]
    lines += [f"## {agent['not_verified_title']}", ""] + [f"- {x}" for x in [*agent["not_verified"], *text["report"]["not_verified_extra"]]] + [""]
    lines += [f"## {agent['excluded_title']}", ""]
    lines += [f"- {x['card_id']}: {x['class']}: {x['text']}" for x in ctx.excluded] or [agent["excluded_none"]]
    lines += [""]
    if ctx.removed:
        lines += [f"## {agent['removed_title']}", ""] + [f"- {x['card_id']} ({x['by']}): {x['text']}" for x in ctx.removed] + [""]
    if ctx.leading_log:
        lines += [f"## {agent['leading_title']}", ""] + [f"- {x['card_id']} ({x['decision']}, {x['approver']}): {x['text']}" for x in ctx.leading_log] + [""]
        if any(x["decision"] == "keep" for x in ctx.leading_log):
            lines += [agent["leading_keep_note"], ""]
    if ctx.anchor_reductions:
        lines += [f"## {agent['anchor_title']}", "", agent["anchor_note"], ""] + [f"- {x['card_id']}: {', '.join(x['anchor_items'])} (left out {', '.join(x['left_out'])})" for x in ctx.anchor_reductions] + [""]
    lines += [f"## {agent['hypothesis_title']}", ""]
    accepted = ctx.narration.get("accepted")
    if accepted:
        lines += [f"- {s}" for s in guard.render(accepted, ctx.catalog)]
    else:
        lines += [guard.rejected_note if ctx.narration.get("rejections") else guard.not_called_note]
    lines += [""]
    lines += [f"## {text['report']['appendix_title']}", "", text["report"]["appendix_note"], "", ctx.verdict["header"], ""]
    lines += [f"- {s}" for s in ctx.verdict["sentences"]] + [""]
    lines += [report.verdict_table(ctx.verdict, segments=False), ""]
    lines += ["### by segment", "", report.verdict_table(ctx.verdict, segments=True), ""]
    lines += [f"### {agent['reasons_title']}", "", agent["reasons_note"], ""]
    for card, tokens in (ctx.reason_tokens or {}).items():
        lines += [f"- {card}: " + (", ".join(f"{w} {c}" for w, c in tokens) or "-")]
    lines += ["", "### diagnostics (panel internal, no truth)", "", agent["diagnostics_note"], ""]
    lines += [f"- {x}" for x in report.scale_lines(ctx)] + [""]
    lines += [report.diagnostics_section(ctx.diagnostics), ""]
    a = ctx.approval or {}
    lines += ["## approval and cost", "", f"Approved by: {a.get('approver')} at {a.get('at')}, plan {a.get('plan_hash')}.", ""]
    lines += [text["report"]["approval_person"] if a.get("channel") == "terminal" else agent["approval_note"], ""]
    lines += [f"Plan: {ctx.plan['calls_total']} calls, cost cap {ctx.plan['cost_cap_usd']} USD, formula {ctx.plan['formula']}.", "", f"Cost: {json.dumps(report.cost_summary(ctx))}", ""]
    return "\n".join(lines)


def save_explore(ctx, out_dir):
    """Sample outputs for readers, after the echo check of each card. Written once all candidates are done."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for card, block in ctx.explore.items():
        (out_dir / f"{card}.json").write_text(json.dumps(block, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "samples.md").write_text(explore.to_markdown(ctx.explore, ctx.text["stage4"]), encoding="utf-8")
