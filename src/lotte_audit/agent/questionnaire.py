"""The questionnaire. Registered wording only, no free text argument, so nothing can be added after the answers are seen. It is never sent."""
import json

from .. import paths


def build(allocation, cards, text):
    q = text["questionnaire"]
    gate = json.loads((paths.CONFIG / "gate_prompt.json").read_text(encoding="utf-8"))
    selected = [c["card"] for c in allocation["cards"]]
    items = [{"id": f"concept_{c}", "kind": "concept", "card_text": cards[c]["clean_text"], "question": q["concept_item"], "options": q["concept_options"]} for c in selected]
    items.append({"id": "anchor_a19", "kind": "anchor", "text": gate["question_a19"]})
    items.append({"id": "anchor_a15", "kind": "anchor", "text": gate["question_a15"]})
    for name in q["demographics"]:
        items.append({"id": f"demo_{name}", "kind": "demographic", "text": name})
    return {
        "intro": q["intro"],
        "anchor_note": q["anchor_note"],
        "fieldwork_rules": q["fieldwork_rules"],
        "benchmark_note": allocation["benchmark_note"],
        "card_order": "randomised per respondent, first card reported separately",
        "items": items,
        "sent": False,
    }
