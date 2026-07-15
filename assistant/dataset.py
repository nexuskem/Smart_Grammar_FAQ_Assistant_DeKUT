"""
assistant/dataset.py
──────────────────────────────────────────────────────────────────────────────
Phase 1 — Data Collection & Simulation
DeKUT School of Computer Science & IT — Smart FAQ Assistant

40 authentic student queries addressed to the COD or Dean's office.
Queries are grouped into 8 intent categories:

  1. registration        – unit registration, add/drop, late registration
  2. missing_marks       – marks not uploaded, exam results issues
  3. graduation          – graduation requirements, clearance, academic gown
  4. supplementary_exam  – supp eligibility, fee, exam scheduling
  5. recommendation_letter – LOR for internship, postgrad, scholarships
  6. project_approval    – FYP topic, supervisor, proposal approval
  7. course_exemption    – credit transfer, exemption, recognition of prior learning
  8. general_inquiry     – office hours, contacts, calendar, policy questions

Each record:
  {
    "id"     : int         – unique sequential ID
    "query"  : str         – verbatim student query
    "intent" : str         – one of the 8 categories above
    "office" : str         – "COD" | "Dean" | "Either"
  }
──────────────────────────────────────────────────────────────────────────────
"""

QUERIES: list[dict] = [
    # ── 1. REGISTRATION (IDs 1-5) ────────────────────────────────────────────
    {
        "id": 1,
        "query": "I would like to register for units in the current semester but the portal shows an error. Can I get assistance?",
        "intent": "registration",
        "office": "COD",
    },
    {
        "id": 2,
        "query": "Can I add a unit that I missed during the official registration period? The deadline has already passed.",
        "intent": "registration",
        "office": "COD",
    },
    {
        "id": 3,
        "query": "I want to drop one of my registered units because of a timetable clash. What is the procedure?",
        "intent": "registration",
        "office": "COD",
    },
    {
        "id": 4,
        "query": "My name does not appear on the class list even though I paid the required fees. How can this be fixed?",
        "intent": "registration",
        "office": "COD",
    },
    {
        "id": 5,
        "query": "Can I register for more than the maximum allowed number of units this semester due to retakes?",
        "intent": "registration",
        "office": "Dean",
    },

    # ── 2. MISSING MARKS (IDs 6-11) ──────────────────────────────────────────
    {
        "id": 6,
        "query": "My continuous assessment marks for SCS 2301 have not been uploaded on the student portal. Who should I contact?",
        "intent": "missing_marks",
        "office": "COD",
    },
    {
        "id": 7,
        "query": "I sat for the end-of-semester examination but my results are showing as absent. What should I do?",
        "intent": "missing_marks",
        "office": "COD",
    },
    {
        "id": 8,
        "query": "I believe there is an error in my final mark for ICS 3202. The marks don't reflect my performance. Can I apply for a remark?",
        "intent": "missing_marks",
        "office": "Dean",
    },
    {
        "id": 9,
        "query": "The lecturer said he submitted the marks but they are still missing on the portal after three weeks. Please help.",
        "intent": "missing_marks",
        "office": "COD",
    },
    {
        "id": 10,
        "query": "I need a transcript urgently for a job application but two units show incomplete results. How fast can this be resolved?",
        "intent": "missing_marks",
        "office": "Dean",
    },
    {
        "id": 11,
        "query": "My CATs marks were never entered and the lecturer is no longer available. What is the school's policy on this?",
        "intent": "missing_marks",
        "office": "Dean",
    },

    # ── 3. GRADUATION (IDs 12-16) ─────────────────────────────────────────────
    {
        "id": 12,
        "query": "What are the minimum graduation requirements for the Bachelor of Science in Computer Science program?",
        "intent": "graduation",
        "office": "Either",
    },
    {
        "id": 13,
        "query": "I have completed all my coursework but I haven't done the industrial attachment. Can I still graduate this year?",
        "intent": "graduation",
        "office": "Dean",
    },
    {
        "id": 14,
        "query": "How do I obtain a graduation clearance form and what departments must sign it?",
        "intent": "graduation",
        "office": "COD",
    },
    {
        "id": 15,
        "query": "I want to know the date by which I must clear all fees in order to be included in the graduation list.",
        "intent": "graduation",
        "office": "Dean",
    },
    {
        "id": 16,
        "query": "Can I attend the graduation ceremony and collect my degree certificate even if one retake result is still pending?",
        "intent": "graduation",
        "office": "Dean",
    },

    # ── 4. SUPPLEMENTARY EXAM (IDs 17-21) ────────────────────────────────────
    {
        "id": 17,
        "query": "I failed SCS 3304 with a grade of 35%. Am I eligible to sit for a supplementary examination?",
        "intent": "supplementary_exam",
        "office": "COD",
    },
    {
        "id": 18,
        "query": "What is the fee for a supplementary examination and how do I make the payment?",
        "intent": "supplementary_exam",
        "office": "Either",
    },
    {
        "id": 19,
        "query": "When will the supplementary examinations for the previous semester be scheduled?",
        "intent": "supplementary_exam",
        "office": "Either",
    },
    {
        "id": 20,
        "query": "I missed the supplementary examination due to illness. Is there a provision for a special sit?",
        "intent": "supplementary_exam",
        "office": "Dean",
    },
    {
        "id": 21,
        "query": "How many supplementary examinations am I allowed to sit in a single academic year?",
        "intent": "supplementary_exam",
        "office": "COD",
    },

    # ── 5. RECOMMENDATION LETTER (IDs 22-26) ─────────────────────────────────
    {
        "id": 22,
        "query": "I need a recommendation letter from the COD for my internship application at Safaricom. How do I request one?",
        "intent": "recommendation_letter",
        "office": "COD",
    },
    {
        "id": 23,
        "query": "Can the Dean write a recommendation letter supporting my application for a master's program at the University of Nairobi?",
        "intent": "recommendation_letter",
        "office": "Dean",
    },
    {
        "id": 24,
        "query": "How long does it take for the office to process a recommendation letter request?",
        "intent": "recommendation_letter",
        "office": "Either",
    },
    {
        "id": 25,
        "query": "I need a reference letter for a scholarship application. What documents should I submit to support the request?",
        "intent": "recommendation_letter",
        "office": "Either",
    },
    {
        "id": 26,
        "query": "Is it possible to get a recommendation letter on short notice, say within 24 hours, because of an urgent deadline?",
        "intent": "recommendation_letter",
        "office": "Either",
    },

    # ── 6. PROJECT APPROVAL (IDs 27-31) ──────────────────────────────────────
    {
        "id": 27,
        "query": "I would like to get my final year project topic approved. What is the procedure for topic submission?",
        "intent": "project_approval",
        "office": "COD",
    },
    {
        "id": 28,
        "query": "How do I request a supervisor for my final year project in the area of machine learning?",
        "intent": "project_approval",
        "office": "COD",
    },
    {
        "id": 29,
        "query": "My project proposal was rejected. What changes must I make before resubmitting?",
        "intent": "project_approval",
        "office": "COD",
    },
    {
        "id": 30,
        "query": "Can I change my final year project topic after it has already been approved by the department?",
        "intent": "project_approval",
        "office": "COD",
    },
    {
        "id": 31,
        "query": "Is it permissible to work on a final year project jointly with students from another department?",
        "intent": "project_approval",
        "office": "Dean",
    },

    # ── 7. COURSE EXEMPTION (IDs 32-36) ──────────────────────────────────────
    {
        "id": 32,
        "query": "I completed a diploma in IT before joining DeKUT. Can some of my diploma units be transferred or exempted?",
        "intent": "course_exemption",
        "office": "Dean",
    },
    {
        "id": 33,
        "query": "What is the process for applying for a unit exemption based on prior learning from another accredited institution?",
        "intent": "course_exemption",
        "office": "Dean",
    },
    {
        "id": 34,
        "query": "I took an online certification course in data structures. Can it count towards any of the university units?",
        "intent": "course_exemption",
        "office": "COD",
    },
    {
        "id": 35,
        "query": "How many credits can be transferred from another university under the credit transfer policy?",
        "intent": "course_exemption",
        "office": "Dean",
    },
    {
        "id": 36,
        "query": "I was previously enrolled at another university and passed several programming courses. Can I be exempted from their equivalents here?",
        "intent": "course_exemption",
        "office": "Dean",
    },

    # ── 8. GENERAL INQUIRY (IDs 37-40) ───────────────────────────────────────
    {
        "id": 37,
        "query": "What are the office hours for the Chair of Department and how can I book an appointment?",
        "intent": "general_inquiry",
        "office": "COD",
    },
    {
        "id": 38,
        "query": "Where can I find the academic calendar for the current academic year including semester dates?",
        "intent": "general_inquiry",
        "office": "Either",
    },
    {
        "id": 39,
        "query": "What is the school's policy on academic integrity and what are the consequences of exam cheating?",
        "intent": "general_inquiry",
        "office": "Dean",
    },
    {
        "id": 40,
        "query": "Can I get a copy of the official student handbook for the School of Computer Science and IT?",
        "intent": "general_inquiry",
        "office": "Either",
    },
]

# ── Helpers ────────────────────────────────────────────────────────────────────

INTENT_LABELS: list[str] = [
    "registration",
    "missing_marks",
    "graduation",
    "supplementary_exam",
    "recommendation_letter",
    "project_approval",
    "course_exemption",
    "general_inquiry",
]


def get_queries_by_intent(intent: str) -> list[dict]:
    """Return all queries matching the given intent label."""
    return [q for q in QUERIES if q["intent"] == intent]


def get_all_texts() -> list[str]:
    """Return a flat list of query strings (useful for NLP pipelines)."""
    return [q["query"] for q in QUERIES]


if __name__ == "__main__":
    for intent in INTENT_LABELS:
        items = get_queries_by_intent(intent)
        print(f"\n{'='*60}")
        print(f"  INTENT: {intent.upper()}  ({len(items)} queries)")
        print(f"{'='*60}")
        for item in items:
            print(f"  [{item['id']:02d}] ({item['office']}) {item['query']}")
