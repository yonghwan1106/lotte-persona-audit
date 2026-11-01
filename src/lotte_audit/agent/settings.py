"""Config, paths, stage budget and the freeze check of the agent stage."""
import hashlib
import json
import subprocess
from pathlib import Path

from .. import paths

STAGE = paths.ROOT / "runs" / "agent"
LOG_DIR = STAGE / "logs"
PANEL_LOG = LOG_DIR / "panel_calls.jsonl"
MODEL_LOG = LOG_DIR / "model_calls.jsonl"
CACHE_DIR = STAGE / "cache"
SAVED_DIR = STAGE / "saved"
RESULTS = paths.RESULTS / "agent"
LEDGER = RESULTS / "ledger.jsonl"
RUN_CONFIG = paths.CONFIG / "agent_run.json"
TEXT = paths.CONFIG / "agent_text.json"
PROMPT = paths.CONFIG / "concept_prompt.json"
CARDS = paths.CONFIG / "demo_cards.json"
FROZEN = paths.MANIFESTS / "frozen_agent.json"
FROZEN_FILES = (
    "config/agent_run.json",
    "config/concept_prompt.json",
    "config/demo_cards.json",
    "config/gate_run.json",
    "config/persona_templates.json",
    "results/stage3/verdict_v2.json",
    "src/lotte_audit/agent/diagnostics.py",
    "src/lotte_audit/agent/verdict_rules.py",
    "src/lotte_audit/agent/allocation.py",
    "src/lotte_audit/agent/panel.py",
    "src/lotte_audit/verdict.py",
    "src/lotte_audit/verdict_v2.py",
    "src/panel_run.py",
)
SHARED_WITH_GATE = ("endpoint", "api_key_file")
SHARED_REQUEST = ("reasoning_effort", "store", "service_tier", "prompt_cache_mode", "max_output_tokens")
SEP = "|"


class BudgetExceeded(RuntimeError):
    """A call would pass the stage budget, so it was not made."""


def load_text():
    return json.loads(TEXT.read_text(encoding="utf-8"))


def load_cards():
    return json.loads(CARDS.read_text(encoding="utf-8"))


def template_sha256(template):
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


def load_prompt():
    return json.loads(PROMPT.read_text(encoding="utf-8"))["template"]


def load_config(check_prompt=True):
    """The agent config. Refuses when the prompt moved or the request differs from the gate."""
    cfg = json.loads(RUN_CONFIG.read_text(encoding="utf-8"))
    gate = json.loads((paths.CONFIG / "gate_run.json").read_text(encoding="utf-8"))
    for field in SHARED_WITH_GATE:
        if cfg[field] != gate[field]:
            raise RuntimeError(f"config/agent_run.json differs from config/gate_run.json on {field}")
    for field in SHARED_REQUEST:
        if cfg["request"][field] != gate["request"][field]:
            raise RuntimeError(f"config/agent_run.json request differs from the gate on {field}")
    if check_prompt and template_sha256(load_prompt()) != cfg["prompt_sha256"]:
        raise RuntimeError("config/concept_prompt.json changed since config/agent_run.json was frozen")
    return cfg


def file_hash(relative):
    # Line endings are normalised, as in main_run.file_hash.
    return hashlib.sha256((paths.ROOT / relative).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def current_hashes(panel_sha256):
    return {"files": {name: file_hash(name) for name in FROZEN_FILES}, "panel_sha256": panel_sha256}


def check_frozen(panel_sha256):
    """Refuse when a frozen file or the panel changed since the freeze."""
    expected = json.loads(FROZEN.read_text(encoding="utf-8"))
    now = current_hashes(panel_sha256)
    changed = [k for k in expected["files"] if expected["files"][k] != now["files"].get(k)]
    if changed:
        raise RuntimeError(f"frozen files changed since freeze: {changed}")
    if expected["panel_sha256"] != now["panel_sha256"]:
        raise RuntimeError("the agent stage panel changed since freeze")


def require_committed():
    """No panel call before the frozen plan is in git."""
    names = [*FROZEN_FILES, "manifests/frozen_agent.json"]
    for name in names:
        if subprocess.run(["git", "-C", str(paths.ROOT), "ls-files", "--error-unmatch", name], capture_output=True).returncode != 0:
            raise RuntimeError(f"{name} is not committed")
    if subprocess.run(["git", "-C", str(paths.ROOT), "diff", "--quiet", "HEAD", "--", *names]).returncode != 0:
        raise RuntimeError("frozen files have uncommitted changes")


def spent_in(path):
    path = Path(path)
    if not path.exists():
        return 0.0
    total = 0.0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                total += json.loads(line).get("cost_usd", 0.0) or 0.0
    return total


class StageBudget:
    """The stage's money. It reads the logs every time, so separate processes share one budget."""

    def __init__(self, budget_usd, log_paths=(PANEL_LOG, MODEL_LOG)):
        self.budget_usd = float(budget_usd)
        self.log_paths = [Path(p) for p in log_paths]

    def spent(self):
        return sum(spent_in(p) for p in self.log_paths)

    def remaining(self):
        return self.budget_usd - self.spent()

    def check(self, worst_case_usd, what):
        """Refuse before the call when its worst case does not fit."""
        left = self.remaining()
        if worst_case_usd >= left:
            raise BudgetExceeded(f"{what}: worst case {worst_case_usd:.6f} USD does not fit the remaining {left:.6f} USD")


def price_of(cfg, model):
    for m in cfg["models"].values():
        if m["id"] == model:
            return m["usd_per_1m"]
    raise KeyError(f"model {model} is not in config/agent_run.json")


def short_model(model):
    """terra or luna, for ids and tables. Model ids hold digits, which metric ids may not."""
    return model.rsplit("-", 1)[-1]
