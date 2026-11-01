"""The number rule. The narrator writes sentences with {{m:metric_id}} placeholders, and only this renderer fills values.

check_sentence is a pure function, so the same rule runs as the SDK output guardrail, at the report writer, in the tests and on
the manager's note. Patterns catch the forms written in config/agent_text.json. A quantity worded in a form not listed there passes.
"""
import re
import unicodedata


class NarrationRejected(ValueError):
    def __init__(self, reasons):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def normalise(text):
    """Compatibility forms folded and invisible format characters dropped, so a superscript, a vulgar fraction or a zero width joiner hides nothing."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text) if unicodedata.category(ch) != "Cf")


def numeric_char(text):
    """The first character Unicode gives a numeric value, such as a Han numeral."""
    return next((ch for ch in text if unicodedata.numeric(ch, None) is not None), None)


class Guard:
    def __init__(self, text):
        g = text["narration_guard"]
        self.placeholder = re.compile(g["placeholder"])
        self.numerals = [re.compile(p) for p in g["numeral_patterns"]]
        self.claims = re.compile(g["forbidden_claim_patterns"])
        self.prefix = g["hypothesis_prefix"]
        self.restatement = re.compile(g["restatement_patterns"])
        self.taste = re.compile(g["taste_patterns"])
        self.ending = re.compile(g["hypothesis_ending"])
        self.rejected_note = g["rejected_note"]
        self.not_called_note = g["not_called_note"]

    def strip_placeholders(self, sentence):
        return self.placeholder.sub(" ", sentence)

    def check_sentence(self, sentence, known_ids, cited=None):
        """A list of reasons, empty when the sentence passes. Malformed placeholders stay in the text and so fail the digit or brace check."""
        reasons = []
        outside = normalise(self.strip_placeholders(sentence))
        if "{" in outside or "}" in outside:
            reasons.append("malformed_placeholder")
        for rx in self.numerals:
            hit = rx.search(outside)
            if hit:
                reasons.append(f"numeral_outside_placeholder:{hit.group(0)}")
                break
        else:
            ch = numeric_char(outside)
            if ch:
                reasons.append(f"numeral_outside_placeholder:{ch}")
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
            reasons += self.check_form(s["text"])
        return reasons

    def check_form(self, sentence):
        """A narrator sentence is a hypothesis about a cause. A restated verdict or a guess about taste is not, whatever mark it gets."""
        outside = normalise(self.strip_placeholders(sentence)).strip()
        reasons = []
        hit = self.restatement.search(outside)
        if hit:
            reasons.append(f"restates_verdict:{hit.group(0)}")
        hit = self.taste.search(outside)
        if hit:
            reasons.append(f"taste_guess:{hit.group(0)}")
        if not self.ending.search(outside):
            reasons.append("not_phrased_as_a_hypothesis")
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
        """The manager's note, or None when it holds a number, a market claim or a taste word. The note is never the source of a value."""
        if not note:
            return None
        if self.check_sentence(note, set()) or self.taste.search(normalise(note)):
            return None
        return note
