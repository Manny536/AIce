"""Claim-language lint (round 3, L #7).

Fails if program output, SCORECARD/README/COMPANION, or any source/test/tool
file states certification or closure: PROVEN / proves, CERTIFIED / certifies,
"L²_C CLOSED", or a measured h value (e.g. "h=1.00"). Explicit negations
("not a proof claim", "certifies nothing", "does not close L²_C") and fence /
status statements (PROPOSED, OPEN, "fence") are allowed. The check is
sentence-level and heuristic: a negation anywhere earlier in the sentence, or
"nothing/no/none" right after the term, exempts it.

Out of scope on purpose: STUDY.md, STUDY_12_23.md, docs/. These are research
texts that cite external mathematics (e.g. the published sticky Kakeya
result). They are not outputs of this harness.

Status: PROPOSED systems hypothesis · efficacy OPEN · h < 1. Fences:
(1) Stickiness ≠ Act / S(x) authority (2) Hold / custody, not capture
(3) nothing here certifies an agent or closes L²_C.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

_L2C = r"L(?:²|2|\^2)_?C"
BANNED = (
    ("PROVEN", re.compile(r"\bproven\b|\bproves?\b|\bproved\b", re.I)),
    ("CERTIFIED", re.compile(r"\bcertif(?:y|ies|ied|ication)\b", re.I)),
    ("L2C_CLOSED", re.compile(
        rf"{_L2C}\s*(?:is\s+|are\s+|now\s+|has\s+been\s+)*closed|clos(?:e|es|ed|ing)\s+{_L2C}",
        re.I)),
    ("H_VALUE", re.compile(r"(?<![\w.])h\s*(?:=|≈|==)\s*\d")),
)
NEGATION_BEFORE = re.compile(
    r"\b(?:not|no|never|nothing|none|cannot|without|nor|neither|unproven|fences?|"
    r"OPEN|PROPOSED|banned|forbid\w*|disallow\w*|lint\w*)\b|≠|n't\b",
    re.I,
)
NEGATION_AFTER = re.compile(r"^\s*(?:nothing|no\b|none\b)", re.I)
_SPLIT = re.compile(r"(?<=[.!?])\s+|\n\s*\n|\s\|\s|^\s*[-*]\s+|·", re.M)


def sentences(text: str):
    text = re.sub(r"^\s*#+\s?", "", text, flags=re.M)
    for chunk in _SPLIT.split(text):
        if chunk and chunk.strip():
            yield " ".join(chunk.split())


def violations(text: str):
    out = []
    for s in sentences(text):
        for name, rx in BANNED:
            for m in rx.finditer(s):
                if NEGATION_BEFORE.search(s[: m.start()]) or NEGATION_AFTER.match(s[m.end():]):
                    continue
                out.append((name, s[:200]))
    return out


def _scanned_files():
    files = [ROOT / n for n in ("SCORECARD.md", "README.md", "COMPANION.md")]
    for sub in ("src", "tests", "tools"):
        files += sorted((ROOT / sub).rglob("*.py"))
    return [f for f in files if f.exists() and f.resolve() != Path(__file__).resolve()]


@pytest.mark.parametrize("path", _scanned_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_certification_or_closure_language_in_repo(path):
    assert violations(path.read_text(encoding="utf-8")) == []


def test_no_certification_or_closure_language_in_output():
    from sticky_scorer.simulate import demo_report, proxy_aligner_report

    assert violations(demo_report()) == []
    assert violations(proxy_aligner_report()) == []


@pytest.mark.parametrize("text", [
    "Sticky custody is PROVEN on these scenarios.",
    "The harness proves the metrics detect capture.",
    "This agent is CERTIFIED safe.",
    "Result: L²_C CLOSED.",
    "We close L²_C with this run.",
    "Measured h=1.00 on S1.",
    "h ≈ 0.97 after round 3",
    # the exact round-2 simulate.py:500 wording L flagged (now removed)
    "Negative-control tests swap in broken variants of this function to prove "
    "the metrics can detect them.",
])
def test_lint_catches_planted_claims(text):
    assert violations(text), text


@pytest.mark.parametrize("text", [
    "Not a proof claim.",
    "Nothing here certifies an agent or closes L²_C.",
    "It certifies nothing (L²_C fence 3).",
    "Status: PROPOSED · efficacy OPEN · h < 1.",
    "This does not show that L²_C is closed.",
    "Act = 0 ≠ Stop.",
])
def test_lint_allows_negations_and_fences(text):
    assert violations(text) == [], text
