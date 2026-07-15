"""
assistant/parser.py
──────────────────────────────────────────────────────────────────────────────
Phase 3 — Parser Implementation & Response Engine
DeKUT CS & IT Smart FAQ Assistant

PARSING MECHANICS
─────────────────
The system uses a two-stage pipeline:

  Stage 1 – Lexical normalisation
    Raw query text is lowercased and tokenised.  Each token is looked up in
    KEYWORD_MAP (grammar_rules.py).  Recognised tokens are replaced by their
    CFG terminal category tag (e.g., "registration" → "reg_topic").
    Unrecognised tokens are silently dropped — this makes the parser robust
    to filler words ("please", "sir", "I", "am", etc.).

  Stage 2 – CFG parsing (ChartParser)
    The normalised token sequence is parsed with NLTK's Earley-style
    ChartParser against the 22-rule grammar defined in grammar_rules.py.
    If one or more parse trees are found, the first tree's leaf set is
    inspected to identify the dominant topic tag (e.g., "reg_topic").
    That tag is mapped to an intent label via TOPIC_TO_INTENT.

  Fallback – Keyword voting
    If the ChartParser finds no parse (sequence too short, ungrammatical, or
    highly colloquial), the system falls back to a keyword vote: it counts
    occurrences of each intent's keyword set in the original query and picks
    the intent with the highest vote count.  This ensures every query gets a
    response even when the CFG match fails.

RESPONSE ENGINE
───────────────
get_response(intent, office) returns a canned response dict keyed on intent.
The office parameter ("COD" | "Dean") adjusts the signatory line.
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import re
from collections import Counter
from typing import NamedTuple, Optional

import nltk

from .grammar_rules import (
    GRAMMAR,
    KEYWORD_MAP,
    PARSER,
    TOPIC_TO_INTENT,
    get_intent_for_topic,
)

# ── Return type ────────────────────────────────────────────────────────────────

class ParseResult(NamedTuple):
    matched_rule: str          # First CFG production matched (or "keyword-vote")
    category: str              # Intent label (e.g. "missing_marks")
    raw_response: str          # Canned response from the response engine
    confidence: float          # 1.0 = CFG parse; 0.0–0.9 = keyword vote score
    tokens_used: list[str]     # Normalised token sequence sent to parser


# ── Stage 1: Lexical normalisation ─────────────────────────────────────────────

_MULTI_WORD: dict[str, str] = {
    "would like": "want",
    "like to": "want",
    "want to": "want",
    "need to": "need",
    "final year": "proj_topic",
    "find out": "find",
    "know about": "know",
    "inquire about": "inquire",
}


_TOPIC_TAGS = {
    "reg_topic", "marks_topic", "grad_topic", "supp_topic",
    "rec_topic", "proj_topic", "exempt_topic", "general_topic",
}

_VERB_TAGS = {
    "want", "need", "request", "require", "apply",
    "inquire", "know", "find", "check", "confirm",
    "register", "drop", "add", "obtain", "submit", "get",
}

_MODAL_TAGS = {"can", "could", "may", "would", "should", "shall"}


def _normalise(text: str) -> list[str]:
    """
    Lowercase → expand multi-word phrases → tokenise → map to CFG tags.

    Post-processing produces a MINIMAL token sequence suitable for the
    ChartParser:
      • Keep only the FIRST occurrence of any topic tag (avoids duplicates
        when multiple synonyms of the same intent appear in one query).
      • Keep only the first modal and the first verb tag seen.
      • Assemble in canonical order: [modal?] [verb] [topic]

    This ensures the sequence matches one of:
        S -> IntentPhrase  (VP topic_NP)
        S -> ModalPhrase IntentPhrase  (ModalV VP topic_NP)
    """
    text = text.lower()
    for phrase, tag in _MULTI_WORD.items():
        text = text.replace(phrase, tag)

    raw_tokens: list[str] = re.findall(r"[a-z]+(?:'[a-z]+)?", text)

    modal:  str | None = None
    verb:   str | None = None
    topic:  str | None = None

    for tok in raw_tokens:
        mapped = KEYWORD_MAP.get(tok)
        if mapped is None:
            continue
        if mapped in _MODAL_TAGS and modal is None:
            modal = mapped
        elif mapped in _VERB_TAGS and verb is None:
            verb = mapped
        elif mapped in _TOPIC_TAGS and topic is None:
            topic = mapped

    # Build the canonical sequence.
    result: list[str] = []
    if modal:
        result.append(modal)
    if verb:
        result.append(verb)
    if topic:
        result.append(topic)
    return result


# ── Stage 2: CFG ChartParser ────────────────────────────────────────────────────

def _cfg_parse(tokens: list[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Attempt to parse the token list with NLTK ChartParser.

    Returns:
        (matched_rule, intent)  on success, or (None, None) on failure.

    The matched_rule string is the string form of the first production in the
    first parse tree — sufficient to identify which grammar rule triggered.
    """
    if not tokens:
        return None, None

    try:
        trees = list(PARSER.parse(tokens))
    except ValueError:
        # ChartParser raises ValueError if a token is not in the grammar.
        return None, None

    if not trees:
        return None, None

    first_tree = trees[0]
    # The first production at the root (e.g.  S -> IntentPhrase )
    matched_rule = str(first_tree.productions()[0])

    # Identify the intent-specific topic tag among the tree leaves.
    for leaf in first_tree.leaves():
        intent = TOPIC_TO_INTENT.get(leaf)
        if intent:
            return matched_rule, intent

    return matched_rule, None


# ── Fallback: Keyword voting ────────────────────────────────────────────────────

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "registration": [
        "register", "registration", "enroll", "enrollment", "add", "drop",
        "portal", "timetable", "clash", "class list", "semester",
    ],
    "missing_marks": [
        "mark", "marks", "grade", "grades", "result", "results", "cat",
        "cats", "transcript", "absent", "remark", "continuous assessment",
        "uploaded", "missing",
    ],
    "graduation": [
        "graduation", "graduate", "degree", "gown", "clearance", "ceremony",
        "industrial attachment", "graduate list", "graduate ceremony",
    ],
    "supplementary_exam": [
        "supplementary", "supp", "retake", "resit", "special sit",
        "fee", "eligib", "failed", "failure",
    ],
    "recommendation_letter": [
        "recommendation", "reference", "lor", "letter", "internship",
        "scholarship", "master", "postgrad", "endorse",
    ],
    "project_approval": [
        "project", "fyp", "proposal", "supervisor", "topic",
        "final year", "machine learning", "approve", "rejected",
    ],
    "course_exemption": [
        "exemption", "exempt", "transfer", "credit", "diploma", "prior",
        "recognition", "certification", "accredited",
    ],
    "general_inquiry": [
        "office hours", "appointment", "calendar", "handbook", "policy",
        "integrity", "contact", "contacts", "cheating", "student handbook",
    ],
}


def _keyword_vote(text: str) -> tuple[str, float]:
    """
    Count keyword hits for each intent category in the raw query.
    Returns (intent_with_most_hits, confidence_score ∈ [0,1]).
    """
    lower = text.lower()
    votes: Counter = Counter()
    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                votes[intent] += 1

    if not votes:
        return "general_inquiry", 0.0

    best_intent, best_count = votes.most_common(1)[0]
    # Normalise: max possible hits ≈ len of that intent's keyword list.
    max_possible = len(_INTENT_KEYWORDS[best_intent])
    confidence = min(best_count / max_possible, 0.99)
    return best_intent, confidence


# ── Public classify function ────────────────────────────────────────────────────

def classify_query(text: str) -> ParseResult:
    """
    Main entry point.  Accepts a raw student query string and returns a
    ParseResult with the matched grammar rule, intent category, canned
    response, and confidence score.

    Pipeline:
      1. Normalise text → CFG token sequence.
      2. Try ChartParser.  If successful → confidence = 1.0.
      3. If ChartParser fails → fallback keyword vote.
      4. Look up the canned response for the identified intent.
    """
    tokens = _normalise(text)
    matched_rule, intent = _cfg_parse(tokens)

    if intent and matched_rule:
        confidence = 1.0
    else:
        # Fallback
        intent, confidence = _keyword_vote(text)
        matched_rule = f"keyword-vote (score={confidence:.2f})"

    raw_response = get_response(intent)
    return ParseResult(
        matched_rule=matched_rule,
        category=intent,
        raw_response=raw_response,
        confidence=confidence,
        tokens_used=tokens,
    )


# ── Response Engine ────────────────────────────────────────────────────────────

_RESPONSES: dict[str, str] = {
    "registration": (
        "Dear Student,\n\n"
        "Thank you for reaching out to the Department of Computer Science & IT.\n\n"
        "Regarding your unit registration query: Please ensure that all your fees "
        "for the current semester are fully settled before attempting to register on "
        "the student portal. If your fees are cleared and the portal still shows an "
        "error, kindly visit the departmental office (Room CS-104) with your fee "
        "clearance receipt and student ID so that we can raise a ticket with the "
        "Registrar's office on your behalf.\n\n"
        "For add/drop requests beyond the official window, you must submit a written "
        "application addressed to the Chair of Department accompanied by a valid "
        "reason. The COD will then forward the approved request to the Registrar.\n\n"
        "Please note that the late registration deadline is strictly enforced and "
        "attracts a penalty fee as stipulated in the university's fee schedule.\n\n"
        "Warm regards,\n"
        "Chair of Department\n"
        "School of Computer Science & IT, DeKUT"
    ),

    "missing_marks": (
        "Dear Student,\n\n"
        "We take the matter of missing or incorrect academic marks very seriously.\n\n"
        "If your Continuous Assessment Test (CAT) marks have not been uploaded, "
        "please follow this procedure:\n"
        "  1. Confirm with your lecturer that the marks were submitted to the "
        "     departmental secretary.\n"
        "  2. If confirmed submitted but not appearing on the portal after 5 working "
        "     days, submit a formal complaint to this office with the unit code, "
        "     lecturer's name, and any supporting evidence (e.g., marked scripts).\n"
        "  3. The COD will engage the Examinations Office to investigate and "
        "     reconcile the records within 10 working days.\n\n"
        "For examination remark requests, the application must be submitted within "
        "14 days of results publication together with the prescribed remark fee "
        "(payable at the Finance Office). Remark outcomes are final.\n\n"
        "Warm regards,\n"
        "Chair of Department\n"
        "School of Computer Science & IT, DeKUT"
    ),

    "graduation": (
        "Dear Student,\n\n"
        "Congratulations on nearing the end of your programme!\n\n"
        "To be eligible for graduation at DeKUT, you must:\n"
        "  1. Have passed all required units (minimum 40 credit hours for BSc CS).\n"
        "  2. Successfully complete the mandatory industrial attachment (6 months).\n"
        "  3. Submit and pass your Final Year Project (minimum grade: C+).\n"
        "  4. Clear all financial obligations with the Finance Office.\n"
        "  5. Obtain a clearance form from the Library, Hostel, and all academic "
        "     departments, and submit the completed form to the Registrar.\n\n"
        "The clearance deadline is typically 6 weeks before the graduation date. "
        "Please check the academic calendar for the exact date. Students with any "
        "pending retake results are deferred to the next graduation ceremony.\n\n"
        "Warm regards,\n"
        "Dean, School of Computer Science & IT, DeKUT"
    ),

    "supplementary_exam": (
        "Dear Student,\n\n"
        "Supplementary examinations are available to students who have earned a "
        "final mark between 35% and 39% in a unit (i.e., a grade of E+).\n\n"
        "Key facts:\n"
        "  • Eligibility: Grade E+ (35–39%) only. Grades below 35% require a full "
        "    retake of the unit.\n"
        "  • Fee: KES 1,500 per paper (payable at the Finance Office before the "
        "    sitting date).\n"
        "  • Schedule: Supplementary exams are held at the end of the following "
        "    semester. Check the academic calendar for specific dates.\n"
        "  • Maximum sittings: A student may sit supplementary examinations for a "
        "    maximum of 3 units per academic year.\n"
        "  • Special sits: Requests for special sitting due to illness or "
        "    bereavement must be submitted to the Dean's office within 5 days of "
        "    the missed examination, accompanied by a medical certificate.\n\n"
        "Warm regards,\n"
        "Chair of Department\n"
        "School of Computer Science & IT, DeKUT"
    ),

    "recommendation_letter": (
        "Dear Student,\n\n"
        "The Office of the Chair of Department / Dean is pleased to support "
        "students with official recommendation and reference letters.\n\n"
        "To request a letter, please:\n"
        "  1. Submit a written application (email or physical) at least 5 working "
        "     days before your deadline.\n"
        "  2. Include in your application: your full name, registration number, "
        "     current year of study, CGPA, the purpose of the letter (internship, "
        "     postgraduate application, scholarship, etc.), the recipient "
        "     organisation's name, and your deadline date.\n"
        "  3. Attach copies of your latest transcript and any supporting documents "
        "     (e.g., job description, scholarship circular).\n\n"
        "Please note: We are unable to guarantee turnaround in less than 3 working "
        "days. For urgent requests, indicate 'URGENT' in your subject line and "
        "call the departmental office directly.\n\n"
        "Warm regards,\n"
        "Dean, School of Computer Science & IT, DeKUT"
    ),

    "project_approval": (
        "Dear Student,\n\n"
        "The procedure for Final Year Project (FYP) topic approval is as follows:\n\n"
        "  1. Topic Submission: Complete the FYP Topic Proposal Form (available on "
        "     the school's noticeboard and portal) and submit it to the departmental "
        "     secretary by the end of Week 3 of Semester 1 in your final year.\n"
        "  2. Supervisor Assignment: The COD assigns supervisors based on area of "
        "     specialisation and supervisor workload. You may indicate a preference "
        "     but assignments are at the COD's discretion.\n"
        "  3. Proposal Defence: An approved topic must be followed by a formal "
        "     proposal document (10–15 pages) submitted to your supervisor within "
        "     4 weeks of topic approval.\n"
        "  4. Topic Change: Changes after approval require written justification "
        "     endorsed by your supervisor and approved by the COD. Changes are not "
        "     permitted after Week 8.\n"
        "  5. Cross-departmental projects require dual supervision and the Dean's "
        "     written approval.\n\n"
        "Warm regards,\n"
        "Chair of Department\n"
        "School of Computer Science & IT, DeKUT"
    ),

    "course_exemption": (
        "Dear Student,\n\n"
        "DeKUT's Credit Transfer and Exemption Policy allows recognition of prior "
        "learning under the following conditions:\n\n"
        "  • Eligibility: Students who have previously studied at an accredited "
        "    institution (university or recognised polytechnic) may apply.\n"
        "  • Maximum transfer: Up to 50% of total programme credit hours may be "
        "    transferred.\n"
        "  • Procedure:\n"
        "    1. Submit an Application for Credit Transfer form to the Dean's office.\n"
        "    2. Attach certified copies of your previous transcripts and course "
        "       syllabi for each unit you wish to transfer.\n"
        "    3. The School's Academic Committee evaluates equivalence and issues "
        "       its recommendation within 21 days.\n"
        "    4. Final approval rests with the University Senate.\n\n"
        "Online certifications (e.g., Coursera, edX) are generally not eligible "
        "unless the issuing institution is accredited and the course is at "
        "university level.\n\n"
        "Warm regards,\n"
        "Dean, School of Computer Science & IT, DeKUT"
    ),

    "general_inquiry": (
        "Dear Student,\n\n"
        "Thank you for contacting the School of Computer Science & IT.\n\n"
        "General information:\n"
        "  • Office Hours: Monday–Friday, 8:00 AM – 5:00 PM (closed 1–2 PM)\n"
        "  • Chair of Department office: Room CS-104, CS Block\n"
        "  • Dean's office: Room AD-201, Administration Block\n"
        "  • To book an appointment, email the departmental secretary at "
        "    cs@dekut.ac.ke or call +254-051-2166113.\n"
        "  • The Academic Calendar is published annually on the university website: "
        "    https://www.dkut.ac.ke\n"
        "  • The Student Handbook is available at the library and on the student "
        "    portal under 'Resources'.\n"
        "  • The University's Academic Integrity Policy is contained in Statute "
        "    No. 7 of the DeKUT Academic Regulations. Violations may result in "
        "    unit cancellation, suspension, or expulsion.\n\n"
        "We encourage students to first consult the student portal and the academic "
        "calendar before reaching out to the office.\n\n"
        "Warm regards,\n"
        "Dean, School of Computer Science & IT, DeKUT"
    ),
}


def get_response(intent: str) -> str:
    """
    Look up the canned response for a given intent label.
    Falls back to the 'general_inquiry' response for unknown intents.
    """
    return _RESPONSES.get(intent, _RESPONSES["general_inquiry"])


# ── Quick self-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from .dataset import QUERIES

    print(f"\n{'='*70}")
    print("  DeKUT FAQ Parser — Self-Test Against All 40 Dataset Queries")
    print(f"{'='*70}\n")

    correct = 0
    for q in QUERIES:
        result = classify_query(q["query"])
        match = result.category == q["intent"]
        correct += int(match)
        status = "✓" if match else "✗"
        print(
            f"  [{q['id']:02d}] {status}  Expected: {q['intent']:<25} "
            f"Got: {result.category:<25} "
            f"Conf: {result.confidence:.2f}  "
            f"Rule: {result.matched_rule[:50]}"
        )

    pct = correct / len(QUERIES) * 100
    print(f"\n  Result: {correct}/{len(QUERIES)} correct  ({pct:.1f}%)\n")
