"""Card intake rules. Pure functions. Refusal scope is enforced here in code, whatever the model decides."""
import re

SENTENCE_RE = re.compile(r"(?<=[.!?\u3002])\s+|\n+")
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

    def classify_request(self, text):
        """Refusal classes named by a request, from fixed patterns."""
        return [k for k, rx in self.request.items() if rx.search(text or "")]

    def sanitize(self, description, suspected):
        """Split the description into sentences and drop instructions and out of scope asks.

        suspected comes from the model. It can only remove text that really is in the card, so it cannot add anything.
        """
        kept, removed, excluded = [], [], []
        for sentence in [s for s in SENTENCE_RE.split(description.strip()) if s.strip()]:
            hit_class = next((k for k, rx in self.card_request.items() if rx.search(sentence)), None)
            if hit_class:
                excluded.append({"class": hit_class, "text": sentence})
                continue
            if self.injection.search(sentence):
                removed.append({"by": "pattern", "text": sentence})
                continue
            if any(q.strip() and (q.strip() in sentence or sentence in q) for q in suspected or []):
                removed.append({"by": "model", "text": sentence})
                continue
            kept.append(sentence)
        return " ".join(kept), removed, excluded

    def check(self, card_id, fields, requested_outputs=(), suspected=()):
        """(status, doc). status is ok, needs_input or refused. The doc holds the cleaned card and every removal."""
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
        clean, removed, excluded = self.sanitize(description, suspected)
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
        }


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
