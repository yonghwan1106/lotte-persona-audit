"""The number rule. The narrator writes sentences with {{m:metric_id}} placeholders, and only this renderer fills values.

check_sentence is a pure function, so the same rule runs as the SDK output guardrail, at the report writer, and in the tests.
"""
import re


class NarrationRejected(ValueError):
    def __init__(self, reasons):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


class Guard:
    def __init__(self, text):
        g = text["narration_guard"]
        self.placeholder = re.compile(g["placeholder"])
        self.numerals = [re.compile(p) for p in g["numeral_patterns"]]
        self.claims = re.compile(g["forbidden_claim_patterns"])
        self.prefix = g["hypothesis_prefix"]
        self.rejected_note = g["rejected_note"]
        self.not_called_note = g["not_called_note"]

    def strip_placeholders(self, sentence):
        return self.placeholder.sub(" ", sentence)

    def check_sentence(self, sentence, known_ids, cited=None):
        """A list of reasons, empty when the sentence passes. Malformed placeholders stay in the text and so fail the digit or brace check."""
        reasons = []
        outside = self.strip_placeholders(sentence)
        if "{" in outside or "}" in outside:
            reasons.append("malformed_placeholder")
        for rx in self.numerals:
            hit = rx.search(outside)
            if hit:
                reasons.append(f"numeral_outside_placeholder:{hit.group(0)}")
                break
        hit = self.claims.search(outside)
        if hit:
            reasons.append(f"forbidden_claim:{hit.group(0)}")
        used = self.placeholder.findall(sentence)
        for mid in used:
            if mid not in known_ids:
                reasons.append(f"unknown_metric:{mid}")
        if cited is not None:
            for mid in cited:
                if mid not in known_ids:
                    reasons.append(f"unknown_metric:{mid}")
            if set(used) - set(cited):
                reasons.append("placeholder_not_cited")
        return reasons

    def check_output(self, sentences, known_ids):
        """sentences is a list of {text, metric_ids}. Returns every reason found."""
        reasons = []
        if not sentences:
            reasons.append("empty")
        for s in sentences:
            reasons += self.check_sentence(s["text"], known_ids, s.get("metric_ids", []))
        return reasons

    def render(self, sentences, catalog):
        """Filled sentences with the hypothesis mark. Refuses anything that did not pass, so a bypass cannot reach a report."""
        known = set(catalog)
        reasons = self.check_output(sentences, known)
        if reasons:
            raise NarrationRejected(reasons)
        out = []
        for s in sentences:
            filled = self.placeholder.sub(lambda m: catalog[m.group(1)]["value"], s["text"])
            out.append(self.prefix + filled)
        return out

    def clean_note(self, note):
        """The manager's note, or None when it holds a number. The note is never the source of a value."""
        if not note:
            return None
        return None if self.check_sentence(note, set()) else note
