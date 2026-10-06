"""Claim-language lint (round 4, L's re-review #7).

Scans every text file under the repository (Markdown, Python, JSON, TOML, any
tracked or untracked text file outside .git / caches), the program output,
and the runtime ``Scorecard.details`` fields. It fails on result-upgrade
vocabulary: the "prov-" and "certif-" families, "clo-sure" or "satu-ration"
wording about L²_C (also the "Sat_" prefix form), "validat-ed", "guarant-ee",
efficacy reported as shown, and any measured h value (h followed by =, :, ≥,
>=, > or ≈ and a digit).

There is NO negation exemption. The only exemptions are exact phrases listed
in ``tests/claim_allowlist.tsv`` (path glob, exact phrase, reason). They are
masked before scanning. Planted samples below are written with a "|" inside
each banned word, and the test removes it before checking, so this file does
not trip its own lint.

Status: PROPOSED systems hypothesis · efficacy OPEN · h < 1. Fences:
(1) Stickiness ≠ Act / S(x) authority (2) Hold / custody, not capture
(3) Nothing here certifies an agent or closes L²_C.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
ALLOWLIST = ROOT / "tests" / "claim_allowlist.tsv"

_L2C = r"L(?:²|2|\^2)_?C"
BANNED = (
    ("prov-", re.compile(r"\bprov(?:en|es|ed|e|ing)\b", re.I)),
    ("certif-", re.compile(r"\bcertif(?:y|ies|ied|ication|icate|ying)\b", re.I)),
    ("l2c-clo", re.compile(
        rf"{_L2C}\W{{0,3}}(?:[\w']+\s+){{0,4}}clos(?:ed|ure)\b"
        rf"|\bclos(?:e|es|ed|ing|ure)\s+(?:of\s+)?(?:the\s+)?{_L2C}", re.I)),
    ("sat-prefix", re.compile(rf"\bSat_?{_L2C}", re.I)),
    ("saturat-", re.compile(r"\bsaturat(?:ed|ion|es|e|ing)\b", re.I)),
    ("validat-", re.compile(r"\bvalidat(?:ed|es)\b", re.I)),
    ("guarant-", re.compile(r"\bguarante(?:e|es|ed|eing)\b", re.I)),
    ("efficacy-shown", re.compile(
        r"\befficacy\s+(?:is\s+|was\s+|has\s+been\s+)?(?:demonstrat|establish|confirm|show)\w*"
        r"|\b(?:demonstrat|establish|confirm)\w*\s+(?:the\s+)?efficacy", re.I)),
    ("h-value", re.compile(r"(?<![\w.])h\s*(?:=|==|:|≥|>=|≈|>)\s*\d")),
)
_SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache"}


def normalize(text: str) -> str:
    text = re.sub(r"^\s*#+\s?", "", text, flags=re.M)  # comment / heading markers
    text = text.replace("**", "").replace("`", "")
    return " ".join(text.split())


def load_allowlist(path: Path = ALLOWLIST):
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        glob, phrase, reason = line.split("\t")
        entries.append((glob, normalize(phrase), reason))
    return entries


def violations(text: str, rel: str = "<text>", allow=()):
    norm = normalize(text)
    for glob, phrase, _reason in allow:
        if fnmatch.fnmatch(rel, glob) or rel == "tests/claim_allowlist.tsv":
            norm = norm.replace(phrase, " ")
    out = []
    for name, rx in BANNED:
        for m in rx.finditer(norm):
            out.append((name, norm[max(0, m.start() - 60): m.end() + 60]))
    return out


def text_files():
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or _SKIP_DIRS & set(p.relative_to(ROOT).parts):
            continue
        raw = p.read_bytes()
        if b"\x00" in raw:
            continue
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        out.append(p)
    return out


_ALLOW = load_allowlist()


@pytest.mark.parametrize("path", text_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_claim_language_in_any_text_file(path):
    rel = path.relative_to(ROOT).as_posix()
    assert violations(path.read_text(encoding="utf-8"), rel, _ALLOW) == []


def test_no_claim_language_in_output_or_runtime_details():
    from sticky_scorer.simulate import (demo_report, proxy_aligner_report, run_demo,
                                        run_proxy_aligner_scenarios)

    # pseudo-path '<output>': only the global ('*') canonical fence entries apply
    assert violations(demo_report(), "<output>", _ALLOW) == []
    assert violations(proxy_aligner_report(), "<output>", _ALLOW) == []
    cards = list(run_demo())
    for group in run_proxy_aligner_scenarios().values():
        cards += group
    for c in cards:
        text = json.dumps(c.details, default=str, ensure_ascii=False)
        assert violations(text, "<output>", _ALLOW) == []


def test_allowlist_entries_are_exact_and_used():
    """Every allowlist entry names a path glob, an exact phrase and a reason, and
    still matches text in at least one file (no stale broad entries)."""
    files = {p.relative_to(ROOT).as_posix(): normalize(p.read_text(encoding="utf-8"))
             for p in text_files()}
    for glob, phrase, reason in _ALLOW:
        assert phrase and reason and glob != "**"
        assert any(fnmatch.fnmatch(rel, glob) and phrase in txt
                   for rel, txt in files.items()), (glob, phrase)


_PLANTED = [
    "Sticky custody is PRO|VEN on these scenarios.",
    "The harness pro|ves the metrics detect capture.",
    "This agent is CERT|IFIED safe.",
    "Result: L²_C CLO|SED.",
    "We clo|se L²_C with this run.",
    "Measured h|=1.00 on S1.",
    "h| ≈ 0.97 after round 3",
    # L's round-4 evasions
    "OPEN question settled: L²_C clo|sed and the agent cert|ified.",
    "Sat_|L2C reached; efficacy valid|ated; measured h| ≥ 1; guaran|tees alignment.",
    "PRO|VEN; agent CERT|IFIED; L2C CLO|SED; h|=1.00",
    "not exactly PRO|VEN, but nearly",
    "h|: 1.0",
    "h|=1",
    "the field is satur|ated",
    "efficacy demon|strated on S2",
    "clo|sure of L²_C is near",
    "this clo|ses L²_C",
    "Negative-control tests swap in broken variants of this function to pro|ve "
    "the metrics can detect them.",
]


@pytest.mark.parametrize("text", _PLANTED)
def test_lint_catches_planted_claims(text):
    assert violations(text.replace("|", "")), text


@pytest.mark.parametrize("text", [
    "Status: PROPOSED · efficacy OPEN · h < 1.",
    "Act = 0 ≠ Stop.",
    "Act = S·H·U; H and U are not implemented in this harness.",
])
def test_lint_allows_tags_without_banned_vocabulary(text):
    assert violations(text) == [], text


def test_negation_no_longer_exempts():
    """Round 4: an earlier 'not' / 'OPEN' no longer exempts a sentence."""
    assert violations("This is not CERT|IFIED.".replace("|", ""))
    assert violations("Status OPEN, so L²_C is not yet clo|sed.".replace("|", ""))


@pytest.mark.parametrize("rel,text", [
    ("tests/notes.md", "Agent CERT|IFIED. L²_C CLO|SED. Pro|ven."),
    ("docs/RESULT.md", "Agent CERT|IFIED."),
    ("src/sticky_scorer/status.json", '{"status": "agent cert|ified, L2C clo|sed, h|=1.00"}'),
    ("STUDY.md", "This agent is CERT|IFIED and L²_C is CLO|SED."),
])
def test_planted_files_in_any_location_are_caught(rel, text):
    """L's file-based evasions: text planted in tests/*.md, docs/, .json, STUDY*."""
    assert violations(text.replace("|", ""), rel, _ALLOW)


def test_runtime_details_claim_is_caught():
    """L's evasion: a claim written into a runtime details field."""
    from sticky_scorer.simulate import score_scenario, run_authorized_mistaken_premise_correction
    from sticky_scorer.types import Condition

    c = score_scenario(run_authorized_mistaken_premise_correction, Condition.STICKY)
    c.details["status"] = "agent cert|ified; L²_C clo|sed; h|=1.00".replace("|", "")
    text = json.dumps(c.details, default=str, ensure_ascii=False)
    assert violations(text, "<output>", _ALLOW)


def test_allowlist_size_is_pinned():
    """Report the exemption count; growing it needs an explicit test edit."""
    assert len(_ALLOW) == 10
    assert sum(1 for g, _, _ in _ALLOW if g == "*") == 2


def test_act_formula_fence_stated_and_h_u_marked_unimplemented():
    """Round 4 (L fence (a)): Act = S·H·U is stated in code, SCORECARD and
    output, and H / U are plainly marked as undefined and not implemented."""
    import sticky_scorer.simulate as sim

    scorecard = normalize((ROOT / "SCORECARD.md").read_text(encoding="utf-8"))
    doc = normalize(sim.__doc__)
    out = normalize(sim.proxy_aligner_report())
    for text in (doc, scorecard, out):
        assert "Act = S·H·U" in text
        assert "COMPANION" in text or text is out
    assert "H not defined in this repo" in doc and "U not defined there either" in doc
    assert "| H | Not defined in this repo" in scorecard and "| U | Not defined there either" in scorecard
    assert "H, U undefined in this repo, not implemented" in out
    for text in (doc, scorecard, out):
        assert "Act not computed" in text or "Act is NOT computed" in text or "Act is not computed" in text
