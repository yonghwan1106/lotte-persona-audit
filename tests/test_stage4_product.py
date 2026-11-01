"""The stage 4 product functions on synthetic answers: action table, detectable arithmetic, exploration, ingestion, the person's approval. No API."""
import asyncio
import io
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lotte_audit import paths
from lotte_audit.agent import action, explore, human, ingest, report4, runtime, settings, toolimpl
from lotte_audit.agent.state import AuditContext

TEXT = settings.load_text()
STAGE = action.load_text()
FULL = {**TEXT, "stage4": STAGE}
RULES = action.load_rules()
CFG = settings.load_config(check_prompt=False)
CARDS = settings.load_cards()["cards"]
TERRA, LUNA = CFG["models"]["main"]["id"], CFG["models"]["cheap"]["id"]
LIMITS = RULES["explore"]["limits"]


def block(rank, gaps, negative, noise=1.0):
    return {"rank": rank, "gaps": gaps, "negative": negative, "noise_upper": noise}


def g(mean, dist=True):
    return {"mean": mean, "ci95": [mean - 0.5, mean + 0.5], "distinguishable": dist}


def diag(terra, luna):
    return {"by_model": {TERRA: terra, LUNA: luna}}


SEP = {c: {"separated": True} for c in "ABC"}
ROLES = {"A": {"role": "candidate"}, "B": {"role": "candidate"}, "C": {"role": "candidate"}, "N": {"role": "negative_control"}, "A_para": {"role": "paraphrase"}}
ACC = lambda key: (0.5, [0.4, 0.6], 10)  # noqa: E731


def table(terra, luna, complete=True, leading=()):
    return action.action_table(diag(terra, luna), ROLES, complete, list(leading), RULES, STAGE, accuracy=ACC)


def labels(doc):
    return {r["card"]: r["action"] for r in doc["rows"]}


# ---------- action table ----------


def test_small_gaps_keep_all_candidates_with_reasons_from_code():
    gaps = {"A|B": g(-2.0), "A|C": g(-4.1), "B|C": g(-2.1)}
    doc = table(block(["C", "B", "A"], gaps, SEP), block(["C", "B", "A"], {"A|B": g(-1.9, False), "A|C": g(-4.8), "B|C": g(-2.9)}, SEP))
    assert labels(doc) == {"A": "keep", "B": "keep", "C": "keep"}
    reasons = {r["card"]: r["reason"] for r in doc["rows"]}
    assert "4.1pp" in reasons["A"] and "4.8pp" in reasons["A"] and "5pp" in reasons["A"]
    assert "\uc120\ud0dd\uc744 \ub73b\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4" in reasons["C"]
    assert [r["label"] for r in doc["rows"]] == ["\uc2e4\uce21 \ud6c4\ubcf4 \uc720\uc9c0"] * 3


def test_a_gap_past_the_limit_in_both_models_is_a_drop_proposal():
    gaps = {"A|B": g(-1.0, False), "A|C": g(-6.0), "B|C": g(-5.0)}
    doc = table(block(["C", "B", "A"], gaps, SEP), block(["C", "B", "A"], {"A|B": g(-1.0, False), "A|C": g(-5.5), "B|C": g(-4.5)}, SEP))
    assert labels(doc) == {"A": "drop", "B": "keep", "C": "keep"}


def test_the_drop_gap_must_hold_in_both_models_and_be_distinguishable():
    gaps = {"A|B": g(-1.0, False), "A|C": g(-6.0), "B|C": g(-5.0)}
    assert labels(table(block(["C", "B", "A"], gaps, SEP), block(["C", "B", "A"], {"A|B": g(-1.0, False), "A|C": g(-4.0), "B|C": g(-3.0)}, SEP)))["A"] == "keep"
    assert labels(table(block(["C", "B", "A"], gaps, SEP), block(["C", "B", "A"], {"A|B": g(-1.0, False), "A|C": g(-6.0, False), "B|C": g(-3.0)}, SEP)))["A"] == "keep"


def test_a_card_inseparable_from_the_negative_control_is_a_drop_proposal():
    neg = {"A": {"separated": False}, "B": {"separated": True}, "C": {"separated": True}}
    gaps = {"A|B": g(-1.0, False), "A|C": g(-1.0, False), "B|C": g(-1.0, False)}
    doc = table(block(["C", "B", "A"], gaps, neg), block(["C", "B", "A"], gaps, neg))
    assert labels(doc)["A"] == "drop" and labels(doc)["B"] == "keep"


def test_a_run_that_separates_nothing_tells_nothing():
    neg = {c: {"separated": False} for c in "ABC"}
    gaps = {"A|B": g(-1.0, False), "A|C": g(-1.0, False), "B|C": g(-1.0, False)}
    assert set(labels(table(block(["C", "B", "A"], gaps, neg), block(["C", "B", "A"], gaps, SEP))).values()) == {"cant_tell"}


def test_incomplete_run_opposed_models_and_a_kept_leading_sentence_are_cant_tell():
    gaps = {"A|B": g(-2.0), "A|C": g(-3.0), "B|C": g(-1.0, False)}
    assert set(labels(table(block(["C", "B", "A"], gaps, SEP), block(["C", "B", "A"], gaps, SEP), complete=False)).values()) == {"cant_tell"}
    opposed = table(block(["C", "B", "A"], gaps, SEP), block(["A", "B", "C"], {"A|B": g(2.0), "A|C": g(3.0), "B|C": g(1.0, False)}, SEP))
    assert labels(opposed)["A"] == "cant_tell"
    leading = table(block(["C", "B", "A"], gaps, SEP), block(["C", "B", "A"], gaps, SEP), leading=[{"card_id": "B", "decision": "keep"}])
    assert labels(leading)["B"] == "cant_tell" and labels(leading)["A"] == "keep"


def test_order_lines_need_both_models_past_noise_and_say_it_is_not_a_choice():
    gaps = {"A|B": g(-2.0), "A|C": g(-4.0), "B|C": g(-2.0)}
    doc = table(block(["C", "B", "A"], gaps, SEP), block(["C", "B", "A"], {"A|B": g(-1.9, False), "A|C": g(-4.8), "B|C": g(-2.9)}, SEP))
    text = " ".join(doc["order"])
    assert "\ubc29\ud5a5 \uac00\uc124" in text and "\uc120\ud0dd\uc774 \uc544\ub2d9\ub2c8\ub2e4" in text
    assert "C\uac00 A\ubcf4\ub2e4" in text and "C\uac00 B\ubcf4\ub2e4" in text
    assert doc["order_hidden_pairs"] == ["A, B"]
    assert len(doc["order"]) == 2


def test_no_pair_past_noise_gives_no_order():
    gaps = {"A|B": g(-0.5, False), "A|C": g(-0.5, False), "B|C": g(-0.5, False)}
    doc = table(block(["C", "B", "A"], gaps, SEP), block(["C", "B", "A"], gaps, SEP))
    assert doc["order"] == [STAGE["action"]["order_none"]]


def test_bands_cover_all_gaps():
    assert action.band_of(0.5)[0] == "under_1pp" and action.band_of(-4.1)[0] == "3_to_5pp" and action.band_of(5.0)[0] == "5pp_and_over"


# ---------- detectable ----------


def test_detectable_arithmetic():
    d = action.detectable(RULES)
    assert d["between_mde_pp"] == 19.8
    assert d["within_mde_pp"] == {"0.0": 14.0, "0.3": 11.7, "0.5": 9.9}
    assert d["needed"][0] == {"gap_pp": 5, "between_per_arm": 1570, "between_total": 3140, "within": {"0.0": 1570, "0.3": 1099, "0.5": 785}}
    assert d["needed"][1]["between_per_arm"] == 393 and d["needed"][1]["between_total"] == 786


def test_detectable_text_names_both_ways_out():
    joined = " ".join(STAGE["detectable"]["below"])
    assert "\uc6d0\uac00" in joined and "\ub77c\uc778" in joined and "\ud45c\ubcf8" in joined


# ---------- exploration ----------


PERSONA = "\uc11c\uc6b8\uc5d0 \uc0ac\ub294 \uc0fc\uc2ed\ub300 \uc9c1\uc7a5\uc778\uc73c\ub85c \ud0c4\uc0b0\uc74c\ub8cc\ub97c \uc77c\uc8fc\uc77c\uc5d0 \ud55c\ubc88 \ub9c8\uc2ed\ub2c8\ub2e4"
REASON = "\uac00\uaca9\uc774 \ub2e4\uc18c \ubd80\ub2f4\uc2a4\ub7fd\uace0 \ub0af\uc120 \ud5a5 \uc870\ud569\uc774\ub77c \ub9dd\uc124\uc77c \uac83 \uac19\ub2e4"
CARD_TEXT = "\uc81c\ub85c \uc288\uac70 \ud0c4\uc0b0\uc74c\ub8cc. \uccad\uadc0\uacfc \ub85c\uc988\ub9c8\ub9ac \ud5a5\uc744 \ub354\ud55c \ub9d1\uc740 \ud0c4\uc0b0"
GOOD_OBJECTION = "\uac00\uaca9\ub300\uac00 \ud3c9\uc18c \uc77c\uc0c1 \uc74c\ub8cc\ubcf4\ub2e4 \ub192\uac8c \ub290\uaef4\uc838 \ub9dd\uc124\uc77c \uc218 \uc788\ub2e4."
GOOD_QUESTION = "\uc774 \uac00\uaca9\ub300\ub77c\uba74 \uc774 \uc74c\ub8cc\ub97c \ud3c9\uc18c\uc5d0 \uace0\ub97c \uc0dd\uac01\uc774 \uc788\uc2b5\ub2c8\uae4c?"


def filtered(raw, personas=(PERSONA,), reasons=(REASON,)):
    return explore.filter_output(raw, TEXT, STAGE, LIMITS, list(personas), list(reasons), CARD_TEXT)


def test_filter_keeps_good_sentences_and_labels_each_a_hypothesis():
    got = filtered({"objections": [GOOD_OBJECTION], "attractions": [], "segment_hypotheses": [], "survey_questions": [GOOD_QUESTION]})
    assert got["sections"]["objections"] == ["\uac00\uc124: " + GOOD_OBJECTION]
    assert got["sections"]["survey_questions"] == ["\uac00\uc124: " + GOOD_QUESTION]
    assert got["dropped"] == {}


@pytest.mark.parametrize("sentence,code", [
    ("\uac00\uaca9\uc774 37% \ub192\uac8c \ub290\uaef4\uc9c8 \uc218 \uc788\ub2e4.", "number_or_claim"),
    ("\u4e09\u5341\u4e03 \ud3ec\uc778\ud2b8 \ub192\uac8c \ub290\uaef4\uc9c8 \uc218 \uc788\ub2e4.", "number_or_claim"),
    ("\ub300\ubd80\ubd84\uc774 \ub9dd\uc124\uc77c \uc218 \uc788\ub2e4.", "number_or_claim"),
    ("\ud310\ub9e4\ub7c9\uc774 \uc904 \uc218 \uc788\ub2e4.", "number_or_claim"),
    ("\ub0a8\uc131\uc774 \ub354 \ub9dd\uc124\uc77c \uc218 \uc788\ub2e4.", "blocked_pattern"),
    ("\ub9cc\uc871\uc2a4\ub7ec\uc6b4 \ub9db\uc77c \uc218 \uc788\ub2e4.", "taste"),
    ("\uc2e4\uce21 \uc804\uc6a9 \ub77c\ubca8\uc774 \ub098\uc62c \uc218 \uc788\ub2e4.", "restates_verdict"),
    ("\uac00\uaca9\ub300\uac00 \ub192\uac8c \ub290\uaef4\uc9c4\ub2e4.", "not_a_hypothesis"),
])
def test_filter_removes_by_code(sentence, code):
    got = filtered({"objections": [sentence], "attractions": [], "segment_hypotheses": [], "survey_questions": []})
    assert got["sections"]["objections"] == [] and got["dropped"] == {code: 1}


def test_a_question_must_be_a_question():
    got = filtered({"objections": [], "attractions": [], "segment_hypotheses": [], "survey_questions": ["\uc774 \uc74c\ub8cc\ub97c \uace0\ub97c \uc0dd\uac01\uc774 \uc788\ub2e4."]})
    assert got["dropped"] == {"not_a_question": 1}


def test_filter_removes_persona_and_reason_echoes_but_not_the_card_wording():
    persona_echo = "\uc0fc\uc2ed\ub300 \uc9c1\uc7a5\uc778\uc73c\ub85c \ud0c4\uc0b0\uc74c\ub8cc\ub97c \uc990\uae38 \uc218 \uc788\ub2e4."
    reason_echo = "\uac00\uaca9\uc774 \ub2e4\uc18c \ubd80\ub2f4\uc2a4\ub7fd\uace0 \ub0af\uc120 \ud5a5 \uc870\ud569\uc774\ub77c \ub9dd\uc124\uc77c \uc218 \uc788\ub2e4."
    card_echo = "\uccad\uadc0\uacfc \ub85c\uc988\ub9c8\ub9ac \ud5a5\uc744 \ub354\ud55c \ub9d1\uc740 \ud0c4\uc0b0\uc774 \ub0af\uc124 \uc218 \uc788\ub2e4."
    got = filtered({"objections": [persona_echo, reason_echo, card_echo], "attractions": [], "segment_hypotheses": [], "survey_questions": []})
    assert got["dropped"] == {"persona_echo": 1, "reason_echo": 1}
    assert len(got["sections"]["objections"]) == 1


def test_filter_cuts_to_the_limits():
    many = [f"\uac00\uaca9\ub300\uac00 \ub192\uac8c \ub290\uaef4\uc9c8 \uc218 \uc788\ub2e4 {chr(0xac00 + i)}\uc218 \uc788\ub2e4." for i in range(7)]
    got = filtered({"objections": many, "attractions": [], "segment_hypotheses": [], "survey_questions": []})
    assert len(got["sections"]["objections"]) == LIMITS["objections"] == 5
    assert got["dropped"] == {"over_limit": 2}


def test_echo_check_catches_what_slips_through():
    bad = {"objections": ["\uac00\uc124: \uc0fc\uc2ed\ub300 \uc9c1\uc7a5\uc778\uc73c\ub85c \ud0c4\uc0b0\uc74c\ub8cc\ub97c \uc990\uae38 \uc218 \uc788\ub2e4."]}
    got = explore.echo_check(bad, [PERSONA], [REASON], CARD_TEXT, "\uac00\uc124: ")
    assert got["persona_echo"] == 1 and got["passed"] is False
    assert explore.echo_check({"objections": ["\uac00\uc124: " + GOOD_OBJECTION]}, [PERSONA], [REASON], CARD_TEXT, "\uac00\uc124: ")["passed"] is True


def reason_rows(n=60):
    segments = ["19-39_m", "19-39_f", "40-59_m", "40-59_f", "60+_m", "60+_f"]
    return [{"reason": f"\uac00\uaca9\uc774 \ub2e4\ub974\uac8c \ub290\uaef4\uc9c4\ub2e4 {i}", "t2b": float(i), "segment": segments[i % 6]} for i in range(n)]


def test_prompt_lines_hold_age_and_intent_words_and_no_sex():
    lines = explore.gather(reason_rows(), STAGE["explore"])
    assert len(lines) == 60
    assert all(line.startswith("[") for line in lines)
    assert not any("\ub0a8\uc131" in x or "\uc5ec\uc131" in x or "_m" in x or "_f" in x for x in lines)
    assert any("\ub0ae\uc74c" in x for x in lines) and any("\ub192\uc74c" in x for x in lines)


class StubExplorer:
    def __init__(self, output=None):
        self.prompts = []
        self.output = output or {"objections": [GOOD_OBJECTION], "attractions": [GOOD_OBJECTION], "segment_hypotheses": [GOOD_OBJECTION], "survey_questions": [GOOD_QUESTION]}

    def __call__(self, card_id, prompt, budget, run_id):
        self.prompts.append(prompt)
        return self.output, 0.01


class ProductBackend:
    """Synthetic backend with reasons in its cache, so exploration runs without any file."""

    def __init__(self, means=None, reasons=60):
        import test_agent

        self.inner = test_agent.FakeBackend(means)
        self.reasons = reasons
        self.codes = [f"PX{i:06d}" for i in range(reasons)]

    def run(self, *a, **k):
        return self.inner.run(*a, **k)

    def load_matrices(self, *a, **k):
        return self.inner.load_matrices(*a, **k)

    def panel(self, n=None):
        segments = ["19-39_m", "19-39_f", "40-59_m", "40-59_f", "60+_m", "60+_f"]
        return {"codes": self.codes, "persona": {c: PERSONA for c in self.codes}, "segments": np.array([segments[i % 6] for i in range(len(self.codes))])}

    def items_for(self, condition, card_id, card_text, codes, personas, c0_text=None, c0_calls=0):
        return [{"condition": condition, "card": card_id, "code": c, "persona": card_text + personas[c]} for c in codes]

    def cached(self, model, item):
        return {"answer": {"p1": 0.2, "p2": 0.2, "p3": 0.2, "p4": 0.2, "p5": 0.2, "reason": REASON}}


def product_ctx(tmp_path, means=None, explorer=None):
    log_a, log_b = tmp_path / "p.jsonl", tmp_path / "m.jsonl"
    ctx = AuditContext(run_id="t4", cfg=CFG, text=FULL, budget=settings.StageBudget(5.0, (log_a, log_b)), backend=ProductBackend(means), transcript_path=tmp_path / "t.jsonl", results_dir=tmp_path / "out", ledger_path=tmp_path / "ledger.jsonl", demo=True, stage4=True, explore_dir=tmp_path / "explore")
    ctx.intake_cards = json.loads(json.dumps(CARDS))
    ctx.explorer = explorer or StubExplorer()
    return ctx


def to_diagnostics(ctx, channel=None):
    for card in CARDS:
        assert toolimpl.validate_card(ctx, card)["status"] == "ok"
    plan = toolimpl.plan_run(ctx, [TERRA, LUNA], 150, True)
    toolimpl.record_approval(ctx, plan["plan"]["plan_hash"], "tester", channel=channel)
    assert asyncio.run(toolimpl.run_panel(ctx, plan["plan"]["plan_hash"]))["status"] == "done"
    assert toolimpl.diagnose_run(ctx)["status"] == "done"


def test_explore_card_order_scope_and_what_the_model_sees(tmp_path):
    ctx = product_ctx(tmp_path)
    assert toolimpl.explore_card(ctx, "A")["reason"] == "verdict_missing"
    to_diagnostics(ctx)
    toolimpl.decide_verdict(ctx)
    assert toolimpl.explore_card(ctx, "N")["reason"] == "only_a_validated_candidate"
    out = toolimpl.explore_card(ctx, "A")
    assert out["status"] == "done" and out["echo_check_passed"] is True
    assert GOOD_OBJECTION not in json.dumps(out, ensure_ascii=False)
    assert toolimpl.explore_card(ctx, "A")["reason"] == "already_explored"
    prompt = ctx.explorer.prompts[0]
    assert PERSONA not in prompt and "PX000000" not in prompt and REASON in prompt


def test_explore_card_is_blocked_when_the_cache_lacks_reasons(tmp_path):
    ctx = product_ctx(tmp_path)
    ctx.backend = ProductBackend(reasons=10)
    to_diagnostics(ctx)
    toolimpl.decide_verdict(ctx)
    got = toolimpl.explore_card(ctx, "A")
    assert got["status"] == "blocked" and got["reason"] == "no_cached_reasons"
    assert ctx.explorer.prompts == []


def test_explore_card_does_not_exist_outside_stage_4(tmp_path):
    ctx = product_ctx(tmp_path)
    ctx.stage4 = False
    assert toolimpl.explore_card(ctx, "A")["reason"] == "not_this_stage"
    assert toolimpl.ingest_real(ctx)["reason"] == "not_this_stage"


class FakeResponse:
    def __init__(self, status=200):
        self.status_code = status

    def json(self):
        return {"status": "completed", "model": TERRA, "store": False, "usage": {"input_tokens": 100, "output_tokens": 50}, "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"objections": [GOOD_OBJECTION], "attractions": [], "segment_hypotheses": [], "survey_questions": []})}]}]}


class FakeClient:
    def __init__(self):
        self.bodies = []

    def post(self, url, headers=None, json=None):
        self.bodies.append(json)
        return FakeResponse()


def test_explorer_sends_store_false_logs_no_text_and_caches(tmp_path, monkeypatch):
    log = tmp_path / "model.jsonl"
    monkeypatch.setattr(settings, "MODEL_LOG", log)
    client = FakeClient()
    run = explore.Explorer(CFG, "not-a-key", cache_dir=tmp_path / "cache", client=client)
    budget = settings.StageBudget(1.0, (log,))
    out, cost = run("A", "prompt text", budget, "t")
    assert out["objections"] == [GOOD_OBJECTION] and cost > 0
    body = client.bodies[0]
    assert body["store"] is False and body["model"] == TERRA and "tools" not in body
    row = log.read_text(encoding="utf-8")
    assert "prompt text" not in row and "\\uac00\\uaca9" not in row
    again, cost2 = run("A", "prompt text", budget, "t")
    assert again == out and cost2 == 0.0 and len(client.bodies) == 1


def test_explorer_stops_before_a_call_past_the_budget(tmp_path, monkeypatch):
    log = tmp_path / "model.jsonl"
    monkeypatch.setattr(settings, "MODEL_LOG", log)
    client = FakeClient()
    run = explore.Explorer(CFG, "not-a-key", cache_dir=tmp_path / "cache", client=client)
    with pytest.raises(settings.BudgetExceeded):
        run("A", "prompt text", settings.StageBudget(0.0001, (log,)), "t")
    assert client.bodies == []


def test_prompt_template_holds_no_persona_slot_and_asks_for_no_number():
    template = explore.load_template()
    assert "{PERSONA}" not in template and template.count("{CARD}") == 1 and template.count("{REASONS}") == 1


# ---------- the report ----------


def finished(tmp_path, channel=None):
    ctx = product_ctx(tmp_path)
    to_diagnostics(ctx, channel)
    toolimpl.decide_verdict(ctx)
    toolimpl.allocate_real_sample(ctx)
    toolimpl.build_questionnaire(ctx)
    assert toolimpl.write_ledger(ctx)["reason"] == "explore_missing"
    for card in ("A", "B", "C"):
        assert toolimpl.explore_card(ctx, card)["status"] == "done"
    out = toolimpl.write_ledger(ctx)
    assert out["status"] == "done"
    return ctx, out, Path(out["report"]).read_text(encoding="utf-8")


def test_report_opens_with_the_action_table_and_moves_labels_to_an_appendix(tmp_path):
    _, out, text = finished(tmp_path)
    first_lines = text.splitlines()
    assert first_lines[0] == f"manifest sha256: {out['manifest_sha256']}"
    positions = [text.index(x) for x in (f"## {STAGE['action']['title']}", f"## {STAGE['detectable']['title']}", f"## {STAGE['explore']['title']}", f"## {STAGE['real']['title']}", f"## {STAGE['report']['appendix_title']}")]
    assert positions == sorted(positions)
    head = text[: positions[-1]]
    for rule_label in ("\ubc29\ud5a5\ub9cc", "\ubcf4\uc815 \ud6c4 \ucc38\uace0"):
        assert rule_label not in text.split(TEXT["report"]["not_verified_title"])[0]
    assert "\uac00\uc124: " + GOOD_OBJECTION in head
    assert STAGE["explore"]["banner"] in head
    assert PERSONA not in text and "PX000000" not in text and REASON not in text


def test_report_says_no_real_survey_and_a_stage_brief_is_no_person(tmp_path):
    _, _, text = finished(tmp_path)
    assert "\ucf58\uc149\ud2b8 \ubb38\ud56d \ub300\uacb0\uc740 \uc2e4\uc81c \uc124\ubb38\uc744 \ub9cc\ub09c \uc801\uc774 \uc5c6\uc2b5\ub2c8\ub2e4" in text
    assert TEXT["report"]["approval_note"] in text
    assert STAGE["report"]["approval_person"] not in text


def test_a_person_channel_changes_the_approval_sentence(tmp_path):
    _, _, text = finished(tmp_path, channel="terminal")
    assert STAGE["report"]["approval_person"] in text and TEXT["report"]["approval_note"] not in text


def test_ledger_entry_carries_the_action_table_and_empty_real_results(tmp_path):
    _, _, _ = finished(tmp_path)
    entry = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert entry["real_results"] is None and entry["human_decision"] is None
    assert {r["card"] for r in entry["action_table"]} == {"A", "B", "C"}
    assert (tmp_path / "out" / "action.json").exists() and (tmp_path / "explore" / "A.json").exists() and (tmp_path / "explore" / "samples.md").exists()


def test_stage_4_tools_appear_only_in_stage_4(tmp_path):
    from test_agent import ScriptedModel

    ctx = product_ctx(tmp_path)
    manager, _ = runtime.build_agents(ctx, client=None, narrator_model=ScriptedModel([]), manager_model=ScriptedModel([]))
    assert {"explore_card", "ingest_real"} <= {t.name for t in manager.tools}
    ctx.stage4 = False
    manager, _ = runtime.build_agents(ctx, client=None, narrator_model=ScriptedModel([]), manager_model=ScriptedModel([]))
    assert not {"explore_card", "ingest_real"} & {t.name for t in manager.tools}


# ---------- ingestion ----------


def write_files(tmp_path, n=200, seed=3, signal=2.0, concept=False, drop_panel=0, dup=False):
    rng = np.random.default_rng(seed)
    ages = rng.choice(ingest.AGE_BANDS, n)
    sexes = rng.choice(ingest.SEXES, n)
    ids = [f"R{i:04d}" for i in range(n)]
    if dup:
        ids[1] = ids[0]
    real = {"respondent_id": ids, "age_band": ages, "sex": sexes, "weight": rng.uniform(0.5, 2.0, n)}
    panel = {"respondent_id": ids}
    for a in ingest.ANCHORS:
        y = (rng.uniform(size=n) < 0.3).astype(int)
        real[a] = y
        panel[f"p_{a}"] = 1 / (1 + np.exp(-(0.4 + signal * (2 * y - 1) + rng.normal(0, 0.3, n))))
    if concept:
        y5 = rng.integers(1, 6, n)
        real["concept_A"] = y5
        panel["p_concept_A"] = np.clip((y5 >= 4) * 0.8 + 0.1, 0, 1)
    real_path, panel_path = tmp_path / "real.csv", tmp_path / "panel.csv"
    pd.DataFrame(real).to_csv(real_path, index=False)
    pd.DataFrame(panel).iloc[drop_panel:].to_csv(panel_path, index=False)
    return real_path, panel_path


def run_dir(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"run_id": "r", "manifest_sha256": "abc"}), encoding="utf-8")
    (d / "report.md").write_text(f"head\n{ingest.MARK_START}\nold\n{ingest.MARK_END}\ntail\n", encoding="utf-8")
    return d


def validity(tmp_path, passed=True, surrogate=0.05):
    doc = {"acceptance": {"passed": passed, "label": "decision_rule" if passed else "health_check", "surrogate_keep_rates": {"s": surrogate}, "positive_keep_rate": 0.9}, "row": {"terra_C2": {"pooled": {"panel_excluded": {"keep_rate": 0.3, "false_keep_rate": 0.4, "missed_keep_rate": 0.6}}}, "luna_C1": {"pooled": {"panel_excluded": {"keep_rate": 0.02, "false_keep_rate": 0.1, "missed_keep_rate": 0.9}}}}}
    v = tmp_path / "v.json"
    v.write_text(json.dumps(doc), encoding="utf-8")
    return v


def run_ingest(tmp_path, real, panel, d, ledger, label, who="tester", model=TERRA, condition="C2", **kw):
    return ingest.ingest(real, panel, d, ledger, label, who, STAGE, model, condition, validity_path=validity(tmp_path), seed_path=tmp_path / "none.json", post_hoc_path=tmp_path / "none2.json", **kw)


def test_ingest_writes_the_report_block_the_ledger_and_real_results(tmp_path):
    real, panel = write_files(tmp_path)
    d = run_dir(tmp_path)
    doc = run_ingest(tmp_path, real, panel, d, tmp_path / "ledger.jsonl", ingest.STANDIN_LABEL)
    assert doc["duel_outcome"] == "keep" and doc["source_label"] == ingest.STANDIN_LABEL
    assert doc["is_real_concept_survey"] is False and doc["concept_duel"] == "not_run_no_real_concept_answers"
    text = (d / "report.md").read_text(encoding="utf-8")
    assert "old" not in text and text.startswith("head") and text.endswith("tail\n")
    assert ingest.STANDIN_LABEL in text and "\uc2e4\uc81c \uc124\ubb38\uc744 \ub9cc\ub09c \uc801\uc774 \uc5c6\uc2b5\ub2c8\ub2e4" in text and "tester" in text
    row = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8"))
    assert row["kind"] == "real_results" and row["approver"] == "tester" and row["manifest_sha256"] == "abc"
    assert row["real_results"]["duel_outcome"] == "keep" and row["human_decision"] is None
    blob = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8") + (d / "real_results.json").read_text(encoding="utf-8") + text
    assert "R0001" not in blob


def test_ingest_drops_a_panel_with_no_signal_and_says_why(tmp_path):
    real, panel = write_files(tmp_path, signal=0.0)
    d = run_dir(tmp_path)
    doc = run_ingest(tmp_path, real, panel, d, tmp_path / "l.jsonl", "field survey")
    assert doc["duel_outcome"] == "drop"
    assert STAGE["real"]["reason_drop"] in doc["lines"]


def test_a_concept_column_runs_its_own_duel_and_only_a_real_label_counts_as_a_survey(tmp_path):
    real, panel = write_files(tmp_path, concept=True)
    d = run_dir(tmp_path)
    doc = run_ingest(tmp_path, real, panel, d, tmp_path / "l.jsonl", "field survey")
    assert doc["concept_duel"] == "ran" and doc["is_real_concept_survey"] is True and doc["concepts"]["A"]["keep"] is True
    d2 = tmp_path / "second"
    d2.mkdir()
    (d2 / "manifest.json").write_text(json.dumps({"run_id": "r", "manifest_sha256": "abc"}), encoding="utf-8")
    (d2 / "report.md").write_text(f"{ingest.MARK_START}\n{ingest.MARK_END}\n", encoding="utf-8")
    doc2 = run_ingest(tmp_path, real, panel, d2, tmp_path / "l.jsonl", ingest.STANDIN_LABEL)
    assert doc2["is_real_concept_survey"] is False


def test_a_failed_acceptance_keeps_its_label_in_the_record(tmp_path):
    got = ingest.grade(STAGE, "terra_C2", validity(tmp_path, passed=False, surrogate=0.3), tmp_path / "none.json", tmp_path / "none2.json")
    assert got["label"] == "health_check" and "health_check" in got["lines"][0]


def test_seed_failures_are_named_next_to_a_passed_acceptance(tmp_path):
    seeds = tmp_path / "s.json"
    seeds.write_text(json.dumps({"runs": {"a": {"acceptance_passed": False}, "b": {"acceptance_passed": True}}}), encoding="utf-8")
    got = ingest.grade(STAGE, "terra_C2", validity(tmp_path), seeds, tmp_path / "none2.json")
    assert got["seed_runs_failed"] == 1
    assert any("2\uac1c\ub85c" in x and "1\uac1c" in x for x in got["lines"])


@pytest.mark.parametrize("kw,needle", [({"dup": True}, "twice"), ({"drop_panel": 5}, "no panel value"), ({"n": 20}, "at least")])
def test_ingest_refuses_files_it_cannot_read_as_stated(tmp_path, kw, needle):
    real, panel = write_files(tmp_path, **kw)
    d = run_dir(tmp_path)
    with pytest.raises(ingest.IngestRefused, match=needle):
        run_ingest(tmp_path, real, panel, d, tmp_path / "l.jsonl", "field survey")
    assert not (tmp_path / "l.jsonl").exists() and "old" in (d / "report.md").read_text(encoding="utf-8")


def test_ingest_refuses_a_row_level_file_in_a_tracked_folder():
    with pytest.raises(ingest.IngestRefused, match="tracked folder"):
        ingest.check_location(paths.ROOT / "README.md")


def test_ingest_needs_a_name_and_a_source(tmp_path):
    real, panel = write_files(tmp_path)
    with pytest.raises(ingest.IngestRefused):
        ingest.ingest(real, panel, run_dir(tmp_path), tmp_path / "l.jsonl", "field survey", " ", STAGE, TERRA, "C2")


def test_a_bad_anchor_value_is_refused(tmp_path):
    real, panel = write_files(tmp_path)
    df = pd.read_csv(real)
    df.loc[0, "ever"] = 2
    df.to_csv(real, index=False)
    with pytest.raises(ingest.IngestRefused, match="0 or 1"):
        ingest.read_real(real)


def test_ingest_tool_takes_its_files_from_the_application_only(tmp_path):
    ctx = product_ctx(tmp_path)
    assert toolimpl.ingest_real(ctx)["reason"] == "no_real_file_registered_by_the_system"
    ctx.real_input = {"real_csv": "x", "panel_csv": "y", "source_label": "z", "approver": "w"}
    assert toolimpl.ingest_real(ctx)["reason"] == "write_ledger_first"


# ---------- the person's approval ----------


PLAN = {"plan_hash": "abcdef0123456789", "calls_total": 10, "cost_cap_usd": 0.1, "formula": "f", "cards": ["A"]}


class Tty(io.StringIO):
    def isatty(self):
        return True


def test_approval_refuses_without_a_terminal():
    with pytest.raises(human.NotApproved, match="interactive terminal"):
        human.typed_approval(PLAN, stdin=io.StringIO(""), out=lambda *_: None)


def test_the_null_device_is_no_terminal(tmp_path):
    with open(os.devnull) as null:
        assert human.is_real_terminal(null) is False
    with pytest.raises(human.NotApproved, match="interactive terminal"):
        with open(os.devnull) as null:
            human.typed_approval(PLAN, stdin=null, out=lambda *_: None)


def test_no_input_is_no_approval():
    def eof(_prompt):
        raise EOFError

    with pytest.raises(human.NotApproved, match="no input"):
        human.typed_approval(PLAN, stdin=Tty(), read=eof, out=lambda *_: None)


def test_approval_needs_a_name_and_the_right_hash():
    answers = iter(["", "abcdef012345"])
    with pytest.raises(human.NotApproved, match="no name"):
        human.typed_approval(PLAN, stdin=Tty(), read=lambda _: next(answers), out=lambda *_: None)
    answers = iter(["someone", "wrong"])
    with pytest.raises(human.NotApproved, match="does not match"):
        human.typed_approval(PLAN, stdin=Tty(), read=lambda _: next(answers), out=lambda *_: None)
    answers = iter(["someone", "abcdef012345"])
    assert human.typed_approval(PLAN, stdin=Tty(), read=lambda _: next(answers), out=lambda *_: None) == "someone"


def test_the_small_run_goes_through_the_fixed_tool_order_after_approval(tmp_path):
    ctx = product_ctx(tmp_path)
    for card in ("A", "A_para", "B", "C", "N"):
        assert toolimpl.validate_card(ctx, card)["status"] == "ok"
    plan = toolimpl.plan_run(ctx, [TERRA, LUNA], 100, False)
    assert plan["status"] == "accepted"
    assert asyncio.run(toolimpl.run_panel(ctx, plan["plan"]["plan_hash"]))["reason"] == "no_human_approval_recorded"
    toolimpl.record_approval(ctx, plan["plan"]["plan_hash"], "someone", channel=human.CHANNEL)
    assert ctx.approval["channel"] == human.CHANNEL
    got = asyncio.run(human.run_after_approval(ctx))
    assert got["status"] == "done"
    assert STAGE["report"]["approval_person"] in (tmp_path / "out" / "report.md").read_text(encoding="utf-8")


def test_stage_config_is_separate():
    doc = json.loads(settings.STAGE4_CONFIG.read_text(encoding="utf-8"))
    assert doc["budget_usd"] == 3.0 and doc["stage_dir"] == "runs/stage4" and doc["results_dir"] == "results/stage4"


def test_runner_refuses_new_panel_calls_for_the_demo_by_default():
    text = (paths.ROOT / "src" / "stage4_run.py").read_text(encoding="utf-8")
    assert "agent_run.BACKEND_CLASS = fixstage.CacheOnlyBackend" in text
    assert text.count("panel_module.RealBackend") == 1


def test_new_product_sources_are_ascii():
    for rel in ("src/stage4_run.py", "src/stage4_sensitivity.py", "src/stage4_posthoc.py", "src/lotte_audit/duel_units.py", "tests/test_stage4_policy.py", "src/lotte_audit/agent/action.py", "src/lotte_audit/agent/explore.py", "src/lotte_audit/agent/human.py", "src/lotte_audit/agent/ingest.py", "src/lotte_audit/agent/report4.py", "tests/test_stage4_product.py"):
        (paths.ROOT / rel).read_bytes().decode("ascii")


# ---------- what was committed ----------


def test_the_stand_in_ingest_gives_the_same_duel_as_the_validity_study_on_that_draw():
    stored_doc = paths.RESULTS / "stage4" / "demo7" / "real_results.json"
    if not stored_doc.exists() or not paths.SAV_2025.exists() or not (paths.ROOT / "runs" / "main" / "key.csv").exists():
        pytest.skip("files not present")
    import stage4_measures as sm
    from lotte_audit import stage4

    doc = json.loads(stored_doc.read_text(encoding="utf-8"))
    assert doc["source_label"] == ingest.STANDIN_LABEL and doc["is_real_concept_survey"] is False
    s = sm.setup()
    draws = sm.stage2_draws(s, 0, "row")
    index = RULES["ingest"]["standin_draw_index"]
    raw = stage4.duel_study(s["ctx"], {"terra": sm.stored(s, sm.TERRA, "C2")}, [draws[index]], sm.A3_PLAN["fold_seed"])
    assert raw["terra"]["pooled"]["keep"][0] == (doc["decision"] == "keep")
    assert raw["terra"]["pooled"]["improvement"][0] == pytest.approx(doc["anchors"]["pooled"]["mean_improvement"], abs=1e-4)


def test_demo7_keeps_the_demo6_verdict_and_reads_no_new_panel_answer():
    root = paths.RESULTS / "stage4" / "demo7"
    if not root.exists():
        pytest.skip("demo7 not run")
    a = json.loads((root / "verdict.json").read_text(encoding="utf-8"))
    b = json.loads((paths.RESULTS / "fix_stage" / "demo6" / "verdict.json").read_text(encoding="utf-8"))
    assert a["rows"] == b["rows"]
    ad = json.loads((root / "diagnostics.json").read_text(encoding="utf-8"))
    bd = json.loads((paths.RESULTS / "fix_stage" / "demo6" / "diagnostics.json").read_text(encoding="utf-8"))
    assert ad["by_model"] == bd["by_model"]
    summary = paths.RESULTS / "stage4" / "run_summary.json"
    if summary.exists():
        panel = json.loads(summary.read_text(encoding="utf-8"))["panel"]
        assert not panel.get("models") or all(m.get("attempts", 0) == 0 for m in panel["models"].values())


def test_no_person_is_claimed_for_the_demo_or_the_stand_in():
    ledger = paths.RESULTS / "stage4" / "ledger.jsonl"
    if not ledger.exists():
        pytest.skip("no ledger")
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    for row in rows:
        if row.get("run_id") in ("demo7", "demo8"):
            who = row.get("approver") or (row.get("approval") or {}).get("approver")
            assert "no person" in who
            assert (row.get("approval") or {}).get("channel") is None


def committed_blob():
    roots = [paths.RESULTS / "stage4", paths.RESULTS / "explore"]
    return "\n".join(p.read_text(encoding="utf-8") for r in roots if r.exists() for p in r.rglob("*") if p.is_file() and p.suffix in (".json", ".md", ".jsonl"))


def test_stage_4_results_hold_no_respondent_code():
    key_path = paths.ROOT / "runs" / "main" / "key.csv"
    if not key_path.exists() or not (paths.RESULTS / "stage4").exists():
        pytest.skip("files not present")
    codes = {line.split(",")[2] for line in key_path.read_text(encoding="utf-8").splitlines()[1:]}
    assert not set(re.findall(r"\b[A-Z2-9]{8}\b", committed_blob())) & codes


def test_explore_samples_hold_no_persona_text_and_no_number():
    root = paths.RESULTS / "explore"
    persona_path = paths.ROOT / "runs" / "main" / "inputs" / "personas.jsonl"
    if not root.exists() or not persona_path.exists():
        pytest.skip("files not present")
    personas = [json.loads(x)["persona"] for x in persona_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    guard_text = explore.narration.Guard(TEXT)
    runs = set().union(*[explore.runs_of(p, explore.PERSONA_RUN) for p in personas])
    cards = settings.load_cards()["cards"]
    for path in root.rglob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        card = explore.runs_of(cards[doc["card"]]["description"], explore.PERSONA_RUN)
        for items in doc["sections"].values():
            for sentence in items:
                assert sentence.startswith("\uac00\uc124: ")
                body = sentence[len("\uac00\uc124: ") :]
                assert not guard_text.check_sentence(body, set()), sentence
                assert not explore.shared_run(body, runs, card, explore.PERSONA_RUN), sentence
