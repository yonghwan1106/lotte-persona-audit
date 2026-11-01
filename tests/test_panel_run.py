"""Tests for the gate runner. All HTTP is mocked: these tests never reach the API and never read answers."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import httpx
import numpy as np
import pytest
from conftest import answers_from

import gate_explore
import panel_run
from lotte_audit import paths

ROOT = Path(__file__).resolve().parents[1]
KEY_PATTERN = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{16,}")
FAKE_KEY = "s" + "k-" + "unit-test-not-a-real-key-000000"
PERSONA = "\ud14c\uc2a4\ud2b8 \ubb38\uc7a5 PERSONA-MARKER"
GOOD = {"p_zero_ever": 0.4, "p_zero_weekly": 0.1, "p_carb_top1": 0.05}
USAGE = {"input_tokens": 1000, "output_tokens": 200, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 150}}


def body(answer=None, status="completed", usage=USAGE):
    return {
        "status": status,
        "model": "served-model",
        "service_tier": "default",
        "usage": usage,
        "output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": json.dumps(GOOD if answer is None else answer)}]}],
    }


@pytest.fixture()
def frozen():
    return panel_run.load_config()


def items(n=3, cond="C1"):
    return [{"condition": cond, "code": f"CODE{i:04d}", "persona": f"{PERSONA} {i}"} for i in range(n)]


def make_runner(frozen, tmp_path, handler, budget=None, **kw):
    cfg, template = frozen
    model = cfg["models"]["main"]["id"]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    ledger = panel_run.Ledger(budget if budget is not None else cfg["limits"]["budget_usd"])
    return panel_run.Runner(cfg, template, model, FAKE_KEY, client=client, log_path=tmp_path / "calls.jsonl", cache_dir=tmp_path / "cache", sleep=lambda s: None, ledger=ledger, **kw)


# ---------- frozen config and prompt ----------


def test_prompt_hash_matches_frozen_config(frozen):
    cfg, template = frozen
    assert panel_run.template_sha256(template) == cfg["prompt_sha256"]
    assert template.count("{PERSONA}") == 1


def test_changed_prompt_is_refused(monkeypatch, tmp_path):
    changed = tmp_path / "gate_prompt.json"
    changed.write_text(json.dumps({"template": "other {PERSONA}"}), encoding="utf-8")
    monkeypatch.setattr(panel_run, "GATE_PROMPT", changed)
    with pytest.raises(RuntimeError, match="changed"):
        panel_run.load_config()


def _prompt_doc():
    return json.loads(panel_run.GATE_PROMPT.read_text(encoding="utf-8"))


@pytest.mark.skipif(shutil.which("pdftotext") is None or not (paths.RAW / "questionnaire_adult_2025.pdf").exists(), reason="pdftotext or questionnaire not present")
def test_prompt_questions_match_the_questionnaire_pdf(tmp_path):
    doc = _prompt_doc()
    out = tmp_path / "q.txt"
    subprocess.run(["pdftotext", "-enc", "UTF-8", str(paths.RAW / "questionnaire_adult_2025.pdf"), str(out)], check=True)
    pdf = re.sub(r"\s+", "", out.read_text(encoding="utf-8"))
    for block in (doc["question_a19"], doc["question_a15"]):
        for line in block.split("\n"):
            # Prompt labels such as the question tag and the options word are not questionnaire text.
            text = re.sub(r"^\[[^\]]+\]\s*", "", line)
            parts = text.split(":", 1)[1].split(" / ") if " / " in text else [text]
            for part in parts:
                part = re.sub(r"\s+", "", part)
                if part and not part.endswith(":"):
                    assert part in pdf, part
    assert doc["question_a19"] in doc["template"] and doc["question_a15"] in doc["template"]
    assert len(re.findall(r"^\d+\. ", doc["question_a15"], flags=re.M)) == 17


def test_prompt_has_no_rates_or_bias_hints(frozen):
    _, template = frozen
    doc = _prompt_doc()
    rest = template.replace(doc["question_a19"], "").replace(doc["question_a15"], "")
    assert "%" not in rest
    # bias, average, national, tendency, for example, compared with
    for word in ("\ud3b8\ud5a5", "\ud3c9\uade0", "\uc804\uad6d", "\uacbd\ud5a5", "\uc608\ub97c", "\uc608\uc2dc", "\ube44\uc728"):
        assert word not in rest


def test_request_shows_no_code_and_fixes_the_settings(frozen):
    cfg, template = frozen
    prompt = panel_run.render(template, PERSONA)
    req = panel_run.build_request(cfg, "gpt-x", prompt)
    assert "temperature" not in req and "top_p" not in req
    assert req["store"] is False
    assert req["text"]["format"]["strict"] is True
    assert set(req["text"]["format"]["schema"]["required"]) == {"p_zero_ever", "p_zero_weekly", "p_carb_top1"}
    assert "previous_response_id" not in req
    assert req["prompt_cache_options"] == {"mode": "explicit"}


@pytest.mark.skipif(not paths.GATE_KEY.exists(), reason="gate key not present")
def test_real_items_match_key_and_the_code_never_reaches_the_prompt(frozen):
    _, template = frozen
    loaded = panel_run.load_items()
    assert len(loaded) == 700
    for it in loaded:
        assert it["code"] not in panel_run.render(template, it["persona"])
    assert {i["persona"] for i in loaded if i["condition"] == "C0"}.__len__() == 1
    smoke = panel_run.smoke_items(loaded)
    assert [i["condition"] for i in smoke] == ["C1"] * 3 + ["C2"] * 3


# ---------- answer parsing and cost ----------


@pytest.mark.parametrize(
    "bad",
    [
        {"p_zero_ever": 1.2, "p_zero_weekly": 0.1, "p_carb_top1": 0.05},
        {"p_zero_ever": -0.1, "p_zero_weekly": 0.1, "p_carb_top1": 0.05},
        {"p_zero_ever": 0.5, "p_zero_weekly": 0.1},
        {"p_zero_ever": 0.5, "p_zero_weekly": 0.1, "p_carb_top1": 0.05, "extra": 1},
        {"p_zero_ever": True, "p_zero_weekly": 0.1, "p_carb_top1": 0.05},
        {"p_zero_ever": "0.5", "p_zero_weekly": 0.1, "p_carb_top1": 0.05},
    ],
)
def test_parse_rejects_bad_answers(bad):
    with pytest.raises(panel_run.AnswerError):
        panel_run.parse_answer(body(bad))


def test_parse_rejects_refusal_and_incomplete():
    with pytest.raises(panel_run.AnswerError, match="refusal"):
        panel_run.parse_answer({"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]})
    with pytest.raises(panel_run.AnswerError, match="incomplete"):
        panel_run.parse_answer({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}})


def test_parse_accepts_weekly_above_ever_because_score_only_counts_it():
    a = {"p_zero_ever": 0.2, "p_zero_weekly": 0.3, "p_carb_top1": 0.0}
    assert panel_run.parse_answer(body(a)) == a


def test_call_cost_formula_matches_the_guide():
    price = {"input": 1.0, "cached_input": 0.05, "cache_write_30m": 1.25, "output": 5.0}
    usage = {"input_tokens": 12000, "output_tokens": 1000, "input_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 7000}}
    expected = (1000 * 1.0 + 4000 * 0.05 + 7000 * 1.25 + 1000 * 5.0) / 1_000_000
    assert panel_run.call_cost(usage, price) == pytest.approx(expected)


def test_prices_in_the_frozen_config_are_per_million_and_positive(frozen):
    cfg, _ = frozen
    assert len(cfg["models"]) == 2
    for m in cfg["models"].values():
        p = m["usd_per_1m"]
        assert 0 < p["cached_input"] < p["input"] < p["output"]


# ---------- runner behaviour with a mocked API ----------


def test_cache_means_a_restart_never_pays_twice(frozen, tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=body())

    its = items(3)
    first = make_runner(frozen, tmp_path, handler).run(its)
    assert first["counts"]["called"] == 3 and len(calls) == 3
    second = make_runner(frozen, tmp_path, handler).run(its)
    assert second["counts"]["cached"] == 3 and len(calls) == 3


def test_retry_on_429_and_5xx_then_success(frozen, tmp_path):
    seq = [httpx.Response(429, json={"error": {"code": "rate_limit_exceeded"}}), httpx.Response(503, text="busy"), httpx.Response(200, json=body())]

    def handler(request):
        return seq.pop(0)

    r = make_runner(frozen, tmp_path, handler, concurrency=1)
    s = r.run(items(1))
    assert s["counts"]["called"] == 1
    rows = [json.loads(x) for x in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["status"] for x in rows] == ["http_429", "http_503", "ok"]


def test_gives_up_after_max_attempts_and_does_not_invent_an_answer(frozen, tmp_path):
    def handler(request):
        return httpx.Response(500, text="down")

    r = make_runner(frozen, tmp_path, handler, concurrency=1)
    s = r.run(items(1))
    assert s["counts"]["failed"] == 1
    assert not list((tmp_path / "cache").rglob("*.json"))


@pytest.mark.parametrize("error", [{"code": "insufficient_quota"}, {"type": "insufficient_quota", "code": "credit_balance_exhausted"}])
def test_no_credit_stops_at_once(frozen, tmp_path, error):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, json={"error": error})

    r = make_runner(frozen, tmp_path, handler, concurrency=1)
    s = r.run(items(5))
    assert s["stop_reason"] == "insufficient_quota"
    assert len(calls) == 1


def test_fatal_client_error_stops_at_once(frozen, tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={"error": {"code": "invalid_request_error"}})

    r = make_runner(frozen, tmp_path, handler, concurrency=1)
    s = r.run(items(5))
    assert s["stop_reason"].startswith("fatal_http_400")
    assert len(calls) == 1


def test_budget_stop_never_passes_the_budget(frozen, tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=body())

    cfg, _ = frozen
    price = cfg["models"]["main"]["usd_per_1m"]
    per_call_worst = cfg["request"]["max_output_tokens"] * price["output"] / 1_000_000
    budget = per_call_worst * 2.5
    r = make_runner(frozen, tmp_path, handler, budget=budget, concurrency=1)
    s = r.run(items(50))
    assert s["stop_reason"] == "budget"
    assert 0 < len(calls) < 50
    assert r.ledger.spent < budget


def test_budget_carries_across_restarts_through_the_log(tmp_path):
    log = tmp_path / "calls.jsonl"
    log.write_text(json.dumps({"cost_usd": 1.5}) + "\n" + json.dumps({"cost_usd": 0.25}) + "\n", encoding="utf-8")
    assert panel_run.spent_from_log(log) == pytest.approx(1.75)


def test_transport_error_books_the_worst_case(frozen, tmp_path):
    seq = [httpx.ReadTimeout("slow"), httpx.Response(200, json=body())]

    def handler(request):
        x = seq.pop(0)
        if isinstance(x, Exception):
            raise x
        return x

    r = make_runner(frozen, tmp_path, handler, concurrency=1)
    r.run(items(1))
    rows = [json.loads(x) for x in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["status"] == "transport_error" and rows[0]["cost_assumed"] is True and rows[0]["cost_usd"] > 0


def test_key_is_only_in_the_header_and_log_has_no_key_or_persona(frozen, tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            # OpenAI echoes a masked key in 401 bodies; the log keeps only the scrubbed error code.
            return httpx.Response(429, json={"error": {"code": FAKE_KEY, "message": FAKE_KEY}})
        return httpx.Response(200, json=body())

    r = make_runner(frozen, tmp_path, handler, concurrency=1)
    r.run(items(1))
    assert seen[0].headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert FAKE_KEY not in seen[0].content.decode("utf-8")
    written = "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file())
    assert FAKE_KEY not in written
    assert "PERSONA-MARKER" not in written


def test_scrub_masks_key_shapes():
    assert FAKE_KEY not in panel_run.scrub(f"Incorrect API key provided: {FAKE_KEY}.")
    assert "sk-" not in panel_run.scrub("key sk-ab***yz")


def test_answers_are_one_csv_per_condition_and_refuse_partial_sets(frozen, tmp_path):
    def handler(request):
        return httpx.Response(200, json=body())

    cfg, template = frozen
    its = items(2, "C1") + [{"condition": "C2", "code": "CODE9999", "persona": "x"}]
    r = make_runner(frozen, tmp_path, handler)
    r.run(its[:2])
    with pytest.raises(RuntimeError, match="no cached answer"):
        panel_run.write_answers(r.model, its, template, cache_dir=tmp_path / "cache", out_root=tmp_path)
    r.run(its)
    out, n = panel_run.write_answers(r.model, its, template, cache_dir=tmp_path / "cache", out_root=tmp_path)
    assert n == 3
    assert sorted(p.name for p in out.glob("*.csv")) == ["C1.csv", "C2.csv"]
    assert (out / "C1.csv").read_text(encoding="utf-8").splitlines()[0] == "code,p_zero_ever,p_zero_weekly,p_carb_top1"


def test_exploratory_script_runs_on_synthetic_answers(real, key, tmp_path):
    """Constant synthetic answers. Exercises the script only; these numbers are not results."""
    frame = answers_from(key, lambda rows, t: np.full(len(rows), {"ever": 0.3, "weekly": 0.4, "carb": 0.1}[t]), c0_value=0.2)
    frame.to_csv(tmp_path / "all.csv", index=False, encoding="utf-8")
    out = gate_explore.explore(tmp_path)
    assert out["_note"].startswith("EXPLORATORY")
    assert out["conditions"]["C1"]["share_weekly_above_ever"] == 1.0
    assert out["conditions"]["C0"]["share_weekly_above_ever"] == 0.0
    item = out["conditions"]["C2"]["items"]["ever"]
    assert len(item["by_age_band_pct"]) == 6 and len(item["cell_means_pct"]) == 12
    assert set(item["by_sex_pct"]) == {"male", "female"}


# ---------- repo hygiene ----------


def _git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")


def _repo_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith((".git/", "data/raw/")) or "__pycache__" in rel or ".pytest_cache" in rel:
            continue
        yield p, rel


def test_repo_contains_no_key_pattern_in_any_file():
    hits = [rel for p, rel in _repo_files() if KEY_PATTERN.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert not hits, f"key pattern in {len(hits)} files: {hits}"


def test_git_history_contains_no_key_pattern():
    log = _git("log", "--all", "-p", "--text").stdout
    assert not KEY_PATTERN.search(log), "key pattern in git history"


def test_real_key_literal_is_nowhere_in_the_repo(frozen):
    cfg, _ = frozen
    path = Path(cfg["api_key_file"])
    if not path.exists():
        pytest.skip("key file not present")
    key = path.read_text(encoding="utf-8-sig").strip()
    hits = [rel for p, rel in _repo_files() if key in p.read_text(encoding="utf-8", errors="replace")]
    assert not hits, f"key literal in {len(hits)} files"


def test_run_outputs_are_ignored():
    for rel in ["runs/gate/cache/m/x.json", "runs/gate/logs/calls.jsonl", "runs/gate/answers_gpt-6.1-terra/C1.csv"]:
        assert _git("check-ignore", rel).returncode == 0, rel


def test_scoring_does_not_depend_on_the_runner():
    pattern = re.compile(r"^\s*(import|from)\s+panel_run\b", re.M)
    for f in [ROOT / "audit.py", *ROOT.glob("src/lotte_audit/*.py")]:
        assert not pattern.search(f.read_text(encoding="utf-8")), f.name
