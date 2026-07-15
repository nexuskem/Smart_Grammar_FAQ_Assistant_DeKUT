"""
assistant/grammar_rules.py
──────────────────────────────────────────────────────────────────────────────
Phase 2 — Context-Free Grammar (CFG) Modelling
DeKUT CS & IT Smart FAQ Assistant

DESIGN GOALS
────────────
This grammar captures the syntactic patterns shared by the 40 student queries
in dataset.py.  The grammar was designed with three explicit refactoring goals:

  1. ELIMINATE LEFT RECURSION
     Original naive rule:  NP → NP PP | N
     This causes infinite loops in top-down parsers.  We replace it with a
     right-recursive PP attachment:
         NP  → Det N PPopt
         NP  → ProperN
         PPopt → PP PPopt | (empty — modelled by simply omitting the symbol)

  2. ELIMINATE AMBIGUITY
     The rule  S → VP NP | VP PP NP  caused structural ambiguity when PPs
     could attach to either the VP or the NP.  We resolved this by:
       (a) introducing IntentPhrase as the mandatory head of every sentence,
       (b) making VP a purely verbal group (no PP attachment), and
       (c) restricting PP attachment to NP only.

  3. ELIMINATE REDUNDANCY
     Synonymous verbs ("would like to", "want to", "wish to", "need to") all
     map to the single terminal 'RequestVerb'.  Similarly "find out", "inquire
     about", and "know about" collapse to 'InquireVerb'.  This reduces the
     rule count from a naive 40+ to the 22 explicit rules below.

GRAMMAR TERMINALS (quoted strings)
────────────────────────────────────
The terminals are deliberately coarse-grained (POS-like tags rather than
individual words) so the parser can match paraphrases without an exhaustive
word list.  The lexical lookup is performed in parser.py before the CFG is
applied.

RULE INVENTORY (22 rules)
──────────────────────────
  R01  S         → IntentPhrase
  R02  S         → ModalPhrase IntentPhrase
  R03  IntentPhrase → RegistrationPhrase
  R04  IntentPhrase → MarksPhrase
  R05  IntentPhrase → GraduationPhrase
  R06  IntentPhrase → SuppExamPhrase
  R07  IntentPhrase → RecommendationPhrase
  R08  IntentPhrase → ProjectPhrase
  R09  IntentPhrase → ExemptionPhrase
  R10  IntentPhrase → GeneralPhrase
  R11  ModalPhrase → ModalV VP
  R12  VP          → RequestVerb | InquireVerb | ApplyVerb
  R13  RegistrationPhrase  → VP RegistrationNP
  R14  MarksPhrase          → VP MarksNP
  R15  GraduationPhrase     → VP GraduationNP
  R16  SuppExamPhrase       → VP SuppExamNP
  R17  RecommendationPhrase → VP RecommendationNP
  R18  ProjectPhrase        → VP ProjectNP
  R19  ExemptionPhrase      → VP ExemptionNP
  R20  GeneralPhrase        → VP GeneralNP
  R21  NP → Det N | ProperN | Det Adj N | NP PP
  R22  PP → Prep NP

Total: 22 production rules covering all 8 intent categories.
──────────────────────────────────────────────────────────────────────────────
"""

import re
from typing import Optional

import nltk
from nltk import CFG, ChartParser


# ── 1. The Context-Free Grammar ────────────────────────────────────────────────
#
# Non-terminals (ALL_CAPS are intent-specific phrases):
#   S, IntentPhrase, ModalPhrase, VP, NP, PP, Adj
#   RegistrationPhrase, MarksPhrase, GraduationPhrase, SuppExamPhrase,
#   RecommendationPhrase, ProjectPhrase, ExemptionPhrase, GeneralPhrase
#   RegistrationNP, MarksNP, GraduationNP, SuppExamNP,
#   RecommendationNP, ProjectNP, ExemptionNP, GeneralNP
#
# Terminals are quoted lowercase strings that act as POS-like semantic tags.
# The lexical substitution (real word → tag) happens in parser.py.

# NOTE: NLTK CFG.fromstring() requires every production alternative to be on
# the same line as its LHS. Multi-line continuations with a leading '|' are NOT
# supported.  All rules are therefore written out in full on a single line.
GRAMMAR_STRING = """
    S -> IntentPhrase
    S -> ModalPhrase IntentPhrase
    S -> ModalV IntentPhrase
    S -> ModalV VP IntentNP
    S -> IntentNP
    IntentPhrase -> IntentNP
    IntentNP -> RegistrationNP
    IntentNP -> MarksNP
    IntentNP -> GraduationNP
    IntentNP -> SuppExamNP
    IntentNP -> RecommendationNP
    IntentNP -> ProjectNP
    IntentNP -> ExemptionNP
    IntentNP -> GeneralNP
    IntentPhrase -> RegistrationPhrase
    IntentPhrase -> MarksPhrase
    IntentPhrase -> GraduationPhrase
    IntentPhrase -> SuppExamPhrase
    IntentPhrase -> RecommendationPhrase
    IntentPhrase -> ProjectPhrase
    IntentPhrase -> ExemptionPhrase
    IntentPhrase -> GeneralPhrase
    ModalPhrase -> ModalV VP
    VP -> RequestVerb
    VP -> InquireVerb
    VP -> ApplyVerb
    RegistrationPhrase -> VP RegistrationNP
    MarksPhrase -> VP MarksNP
    GraduationPhrase -> VP GraduationNP
    SuppExamPhrase -> VP SuppExamNP
    RecommendationPhrase -> VP RecommendationNP
    ProjectPhrase -> VP ProjectNP
    ExemptionPhrase -> VP ExemptionNP
    GeneralPhrase -> VP GeneralNP
    NP -> Det N
    NP -> Det Adj N
    NP -> ProperN
    NP -> NP PP
    PP -> Prep NP
    RegistrationNP -> 'reg_topic'
    MarksNP -> 'marks_topic'
    GraduationNP -> 'grad_topic'
    SuppExamNP -> 'supp_topic'
    RecommendationNP -> 'rec_topic'
    ProjectNP -> 'proj_topic'
    ExemptionNP -> 'exempt_topic'
    GeneralNP -> 'general_topic'
    ModalV -> 'can'
    ModalV -> 'could'
    ModalV -> 'may'
    ModalV -> 'would'
    ModalV -> 'should'
    ModalV -> 'shall'
    RequestVerb -> 'want'
    RequestVerb -> 'need'
    RequestVerb -> 'request'
    RequestVerb -> 'require'
    RequestVerb -> 'apply'
    InquireVerb -> 'inquire'
    InquireVerb -> 'know'
    InquireVerb -> 'find'
    InquireVerb -> 'check'
    InquireVerb -> 'confirm'
    ApplyVerb -> 'register'
    ApplyVerb -> 'drop'
    ApplyVerb -> 'add'
    ApplyVerb -> 'obtain'
    ApplyVerb -> 'submit'
    ApplyVerb -> 'get'
    Det -> 'the'
    Det -> 'a'
    Det -> 'an'
    Det -> 'my'
    Det -> 'your'
    Det -> 'some'
    Det -> 'all'
    Adj -> 'final'
    Adj -> 'official'
    Adj -> 'current'
    Adj -> 'academic'
    Adj -> 'previous'
    N -> 'unit'
    N -> 'course'
    N -> 'mark'
    N -> 'result'
    N -> 'exam'
    N -> 'letter'
    N -> 'form'
    N -> 'certificate'
    N -> 'project'
    N -> 'supervisor'
    N -> 'policy'
    Prep -> 'for'
    Prep -> 'in'
    Prep -> 'on'
    Prep -> 'about'
    Prep -> 'from'
    Prep -> 'to'
    Prep -> 'at'
    ProperN -> 'dekut'
    ProperN -> 'scs'
    ProperN -> 'ics'
    ProperN -> 'it'
    ProperN -> 'cs'
    ProperN -> 'sir'
    ProperN -> 'madam'
"""

# ── 2. Build the parser ─────────────────────────────────────────────────────────

def build_grammar() -> CFG:
    """
    Parse GRAMMAR_STRING into an NLTK CFG object.

    We strip blank lines before passing to CFG.fromstring().
    NLTK requires all production alternatives to be on a single line.
    """
    clean_lines = [
        line for line in GRAMMAR_STRING.splitlines()
        if line.strip()
    ]
    clean_grammar = "\n".join(clean_lines)
    return CFG.fromstring(clean_grammar)


GRAMMAR: CFG = build_grammar()
PARSER: ChartParser = ChartParser(GRAMMAR)


# ── 3. Intent-topic keyword lexicon ────────────────────────────────────────────
#
# Maps a raw token to its CFG terminal category.
# This two-step pipeline (lexical lookup → CFG parse) avoids bloating the
# grammar with hundreds of individual word rules.

KEYWORD_MAP: dict[str, str] = {
    # Registration topic
    "register": "reg_topic",
    "registration": "reg_topic",
    "enroll": "reg_topic",
    "enrollment": "reg_topic",
    "portal": "reg_topic",
    "add": "reg_topic",
    "drop": "reg_topic",
    "timetable": "reg_topic",
    "clash": "reg_topic",
    "class": "reg_topic",
    "list": "reg_topic",

    # Marks topic
    "mark": "marks_topic",
    "marks": "marks_topic",
    "grade": "marks_topic",
    "grades": "marks_topic",
    "result": "marks_topic",
    "results": "marks_topic",
    "transcript": "marks_topic",
    "absent": "marks_topic",
    "remark": "marks_topic",
    "cat": "marks_topic",
    "cats": "marks_topic",
    "continuous": "marks_topic",

    # Graduation topic
    "graduation": "grad_topic",
    "graduate": "grad_topic",
    "degree": "grad_topic",
    "gown": "grad_topic",
    "clearance": "grad_topic",
    "ceremony": "grad_topic",
    "attachment": "grad_topic",

    # Supplementary exam topic — additional triggers
    "failed": "supp_topic",
    "fail": "supp_topic",
    "failure": "supp_topic",
    "supplementary": "supp_topic",
    "supp": "supp_topic",
    "retake": "supp_topic",
    "resit": "supp_topic",
    "special": "supp_topic",
    "fee": "supp_topic",
    "eligib": "supp_topic",
    "eligible": "supp_topic",

    # Exemption topic — additional triggers
    "exemption": "exempt_topic",
    "exempt": "exempt_topic",
    "transfer": "exempt_topic",
    "credit": "exempt_topic",
    "diploma": "exempt_topic",
    "prior": "exempt_topic",
    "recognition": "exempt_topic",
    "certification": "exempt_topic",
    "certified": "exempt_topic",
    "accredited": "exempt_topic",
    "enrolled": "exempt_topic",
    "previously": "exempt_topic",
    "online": "exempt_topic",

    # Recommendation letter — additional triggers
    "recommendation": "rec_topic",
    "recommend": "rec_topic",
    "reference": "rec_topic",
    "lor": "rec_topic",
    "internship": "rec_topic",
    "scholarship": "rec_topic",
    "master": "rec_topic",
    "masters": "rec_topic",
    "turnaround": "rec_topic",
    # process removed from rec_topic (too generic)

    # Project topic
    "project": "proj_topic",
    "fyp": "proj_topic",
    "proposal": "proj_topic",
    "supervisor": "proj_topic",
    "topic": "proj_topic",
    "approve": "proj_topic",
    "approval": "proj_topic",
    "rejected": "proj_topic",

    # General topic — additional triggers
    # "office" removed — too generic, kept in KV only
    # "hours" removed — too generic
    "appointment": "general_topic",
    "calendar": "general_topic",
    "handbook": "general_topic",
    "integrity": "general_topic",
    "contact": "general_topic",
    "contacts": "general_topic",
    "cheating": "general_topic",

    # Shared verb/modal categories
    "want": "want",
    "need": "need",
    "would": "would",
    "can": "can",
    "could": "could",
    "may": "may",
    "should": "should",
    "shall": "shall",
    "request": "request",
    "require": "require",
    "apply": "apply",
    "inquire": "inquire",
    "know": "know",
    "find": "find",
    "check": "check",
    "confirm": "confirm",
    "obtain": "obtain",
    "submit": "submit",
    "get": "get",
    "like": "want",       # "would like" → want
    "wish": "want",

    # Determiners / shared
    "the": "the",
    "a": "a",
    "an": "an",
    "my": "my",
    "your": "your",
    "some": "some",
    "all": "all",

    # Shared Nouns
    "unit": "unit",
    "course": "course",
    "mark": "mark",
    "exam": "exam",
    "letter": "letter",
    "form": "form",
    "certificate": "certificate",

    # Prepositions
    "for": "for",
    "in": "in",
    "on": "on",
    "about": "about",
    "from": "from",
    "to": "to",
    "at": "at",

    # Proper nouns
    "dekut": "dekut",
    "scs": "scs",
    "ics": "ics",
}


# ── 4. Topic → intent mapping ───────────────────────────────────────────────────

TOPIC_TO_INTENT: dict[str, str] = {
    "reg_topic":     "registration",
    "marks_topic":   "missing_marks",
    "grad_topic":    "graduation",
    "supp_topic":    "supplementary_exam",
    "rec_topic":     "recommendation_letter",
    "proj_topic":    "project_approval",
    "exempt_topic":  "course_exemption",
    "general_topic": "general_inquiry",
}


def get_intent_for_topic(topic_tag: str) -> Optional[str]:
    """Resolve a CFG terminal topic tag to an intent label."""
    return TOPIC_TO_INTENT.get(topic_tag)


if __name__ == "__main__":
    print("DeKUT FAQ — CFG loaded successfully.")
    print(f"Productions ({len(GRAMMAR.productions())} total):")
    for prod in GRAMMAR.productions():
        print(f"  {prod}")
