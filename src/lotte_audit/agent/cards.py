"""Card intake rules. Pure functions. Refusal scope is enforced here in code, whatever the model decides.

Patterns catch the forms that were tried and written down. A sentence in a form nobody tried still passes.
"""
import re

# A sentence also ends where a Korean sentence end runs straight into the next word with no space. A decimal like 1.5 stays whole.
SENTENCE_RE = re.compile(r"(?<=[.!?\u3002])\s+|\n+|(?<=[\uac00-\ud7a3][.!?\u3002])(?=[\uac00-\ud7a3A-Za-z0-9])")
REQUIRED = ("description", "role", "target_segment", "anchor_items")
ROLES = ("candidate", "paraphrase", "brand", "negative_control", "benchmark")
TARGETS = ("all", "19-39", "40-59", "60+", "19-59")
ANCHORS = ("ever", "weekly", "carb")
TEXT_MIN, TEXT_MAX = 20, 1200


class Intake:
    def __init__(self, text):
        r = text["refusal"]
        c = text["card_rules"]
        self.request = {k: re.compile(v, re.I) for k, v in r["request_patterns"].items()}
        self.card_request = {k: re.compile(v, re.I) for k, v in r["card_request_patterns"].items()}
        self.injection = re.compile(c["injection_patterns"], re.I)
        self.brand = re.compile(c["real_brand_patterns"])
        self.alcohol = re.compile(c["alcohol_patterns"])
        self.image = re.compile(c["image_patterns"], re.I)
        self.under19 = re.compile(c["under19_patterns"])
        self.leading = [re.compile(p) for p in c["leading_fact_patterns"]]

    def classify_request(self, text):
        """Refusal classes named by a request, from fixed patterns."""
        return [k for k, rx in self.request.items() if rx.search(text or "")]

    def sentences(self, description):
        return [s for s in SENTENCE_RE.split(description.strip()) if s and s.strip()]

    def leading_sentences(self, description):
        """Fact style sentences that could lead a respondent, such as a prior survey or most people buying. Only a person may clear them."""
        out = []
        for sentence in self.sentences(description):
            if any(rx.search(sentence) for rx in self.card_request.values()) or self.injection.search(sentence):
                continue  # already taken out by a fixed pattern, with a record
            if any(rx.search(sentence) for rx in self.leading):
                out.append(sentence)
        return out

    def sanitize(self, description, suspected, human=None):
        """Split the description into sentences and drop instructions and out of scope asks.

        suspected comes from the model. It removes a sentence only when it names that whole sentence, so a word or a fragment does nothing.
        human maps a flagged sentence to the person's decision, remove or keep. A kept sentence cannot be removed by the model.
        """
        kept, removed, excluded = [], [], []
        human = human or {}
        for sentence in self.sentences(description):
            hit_class = next((k for k, rx in self.card_request.items() if rx.search(sentence)), None)
            if hit_class:
                excluded.append({"class": hit_class, "text": sentence})
                continue
            if self.injection.search(sentence):
                removed.append({"by": "pattern", "text": sentence})
                continue
            if human.get(sentence) == "remove":
                removed.append({"by": "human", "text": sentence})
                continue
            if human.get(sentence) != "keep" and any(same_sentence(q, sentence) for q in suspected or []):
                removed.append({"by": "model", "text": sentence})
                continue
            kept.append(sentence)
        return " ".join(kept), removed, excluded

    def check(self, card_id, fields, requested_outputs=(), suspected=(), decisions=None):
        """(status, doc). status is ok, needs_input, needs_human_confirmation or refused. The doc holds the cleaned card and every removal.

        decisions comes from the application, never from the model: {sentence: remove or keep} for sentences a person has looked at.
        """
        missing = [f for f in REQUIRED if not fields.get(f)]
        if missing:
            return "needs_input", {"card_id": card_id, "missing": missing}
        problems = []
        role = fields["role"]
        if role not in ROLES:
            problems.append(f"unknown_role:{role}")
        if fields["target_segment"] not in TARGETS:
            problems.append(f"unknown_target:{fields['target_segment']}")
        bad_anchor = [a for a in fields["anchor_items"] if a not in ANCHORS]
        if bad_anchor:
            problems.append(f"unknown_anchor:{bad_anchor}")
        if role == "paraphrase" and not fields.get("paraphrase_of"):
            problems.append("paraphrase_of_missing")
        if role == "brand" and not fields.get("brand_of"):
            problems.append("brand_of_missing")
        if problems:
            return "needs_input", {"card_id": card_id, "problems": problems}

        description = fields["description"]
        refused = []
        if self.alcohol.search(description):
            refused.append({"class": "out_of_scope", "why": "alcohol"})
        if self.under19.search(description):
            refused.append({"class": "out_of_scope", "why": "under 19"})
        if self.image.search(description):
            refused.append({"class": "packaging", "why": "image attached"})
        if "{" in description or "}" in description:
            refused.append({"class": "out_of_scope", "why": "braces in card text"})
        decisions = decisions or {}
        if not refused:
            pending = [s for s in self.leading_sentences(description) if s not in decisions]
            if pending:
                return "needs_human_confirmation", {"card_id": card_id, "flagged": pending, "next": "a person must decide remove or keep for each flagged sentence; the card stays out until then"}
        clean, removed, excluded = self.sanitize(description, suspected, decisions)
        if role != "brand" and self.brand.search(clean):
            refused.append({"class": "out_of_scope", "why": "a real brand on a card that is not the brand card"})
        if not TEXT_MIN <= len(clean) <= TEXT_MAX:
            refused.append({"class": "out_of_scope", "why": "description length after cleaning"})
        if refused:
            return "refused", {"card_id": card_id, "refused": refused, "removed": removed, "excluded": excluded}
        for ask in requested_outputs or []:
            for cls in self.classify_request(ask):
                excluded.append({"class": cls, "text": ask})
        return "ok", {
            "card_id": card_id,
            "role": role,
            "clean_text": clean,
            "attributes": fields.get("attributes") or [],
            "price_band": fields.get("price_band"),
            "alternatives": fields.get("alternatives") or [],
            "target_segment": fields["target_segment"],
            "anchor_items": list(fields["anchor_items"]),
            "paraphrase_of": fields.get("paraphrase_of"),
            "brand_of": fields.get("brand_of"),
            "removed": removed,
            "excluded": excluded,
            "leading_kept": [s for s, d in decisions.items() if d == "keep"],
        }


def same_sentence(named, sentence):
    """True when named is the whole sentence, apart from spacing and the closing mark."""

    def norm(text):
        return " ".join(str(text).split()).rstrip(".!?\u3002 ")

    return bool(norm(named)) and norm(named) == norm(sentence)


def roles_problem(cards):
    """What the card set lacks before a plan can exist. Roles are what the diagnostics need."""
    roles = [c["role"] for c in cards.values()]
    problems = []
    if roles.count("candidate") < 2:
        problems.append("at_least_two_candidates_needed")
    if roles.count("negative_control") != 1:
        problems.append("exactly_one_negative_control_needed")
    if roles.count("paraphrase") != 1:
        problems.append("exactly_one_paraphrase_needed")
    if roles.count("brand") > 1:
        problems.append("at_most_one_brand_card")
    for c in cards.values():
        if c["role"] == "paraphrase" and cards.get(c["paraphrase_of"], {}).get("role") != "candidate":
            problems.append("paraphrase_source_must_be_a_validated_candidate")
        if c["role"] == "brand" and cards.get(c["brand_of"], {}).get("role") != "candidate":
            problems.append("brand_source_must_be_a_validated_candidate")
    return problems
