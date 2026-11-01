"""Render persona text for C0, C1, C2. Text comes from config/persona_templates.json only."""
import json
import math

from . import leakguard, paths


def load_templates():
    return json.loads((paths.CONFIG / "persona_templates.json").read_text(encoding="utf-8"))


def load_final_allowlist():
    return json.loads((paths.CONFIG / "allowlist_final.json").read_text(encoding="utf-8"))


def _code(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(int(value))


def render_c0(templates=None):
    templates = templates or load_templates()
    return leakguard.scan_text(templates["c0_text"])


def render_c1(row, templates=None):
    """row is a mapping of variable name to value."""
    templates = templates or load_templates()
    c1 = templates["c1"]
    parts = {}
    for key, var in templates["c1_vars"].items():
        code = _code(row[var])
        if code is None or code not in c1[key]:
            raise KeyError(f"no C1 wording for {var} code {code}")
        parts[key] = c1[key][code]
    return leakguard.scan_text(c1["frame"].format(**parts))


def render_item(item, row, scales):
    """Render one allowlisted answer as a sentence. Returns None for a skipped question."""
    code = _code(row[item["var"]])
    if code is None:
        if item.get("skip_if_missing"):
            return None
        raise KeyError(f"unexpected missing value for {item['var']}")
    if "scale" in item:
        return scales["agree_frame"].format(stem=item["stem"], answer=scales[item["scale"]][code])
    if "freq_frame" in item:
        return item["freq_frame"].format(freq=scales["freq8"][code])
    if code not in item["answers"]:
        raise KeyError(f"no wording for {item['var']} code {code}")
    return item["answers"][code]


def render_c2(row, allowlist, templates=None, forbidden=()):
    templates = templates or load_templates()
    sentences = []
    for item in allowlist:
        s = render_item(item, row, templates["scales"])
        if s:
            sentences.append(s)
    text = render_c1(row, templates) + " " + templates["c2_intro"] + " " + " ".join(sentences)
    return leakguard.scan_text(text, forbidden)
