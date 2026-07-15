#!/usr/bin/env python
"""
validate.py
──────────────────────────────────────────────────────────────────────────────
Phase 5 — Standalone Validation Framework
DeKUT CS & IT Smart FAQ Assistant

USAGE
─────
  # Interactive mode (type a query or an audio file path):
  python validate.py

  # Batch mode — test all 40 dataset queries:
  python validate.py --batch

  # Batch mode with AI refinement (requires OPENAI_API_KEY in env):
  python validate.py --batch --ai

  # Test a single audio file:
  python validate.py --audio /path/to/voicenote.ogg

  # Test a single text query:
  python validate.py --query "I want to register for units this semester"

  # Save a full HTML report:
  python validate.py --batch --report

OUTPUT FORMAT (for each query)
────────────────────────────────
  ╔══════════════════════════════════════════════╗
  ║ Query #01                                   ║
  ╠══════════════════════════════════════════════╣
  ║ Input          : <raw text>                 ║
  ║ Tokens Used    : [list of CFG tags]         ║
  ║ Matched Rule   : S -> IntentPhrase  (R01)  ║
  ║ Category       : registration               ║
  ║ Confidence     : 1.00 (CFG parse)           ║
  ╠══════════════════════════════════════════════╣
  ║ Response:                                   ║
  ║   Dear Student, ...                         ║
  ╚══════════════════════════════════════════════╝

──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# ── Ensure the project root is on the Python path ─────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set Django settings so assistant models work if needed.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "faq_assistant.settings")

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# ── Imports (non-Django) ───────────────────────────────────────────────────────
from assistant.parser import classify_query, ParseResult
from assistant.dataset import QUERIES, INTENT_LABELS


# ── ANSI colours ───────────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BLUE   = "\033[94m"
    GREY   = "\033[90m"
    WHITE  = "\033[97m"

def _c(text: str, *codes: str) -> str:
    return "".join(codes) + text + C.RESET

def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = _supports_color()
def col(text: str, *codes: str) -> str:
    return _c(text, *codes) if USE_COLOR else text


# ── Display helpers ────────────────────────────────────────────────────────────

WIDTH = 72

def _box_top(title: str = "") -> str:
    inner = f" {title} " if title else ""
    line  = f"╔{'═' * (WIDTH - 2)}╗"
    if title:
        pad = WIDTH - 2 - len(inner)
        line = f"╔{inner}{'═' * pad}╗"
    return col(line, C.CYAN, C.BOLD)

def _box_mid() -> str:
    return col(f"╠{'═' * (WIDTH - 2)}╣", C.CYAN)

def _box_bot() -> str:
    return col(f"╚{'═' * (WIDTH - 2)}╝", C.CYAN)

def _box_row(label: str, value: str, value_color: str = C.WHITE) -> str:
    label_str = col(f"{label:<16}", C.GREY)
    value_str = col(value, value_color)
    inner = f"{label_str}: {value_str}"
    # Strip ANSI for width calculation
    import re
    plain = re.sub(r"\033\[[0-9;]*m", "", inner)
    pad = max(0, WIDTH - 4 - len(plain))
    return col("║ ", C.CYAN) + inner + " " * pad + col(" ║", C.CYAN)

def _box_text(text: str, indent: int = 2) -> list[str]:
    """Wrap text into box rows."""
    import textwrap
    lines_out = []
    for para in text.split("\n"):
        wrapped = textwrap.wrap(para, width=WIDTH - 4 - indent) or [""]
        for line in wrapped:
            pad = max(0, WIDTH - 4 - indent - len(line))
            lines_out.append(
                col("║ ", C.CYAN) + " " * indent + col(line, C.WHITE) + " " * pad + col(" ║", C.CYAN)
            )
    return lines_out


def print_result(
    query_text: str,
    result: ParseResult,
    query_id: str = "",
    expected_intent: str = "",
    ai_response: str = "",
) -> None:
    """Pretty-print a single ParseResult to stdout."""
    title = f" Query {query_id} " if query_id else " Result "
    correct = (expected_intent == result.category) if expected_intent else None

    if correct is True:
        status = col("✓ CORRECT", C.GREEN, C.BOLD)
    elif correct is False:
        status = col(f"✗ WRONG (expected: {expected_intent})", C.RED, C.BOLD)
    else:
        status = ""

    conf_color = C.GREEN if result.confidence >= 1.0 else (C.YELLOW if result.confidence > 0.4 else C.RED)
    conf_label = "CFG parse" if result.confidence >= 1.0 else f"keyword-vote ({result.confidence:.2f})"

    print(_box_top(title))
    print(_box_row("Input", query_text[:60] + ("..." if len(query_text) > 60 else "")))
    if result.tokens_used:
        print(_box_row("Tokens Used", str(result.tokens_used[:8]), C.GREY))
    print(_box_row("Matched Rule", result.matched_rule[:55], C.BLUE))
    print(_box_row("Category", result.category, C.YELLOW))
    print(_box_row("Confidence", conf_label, conf_color))
    if status:
        print(_box_row("Verdict", status.replace("\033[0m","") if not USE_COLOR else ""))  # hack
        # Redo cleanly:
        verdict_inner = col(f"{'Verdict':<16}", C.GREY) + ": " + status
        import re
        plain = re.sub(r"\033\[[0-9;]*m", "", verdict_inner)
        pad = max(0, WIDTH - 4 - len(plain))
        print(col("║ ", C.CYAN) + verdict_inner + " " * pad + col(" ║", C.CYAN))

    print(_box_mid())
    response_to_show = ai_response if ai_response else result.raw_response
    header_label = "AI Response" if ai_response else "CFG Response"
    print(col("║ ", C.CYAN) + col(f" {header_label}:", C.CYAN, C.BOLD) + " " * (WIDTH - 4 - len(header_label) - 1) + col(" ║", C.CYAN))
    for line in _box_text(response_to_show, indent=2):
        print(line)
    print(_box_bot())
    print()


# ── AI services (optional) ─────────────────────────────────────────────────────

def _try_refine(result: ParseResult, query_text: str, use_ai: bool) -> tuple[str, bool]:
    """
    Attempt GPT-4o refinement if use_ai=True.
    Returns (response_text, ai_was_used).
    """
    if not use_ai:
        return result.raw_response, False
    try:
        from assistant.ai_services import refine_response, OfflineModeError
        refined = refine_response(result.category, result.raw_response, query_text)
        return refined, True
    except Exception as e:
        print(col(f"  ⚠ AI refinement unavailable: {e}", C.YELLOW))
        return result.raw_response, False


def _try_transcribe(audio_path: str) -> str:
    """Transcribe audio → text via Whisper. Returns transcribed text."""
    try:
        from assistant.ai_services import transcribe_audio, OfflineModeError
        print(col(f"\n  🎤 Transcribing: {audio_path}", C.CYAN))
        text = transcribe_audio(audio_path)
        print(col(f"  📝 Transcript: {text}", C.GREEN))
        return text
    except Exception as e:
        print(col(f"  ✗ Transcription failed: {e}", C.RED))
        sys.exit(1)


# ── Report generation (HTML) ───────────────────────────────────────────────────

def generate_html_report(
    results_data: list[dict],
    output_path: Path,
    batch_stats: dict,
) -> None:
    """Generate a self-contained HTML report of batch validation results."""
    intent_colors = {
        "registration":        "#3B82F6",
        "missing_marks":       "#EF4444",
        "graduation":          "#10B981",
        "supplementary_exam":  "#F59E0B",
        "recommendation_letter":"#8B5CF6",
        "project_approval":    "#EC4899",
        "course_exemption":    "#06B6D4",
        "general_inquiry":     "#6B7280",
    }

    rows = ""
    for d in results_data:
        color = intent_colors.get(d["category"], "#888")
        verdict_td = (
            '<td class="correct">✓ Correct</td>'
            if d.get("correct")
            else f'<td class="wrong">✗ Expected: {d.get("expected","")}</td>'
        )
        rows += f"""
        <tr>
            <td>{d['id']}</td>
            <td class="query">{d['query']}</td>
            <td><span class="badge" style="background:{color}">{d['category']}</span></td>
            <td>{d['matched_rule'][:50]}</td>
            <td>{d['confidence']:.2f}</td>
            {verdict_td}
        </tr>
        """

    accuracy  = batch_stats.get("accuracy", 0)
    correct   = batch_stats.get("correct", 0)
    total     = batch_stats.get("total", 0)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DeKUT FAQ Validation Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
  h1 {{ font-size: 1.75rem; color: #38bdf8; margin-bottom: 0.25rem; }}
  .meta {{ color: #64748b; margin-bottom: 2rem; font-size: 0.9rem; }}
  .stats {{ display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }}
  .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1rem 1.5rem; min-width: 140px; }}
  .stat-card h3 {{ color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; }}
  .stat-card p {{ font-size: 1.75rem; font-weight: 700; color: #38bdf8; }}
  .accuracy {{ color: {'#10b981' if accuracy >= 85 else '#f59e0b' if accuracy >= 70 else '#ef4444'} !important; }}
  table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
  th {{ background: #0f172a; color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; padding: 0.75rem 1rem; text-align: left; }}
  td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #334155; font-size: 0.85rem; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #243349; }}
  .query {{ max-width: 280px; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.7rem; font-weight: 600; color: #fff; }}
  .correct {{ color: #10b981; font-weight: 600; }}
  .wrong {{ color: #ef4444; font-weight: 600; }}
  footer {{ margin-top: 2rem; color: #475569; font-size: 0.8rem; text-align: center; }}
</style>
</head>
<body>
  <h1>🎓 DeKUT CS & IT FAQ — Validation Report</h1>
  <p class="meta">Generated: {timestamp} | School of Computer Science & IT, Dedan Kimathi University of Technology</p>

  <div class="stats">
    <div class="stat-card"><h3>Total Queries</h3><p>{total}</p></div>
    <div class="stat-card"><h3>Correct</h3><p style="color:#10b981">{correct}</p></div>
    <div class="stat-card"><h3>Wrong</h3><p style="color:#ef4444">{total - correct}</p></div>
    <div class="stat-card"><h3>Accuracy</h3><p class="accuracy">{accuracy:.1f}%</p></div>
  </div>

  <table>
    <thead>
      <tr>
        <th>#</th><th>Query</th><th>Category</th><th>Matched Rule</th><th>Conf.</th><th>Verdict</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>

  <footer>DeKUT FAQ Assistant · Theory of Computation · Phase 5 Validation</footer>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    print(col(f"\n  📄 HTML report saved: {output_path}", C.GREEN))


# ── Batch validation ───────────────────────────────────────────────────────────

def run_batch(use_ai: bool = False, generate_report: bool = False) -> None:
    print(col(f"\n{'═' * WIDTH}", C.CYAN, C.BOLD))
    print(col("  DeKUT FAQ Assistant — Batch Validation (40 queries)", C.WHITE, C.BOLD))
    print(col(f"  AI refinement: {'ON' if use_ai else 'OFF (offline mode)'}", C.GREY))
    print(col(f"{'═' * WIDTH}\n", C.CYAN, C.BOLD))

    correct = 0
    results_data = []

    for q in QUERIES:
        t0     = time.perf_counter()
        result = classify_query(q["query"])
        elapsed = (time.perf_counter() - t0) * 1000

        ai_response, _ = _try_refine(result, q["query"], use_ai)
        is_correct      = result.category == q["intent"]
        correct        += int(is_correct)

        print_result(
            query_text=q["query"],
            result=result,
            query_id=f"#{q['id']:02d}",
            expected_intent=q["intent"],
            ai_response=ai_response if use_ai else "",
        )
        print(col(f"  ⏱ Parsed in {elapsed:.1f} ms\n", C.GREY))

        results_data.append({
            "id":           q["id"],
            "query":        q["query"],
            "category":     result.category,
            "matched_rule": result.matched_rule,
            "confidence":   result.confidence,
            "expected":     q["intent"],
            "correct":      is_correct,
        })

    total    = len(QUERIES)
    accuracy = correct / total * 100

    print(col(f"{'═' * WIDTH}", C.CYAN, C.BOLD))
    print(col(f"  BATCH RESULT:  {correct}/{total} correct  ({accuracy:.1f}%)", C.WHITE, C.BOLD))

    per_intent: dict[str, dict] = {i: {"correct": 0, "total": 0} for i in INTENT_LABELS}
    for rd in results_data:
        per_intent[rd["expected"]]["total"] += 1
        if rd["correct"]:
            per_intent[rd["expected"]]["correct"] += 1

    print(col("\n  Per-intent breakdown:", C.GREY))
    for intent, stats in per_intent.items():
        bar_len  = int(stats["correct"] / max(stats["total"], 1) * 20)
        bar      = "█" * bar_len + "░" * (20 - bar_len)
        pct      = stats["correct"] / max(stats["total"], 1) * 100
        bar_col  = C.GREEN if pct >= 80 else (C.YELLOW if pct >= 50 else C.RED)
        print(
            col(f"  {intent:<26}", C.GREY) +
            col(bar, bar_col) +
            col(f"  {stats['correct']}/{stats['total']}  ({pct:.0f}%)", C.WHITE)
        )
    print(col(f"{'═' * WIDTH}\n", C.CYAN, C.BOLD))

    if generate_report:
        report_path = PROJECT_ROOT / "validation_report.html"
        generate_html_report(
            results_data,
            report_path,
            {"correct": correct, "total": total, "accuracy": accuracy},
        )


# ── Single query ───────────────────────────────────────────────────────────────

def run_single(query_text: str, use_ai: bool = False) -> None:
    result      = classify_query(query_text)
    ai_response, ai_used = _try_refine(result, query_text, use_ai)
    print_result(
        query_text=query_text,
        result=result,
        ai_response=ai_response if ai_used else "",
    )


# ── Interactive REPL ───────────────────────────────────────────────────────────

def run_interactive(use_ai: bool = False) -> None:
    print(col(f"\n{'═' * WIDTH}", C.CYAN, C.BOLD))
    print(col("  DeKUT CS & IT FAQ Assistant — Interactive Validation", C.WHITE, C.BOLD))
    print(col("  Type a query, an audio file path, or 'exit' to quit.", C.GREY))
    print(col(f"{'═' * WIDTH}\n", C.CYAN, C.BOLD))

    while True:
        try:
            raw = input(col("  ❯ Your query: ", C.CYAN, C.BOLD)).strip()
        except (EOFError, KeyboardInterrupt):
            print(col("\n\n  Goodbye!\n", C.GREY))
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "q"):
            print(col("\n  Goodbye!\n", C.GREY))
            break

        # Detect audio file path
        audio_extensions = {".mp3", ".ogg", ".wav", ".m4a", ".webm", ".opus"}
        if Path(raw).suffix.lower() in audio_extensions:
            raw = _try_transcribe(raw)

        run_single(raw, use_ai=use_ai)


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description="DeKUT FAQ Assistant — Standalone Validation Framework",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch validation against all 40 dataset queries.",
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        metavar="TEXT",
        help="Test a single text query.",
    )
    parser.add_argument(
        "--audio", "-a",
        type=str,
        metavar="PATH",
        help="Transcribe an audio file and test the resulting text.",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Enable GPT-4o response refinement (requires OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate an HTML validation report (used with --batch).",
    )

    args = parser.parse_args()

    if args.batch:
        run_batch(use_ai=args.ai, generate_report=args.report)
    elif args.query:
        run_single(args.query, use_ai=args.ai)
    elif args.audio:
        text = _try_transcribe(args.audio)
        run_single(text, use_ai=args.ai)
    else:
        run_interactive(use_ai=args.ai)


if __name__ == "__main__":
    main()
