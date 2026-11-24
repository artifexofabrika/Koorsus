"""Document type classification from source filename.

The first token after any matter_NN_ prefix is the reliable signal. A
substring test cannot distinguish "motion_for_protective_order" (a motion)
from "order_on_motion_to_compel" (an order), and getting that wrong would
let a motion through the outcome gate - the exact failure the gate exists
to prevent.
"""
import re

_ORDER_HEADS = {"order", "orders", "judgment", "judgments", "ruling",
                "rulings", "decree", "decree", "opinion", "verdict"}

_MOTION_HEADS = {"motion", "motions"}

_CHAIN = [
    (("motion",), "motion"),
    (("affidavit", "declaration"), "affidavit"),
    (("deposition", "transcript"), "deposition"),
    (("interrogator", "admission", "discovery", "subpoena"), "discovery"),
    (("complaint", "petition", "answer", "response", "reply", "brief"), "pleading"),
    (("lease", "agreement", "contract", "deed", "note", "policy", "warranty"), "contract"),
    (("letter", "email", "correspondence", "notice"), "correspondence"),
    (("report", "log", "record", "stipulation", "exhibit", "summary", "minutes"), "record"),
]


def classify(source):
    name = (source or "").lower()
    for _ in range(3):
        for ext in (".txt", ".pdf", ".docx", ".odt", ".md"):
            if name.endswith(ext):
                name = name[: -len(ext)]
    parts = [p for p in re.split(r"[^a-z0-9]+", name) if p]
    while parts and (parts[0] == "matter" or parts[0].isdigit()):
        parts.pop(0)
    if not parts:
        return "other"
    head = parts[0]
    if head in _ORDER_HEADS:
        return "order"
    if head in _MOTION_HEADS:
        return "motion"
    joined = " ".join(parts)
    for needles, label in _CHAIN:
        if any(n in joined for n in needles):
            return label
    return "other"
