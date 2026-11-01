"""The run's state: what is done, what was approved, and the transcript.

The transcript is append only and written as it happens, so a crash keeps what came before. It holds tool arguments, tool outputs,
approvals and model metadata. Persona text never reaches this object because tools only return aggregates.
"""
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# The SDK runs plain function tools on worker threads, so parallel tool calls can write at the same moment.
_WRITE_LOCK = threading.Lock()
PERSISTED = ("run_id", "cards", "excluded", "removed", "plan", "approval", "run_doc", "diagnostics", "verdict", "catalog", "allocation", "questionnaire", "narration", "ledger_entry", "reason_tokens", "reasons_too_long", "panel_sha256", "demo", "refusals", "intake_cards")


@dataclass
class AuditContext:
    run_id: str
    cfg: dict
    text: dict
    budget: object
    backend: object = None
    transcript_path: Path = None
    log_path: Path = None
    intake_cards: dict = field(default_factory=dict)
    cards: dict = field(default_factory=dict)
    excluded: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    plan: dict = None
    approval: dict = None
    run_doc: dict = None
    diagnostics: dict = None
    verdict: dict = None
    catalog: dict = None
    allocation: dict = None
    questionnaire: dict = None
    narration: dict = field(default_factory=lambda: {"attempts": 0, "accepted": None, "rejections": []})
    ledger_entry: dict = None
    reason_tokens: dict = None
    reasons_too_long: int = 0
    panel_sha256: str = None
    demo: bool = False
    guardrail_enabled: bool = True
    panel_allowed: bool = True
    progress: int = None
    results_dir: Path = None
    ledger_path: Path = None
    planted: dict = field(default_factory=dict)
    tool_counts: dict = field(default_factory=dict)
    guardrail_fn: object = None

    def event(self, kind, **fields):
        row = {"t": round(time.time(), 3), "run_id": self.run_id, "event": kind, **fields}
        if self.transcript_path:
            path = Path(self.transcript_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with _WRITE_LOCK, path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return row

    def count_tool(self, name):
        self.tool_counts[name] = self.tool_counts.get(name, 0) + 1

    def snapshot(self):
        doc = {k: getattr(self, k) for k in PERSISTED}
        doc["tool_counts"] = self.tool_counts
        return doc

    def restore(self, doc):
        for k in PERSISTED:
            if k in doc:
                setattr(self, k, doc[k])
        self.tool_counts = doc.get("tool_counts", {})
        return self

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.snapshot(), ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(path)
