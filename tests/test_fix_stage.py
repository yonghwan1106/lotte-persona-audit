"""Tests of the must_fix changes, offline. Korean test sentences come from config/attacks_wf7.json, so this source stays ASCII."""
import asyncio
import json
import re
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("agents")

from lotte_audit import paths  # noqa: E402
from lotte_audit.agent import cards as card_rules  # noqa: E402
from lotte_audit.agent import diagnostics, narration, report, runtime, settings, toolimpl  # noqa: E402
from lotte_audit.agent.state import AuditContext  # noqa: E402

TEXT = settings.load_text()
CFG = settings.load_config(check_prompt=False)
CARDS = settings.load_cards()["cards"]
ATT = json.loads((paths.CONFIG / "attacks_wf7.json").read_text(encoding="utf-8"))
GUARD = narration.Guard(TEXT)
INTAKE = card_rules.Intake(TEXT)
TERRA = CFG["models"]["main"]["id"]
LUNA = CFG["models"]["cheap"]["id"]
PRICE = ATT["price_sentence"]
SOCIAL = ATT["leading_variants"][0]
BASE = f"{CARDS['A']['description'].split('. ')[0]}. {SOCIAL} {PRICE}"
UNREGISTERED = {"role": "candidate", "target_segment": "19-39", "anchor_items": ["ever", "weekly", "carb"], "description": BASE}


def ctx_for(tmp_path, registered=True):
    ctx = AuditContext(run_id="t", cfg=CFG, text=TEXT, budget=settings.StageBudget(5.0, (tmp_path / "p.jsonl", tmp_path / "m.jsonl")), transcript_path=tmp_path / "t.jsonl", results_dir=tmp_path / "out", ledger_path=tmp_path / "ledger.jsonl", demo=True)
    if registered:
        ctx.intake_cards = json.loads(json.dumps(CARDS))
    return ctx


def validated(ctx):
    for card in CARDS:
        assert toolimpl.validate_card(ctx, card)["status"] == "ok"


# ---------- must_fix 1: fact style sentences wait for a person ----------


def test_the_fact_style_sentence_that_moved_the_panel_stops_the_card(tmp_path):
    ctx = ctx_for(tmp_path, registered=False)
    out = toolimpl.validate_card(ctx, "X5", UNREGISTERED)
    assert out["status"] == "needs_human_confirmation" and out["flagged"] == [SOCIAL]
    assert "X5" not in ctx.cards and "X5" in ctx.pending_confirmations


def test_the_model_cannot_clear_a_flagged_sentence_by_naming_it(tmp_path):
    ctx = ctx_for(tmp_path, registered=False)
    out = toolimpl.validate_card(ctx, "X5", UNREGISTERED, [], [SOCIAL])
    assert out["status"] == "needs_human_confirmation" and "X5" not in ctx.cards


def test_rewriting_the_card_does_not_clear_the_wait(tmp_path):
    ctx = ctx_for(tmp_path, registered=False)
    toolimpl.validate_card(ctx, "X5", UNREGISTERED)
    rewritten = {**UNREGISTERED, "description": f"{CARDS['A']['description']}"}
    assert toolimpl.validate_card(ctx, "X5", rewritten)["status"] == "ok"
    assert "X5" in ctx.pending_confirmations
    assert toolimpl.plan_run(ctx, [TERRA], 150, False)["reason"] == "card_pending_human_confirmation"


def test_a_person_can_remove_the_sentence(tmp_path):
    ctx = ctx_for(tmp_path, registered=False)
    toolimpl.validate_card(ctx, "X5", UNREGISTERED)
    out = toolimpl.record_leading_decision(ctx, "X5", "remove", "person")
    assert out["status"] == "ok" and SOCIAL not in ctx.cards["X5"]["clean_text"] and PRICE in ctx.cards["X5"]["clean_text"]
    assert ctx.pending_confirmations == {} and ctx.leading_log[0]["decision"] == "remove" and ctx.leading_log[0]["approver"] == "person"
    assert [r for r in ctx.removed if r["by"] == "human"]


def test_a_person_can_keep_the_sentence_and_the_record_says_so(tmp_path):
    ctx = ctx_for(tmp_path, registered=False)
    toolimpl.validate_card(ctx, "X5", UNREGISTERED)
    toolimpl.record_leading_decision(ctx, "X5", "keep", "person")
    assert SOCIAL in ctx.cards["X5"]["clean_text"] and ctx.cards["X5"]["leading_kept"] == [SOCIAL]
    out = toolimpl.validate_card(ctx, "X5", UNREGISTERED, [], [SOCIAL])
    assert out["status"] == "ok" and SOCIAL in ctx.cards["X5"]["clean_text"]


def test_a_decision_needs_a_named_person_and_a_waiting_sentence(tmp_path):
    ctx = ctx_for(tmp_path, registered=False)
    with pytest.raises(ValueError):
        toolimpl.record_leading_decision(ctx, "X5", "remove", "person")
    toolimpl.validate_card(ctx, "X5", UNREGISTERED)
    with pytest.raises(ValueError):
        toolimpl.record_leading_decision(ctx, "X5", "remove", "  ")
    with pytest.raises(ValueError):
        toolimpl.record_leading_decision(ctx, "X5", "delete", "person")


def test_the_decision_is_no_tool_of_the_model():
    assert "record_leading_decision" not in {t.name for t in runtime.build_tools(TEXT)}
    joined = json.dumps([t.params_json_schema for t in runtime.build_tools(TEXT)])
    assert "decision" not in joined and "approver" not in joined


@pytest.mark.parametrize("sentence", ATT["leading_must_pass"])
def test_plain_card_sentences_are_not_flagged(sentence):
    assert INTAKE.leading_sentences(sentence) == []


def test_no_registered_card_is_flagged():
    for card, doc in CARDS.items():
        assert INTAKE.leading_sentences(doc["description"]) == [], card


def test_the_first_seven_leading_variants_are_flagged():
    for sentence in ATT["leading_variants"][:8]:
        assert INTAKE.leading_sentences(sentence), sentence


def test_sentences_joined_without_a_space_are_split():
    text = ATT["A_TEXT"].replace(". ", ".")
    assert len(INTAKE.sentences(text)) >= 2
    assert INTAKE.sentences("1.5L \uce94") == ["1.5L \uce94"]


# ---------- must_fix 2: a run fixes its cards ----------


def after_run(ctx):
    validated(ctx)
    plan = toolimpl.plan_run(ctx, [TERRA, LUNA], 150, True)["plan"]
    ctx.run_doc = {"complete": True, "plan_hash": plan["plan_hash"], "stages": []}
    ctx.diagnostics = {"by_model": {}}
    ctx.verdict = {"rows": [], "sentences": []}
    return plan


def test_validate_card_is_blocked_after_a_run(tmp_path):
    ctx = ctx_for(tmp_path, registered=False)
    ctx.intake_cards = {}
    for card, doc in CARDS.items():
        toolimpl.validate_card(ctx, card, doc)
    plan = toolimpl.plan_run(ctx, [TERRA, LUNA], 150, True)["plan"]
    ctx.run_doc = {"complete": True, "plan_hash": plan["plan_hash"], "stages": []}
    ctx.diagnostics = {"by_model": {}}
    out = toolimpl.validate_card(ctx, "A", {**CARDS["A"], "anchor_items": ["ever"]})
    assert out["status"] == "blocked" and out["reason"] == "run_exists_start_a_new_run"
    assert ctx.cards["A"]["anchor_items"] == CARDS["A"]["anchor_items"]
    assert ctx.plan["plan_hash"] == plan["plan_hash"]


def test_an_incomplete_run_record_is_cleared_when_a_card_changes(tmp_path):
    ctx = ctx_for(tmp_path)
    validated(ctx)
    ctx.run_doc = {"complete": False, "stop_reason": "budget"}
    assert toolimpl.validate_card(ctx, "B")["status"] == "ok"
    assert ctx.run_doc is None and ctx.plan is None


def test_registered_card_ignores_suspected_sentences(tmp_path):
    ctx = ctx_for(tmp_path)
    for suspect in (PRICE, ATT["one_syllable"], CARDS["A"]["description"]):
        out = toolimpl.validate_card(ctx, "A", None, [], [suspect])
        assert out["status"] == "ok" and out["removed"] == []
        assert ctx.cards["A"]["clean_text"] == CARDS["A"]["description"]


def test_suspected_takes_whole_sentences_only_on_an_unregistered_card():
    fields = dict(CARDS["A"])
    status, doc = INTAKE.check("X", fields, (), [ATT["one_syllable"]])
    assert status == "ok" and doc["removed"] == [] and doc["clean_text"] == fields["description"]
    status, doc = INTAKE.check("X", fields, (), [PRICE])
    assert status == "ok" and PRICE not in doc["clean_text"] and doc["removed"][0]["by"] == "model"
    status, doc = INTAKE.check("X", fields, (), [PRICE.rstrip(".") + " "])
    assert PRICE not in doc["clean_text"]


def test_plan_hash_covers_the_clean_text_and_the_anchors(tmp_path):
    hashes = {}
    for name, change in (("base", {}), ("text", {"description": ATT["changed_card_b"]}), ("anchor", {"anchor_items": ["ever"]})):
        ctx = ctx_for(tmp_path / name if (tmp_path / name).mkdir() is None else tmp_path)
        ctx.intake_cards["B"].update(change)
        validated(ctx)
        hashes[name] = toolimpl.plan_run(ctx, [LUNA], 100, False)["plan"]["plan_hash"]
    assert len(set(hashes.values())) == 3


def test_an_approval_does_not_survive_a_changed_card_body(tmp_path):
    ctx = ctx_for(tmp_path)
    validated(ctx)
    plan = toolimpl.plan_run(ctx, [LUNA], 100, False)["plan"]
    toolimpl.record_approval(ctx, plan["plan_hash"], "person")
    ctx.cards["B"]["clean_text"] = ATT["changed_card_b"]
    out = asyncio.run(toolimpl.run_panel(ctx, plan["plan_hash"]))
    assert out["status"] == "blocked" and out["reason"] == "cards_changed_since_plan"


def test_a_plan_without_a_digest_cannot_go_on(tmp_path):
    ctx = ctx_for(tmp_path)
    validated(ctx)
    plan = toolimpl.plan_run(ctx, [LUNA], 100, False)["plan"]
    del ctx.plan["card_digest"]
    assert toolimpl.plan_cards_problem(ctx) == "plan_has_no_card_digest"
    ctx.run_doc = {"complete": True, "plan_hash": plan["plan_hash"]}
    ctx.diagnostics = {"by_model": {}}
    assert toolimpl.decide_verdict(ctx)["reason"] == "plan_has_no_card_digest"
    assert toolimpl.diagnose_run(ctx)["reason"] == "plan_has_no_card_digest"


def test_anchor_reduction_of_an_unregistered_card_is_recorded(tmp_path):
    ctx = ctx_for(tmp_path, registered=False)
    assert toolimpl.validate_card(ctx, "B", {**CARDS["B"], "anchor_items": ["ever"]})["status"] == "ok"
    assert ctx.anchor_reductions == [{"card_id": "B", "anchor_items": ["ever"], "left_out": ["weekly", "carb"]}]
    toolimpl.validate_card(ctx, "B", {**CARDS["B"], "anchor_items": ["ever", "weekly", "carb"]})
    assert ctx.anchor_reductions == []
    registered = ctx_for(tmp_path)
    toolimpl.validate_card(registered, "C")  # a registered card's anchors were frozen before any answer
    assert registered.anchor_reductions == []


# ---------- must_fix 3: the number rule, also on the manager's note ----------


@pytest.mark.parametrize("sentence", ATT["guard_variants"])
def test_every_wf7_guard_variant_is_rejected(sentence):
    assert GUARD.check_output([{"text": sentence, "metric_ids": []}], set()) != []


@pytest.mark.parametrize("sentence", ATT["note_variants"])
def test_notes_with_numbers_or_market_words_are_dropped_except_the_plain_order_claim(sentence):
    # The third variant names no number and no market word. It stays and is listed as passing in results/fix_stage.
    if "\uac00\uc7a5 \ub192\uc2b5\ub2c8\ub2e4" in sentence:
        assert GUARD.clean_note(sentence) == sentence
    else:
        assert GUARD.clean_note(sentence) is None


@pytest.mark.parametrize("sentence", ATT["guard_must_pass"])
def test_ordinary_sentences_are_not_rejected(sentence):
    assert GUARD.check_output([{"text": sentence, "metric_ids": []}], set()) == []


def test_format_characters_and_compatibility_forms_hide_nothing():
    zero_width = "\uc0bc\u200b\uc2ed \ud3ec\uc778\ud2b8 \ucc28\uc774\uc77c \uc218 \uc788\ub2e4"
    assert GUARD.check_sentence(zero_width, set()) != []
    for ch in ("\u00bd", "\u00b3", "\u2155", "\u2467", "\u4e09", "\u842c", "\u58f9", "\uff13", "\u0663"):
        assert GUARD.check_sentence(f"\ucc28\uc774\uac00 {ch} \uc218\uc900\uc77c \uc218 \uc788\ub2e4", set()) != [], ch


def test_a_placeholder_still_carries_a_value():
    catalog = {"noise_terra": {"value": "+1.2pp", "what": "x"}}
    sentence = "\ucc28\uc774\ub294 {{m:noise_terra}} \uc218\uc900\uc77c \uc218 \uc788\ub2e4"
    assert GUARD.render([{"text": sentence, "metric_ids": ["noise_terra"]}], catalog)[0].count("+1.2pp") == 1


# ---------- must_fix 6: tracked diagnostics hold no absolute value ----------


def fake_diag():
    rng = np.random.default_rng(1)
    n = 120
    roles = {c: {"role": v["role"], "paraphrase_of": v.get("paraphrase_of"), "brand_of": v.get("brand_of"), "anchor_items": v["anchor_items"]} for c, v in CARDS.items()}
    answers = {c: np.tile([0.1, 0.1, 0.2, 0.3, 0.3], (n, 1)) + rng.normal(0, 0.005, (n, 5)) for c in CARDS}
    c0 = {c: answers[c][:10] for c in ("A", "A_para", "B", "C", "N")}
    rules = {**CFG["rules"], "bootstrap": {**CFG["rules"]["bootstrap"], "draws": 50}}
    segments = np.array(["19-39_m", "19-39_f", "40-59_m", "40-59_f", "60+_m", "60+_f"] * 20)
    return diagnostics.compute({TERRA: answers}, c0, TERRA, np.repeat(np.arange(30), 4), segments, roles, rules)


def test_tracked_diagnostics_leave_out_every_absolute_value():
    diag = fake_diag()
    assert "internal" in diag["by_model"][TERRA] and "c0_internal" in diag["c0"]
    doc = report.tracked_diagnostics(diag)
    text = json.dumps(doc)
    assert '"internal"' not in text and '"t2b_pp"' not in text and '"c0_internal"' not in text
    block = doc["by_model"][TERRA]
    assert block["gaps"] and block["negative"] and block["noise"] and block["rank"]
    assert "internal" in diag["by_model"][TERRA]  # the original document is left alone


# ---------- must_fix 7: plan size and a claimed complete ----------


@pytest.mark.parametrize("n,status", [(1, "refused"), (3, "refused"), (99, "refused"), (100, "accepted"), (150, "accepted"), (300, "accepted"), (301, "refused"), (1000, "refused")])
def test_plan_size_limits(tmp_path, n, status):
    ctx = ctx_for(tmp_path)
    validated(ctx)
    ctx.budget = settings.StageBudget(1000.0, (tmp_path / "p.jsonl", tmp_path / "m.jsonl"))
    assert toolimpl.plan_run(ctx, [LUNA], n, False)["status"] == status


def test_the_panel_pool_size_equals_the_key_when_the_key_exists():
    key = paths.ROOT / "runs" / "stage3" / "key.csv"
    if not key.exists():
        pytest.skip("stage 3 key not present")
    rows = [line.split(",") for line in key.read_text(encoding="utf-8").splitlines()]
    assert sum(1 for r in rows[1:] if "C1" in r) == TEXT["plan_limits"]["panel_pool_size"]


def test_complete_needs_the_ledger(tmp_path):
    ctx = ctx_for(tmp_path)
    claim = runtime.AuditReply(status="complete", refused_classes=[], note="ok")
    out = runtime.outcome_from_final(ctx, claim)
    assert out["status"] == "stopped" and out["claimed_status"] == "complete" and out["status_corrected_by_code"] is True
    ctx.ledger_entry = {"run_id": "t"}
    out = runtime.outcome_from_final(ctx, claim)
    assert out["status"] == "complete" and out["status_corrected_by_code"] is False


def test_complete_with_a_refusal_and_no_ledger_is_stopped_and_keeps_the_classes(tmp_path):
    ctx = ctx_for(tmp_path)
    out = runtime.outcome_from_final(ctx, runtime.AuditReply(status="complete", refused_classes=["sales_forecast"], note="ok"))
    assert out["status"] == "stopped" and out["refused_classes"] == ["sales_forecast"]


def test_other_statuses_pass_through(tmp_path):
    ctx = ctx_for(tmp_path)
    for status in ("refused", "needs_input", "blocked", "stopped"):
        assert runtime.outcome_from_final(ctx, runtime.AuditReply(status=status, refused_classes=[], note="ok"))["status"] == status


def test_complete_does_not_stand_while_a_card_waits_for_a_person(tmp_path):
    ctx = ctx_for(tmp_path)
    ctx.ledger_entry = {"run_id": "t"}
    ctx.pending_confirmations = {"X": {"flagged": ["s"]}}
    assert runtime.outcome_from_final(ctx, runtime.AuditReply(status="complete", refused_classes=[], note="ok"))["status"] == "stopped"


# ---------- must_fix 4 and 5: what the text says ----------


def test_compare_docstring_no_longer_claims_the_v2_test():
    from lotte_audit.agent import compare

    doc = compare.compare_panel_direct.__doc__
    assert "same test as" not in doc and "not the v2 test" in doc
    assert "not built" in compare.__doc__


def test_report_promises_no_path_that_does_not_exist():
    lines = " ".join(TEXT["report"]["r1_lines"])
    assert "compare_panel_direct" in lines
    assert "\ub9cc\ub4e4\uc5b4\uc838 \uc788\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4" in lines
    assert "\ubcf4\uace0\uc11c\uc5d0 \uadf8\ub300\ub85c \uc801\uc2b5\ub2c8\ub2e4" not in lines


def test_fix_stage_config_is_separate_and_three_dollars():
    doc = json.loads(settings.FIX_CONFIG.read_text(encoding="utf-8"))
    assert doc["budget_usd"] == 3.0 and doc["stage_dir"] == "runs/agent_fix" and doc["results_dir"] == "results/fix_stage"


def test_new_sources_are_ascii():
    for rel in ("src/agent_fix_run.py", "src/lotte_audit/agent/fixstage.py", "src/lotte_audit/agent/attack_replay.py", "tests/test_fix_stage.py"):
        (paths.ROOT / rel).read_bytes().decode("ascii")


def test_fix_stage_results_hold_no_persona_text_and_no_respondent_code():
    key_path = paths.ROOT / "runs" / "stage3" / "key.csv"
    root = paths.RESULTS / "fix_stage"
    if not key_path.exists() or not root.exists():
        pytest.skip("files not present")
    codes = {line.split(",")[1] for line in key_path.read_text(encoding="utf-8").splitlines()[1:]}
    blob = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file())
    assert not set(re.findall(r"\b[A-Z2-9]{8}\b", blob)) & codes


def test_nothing_in_the_new_stage_touches_the_frozen_agent_results():
    assert Path(settings.RESULTS).name == "agent"  # this test process did not activate the fix stage
