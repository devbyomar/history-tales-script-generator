"""Feedback memory — persists QC issues and lessons across runs.

After each pipeline run, the finalize node saves the QC issues,
recommendations, and distilled lessons to a JSONL file.  On the next
run, the script-generation and outline nodes inject the most recent
lessons into their prompts so the agent avoids repeating the same
mistakes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DEFAULT_MEMORY_DIR = Path(".memory")
_FEEDBACK_FILE = "feedback_log.jsonl"
_LESSONS_FILE = "distilled_lessons.json"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


def _memory_dir() -> Path:
    d = _DEFAULT_MEMORY_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Write — called by FinalizeNode after every run
# ---------------------------------------------------------------------------


def save_run_feedback(
    *,
    topic_title: str,
    era: str,
    geo: str,
    word_count: int,
    target_words: int,
    qc_pass: bool,
    issues: list[str],
    recommendations: list[str],
    emotional_score: float,
    sensory_score: float,
    iteration_count: int,
) -> Path:
    """Append a feedback entry for this run and update distilled lessons."""

    entry: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "topic_title": topic_title,
        "era": era,
        "geo": geo,
        "word_count": word_count,
        "target_words": target_words,
        "qc_pass": qc_pass,
        "issues": issues,
        "recommendations": recommendations,
        "emotional_score": emotional_score,
        "sensory_score": sensory_score,
        "iteration_count": iteration_count,
    }

    # Append raw feedback
    feedback_path = _memory_dir() / _FEEDBACK_FILE
    with open(feedback_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info(
        "feedback_saved",
        topic=topic_title,
        issues=len(issues),
        recommendations=len(recommendations),
    )

    # Distill recurring lessons
    _update_distilled_lessons(entry)

    return feedback_path


# ---------------------------------------------------------------------------
# Distillation — extract patterns from feedback history
# ---------------------------------------------------------------------------


def _update_distilled_lessons(latest_entry: dict[str, Any]) -> None:
    """Read all feedback, extract recurring themes, write distilled lessons."""

    feedback_path = _memory_dir() / _FEEDBACK_FILE
    lessons_path = _memory_dir() / _LESSONS_FILE

    # Read all entries
    entries: list[dict[str, Any]] = []
    if feedback_path.exists():
        with open(feedback_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    if not entries:
        return

    # Categorise issues by pattern
    issue_counts: dict[str, int] = {}
    all_recommendations: list[str] = []
    word_count_misses: list[dict[str, int]] = []

    for entry in entries:
        for issue in entry.get("issues", []):
            # Normalise: strip leading ⚠️ and whitespace
            clean = issue.lstrip("⚠️ ").strip()
            # Group by first 60 chars to cluster similar issues
            key = clean[:60].lower()
            issue_counts[key] = issue_counts.get(key, 0) + 1

        for rec in entry.get("recommendations", []):
            clean = rec.lstrip("💡 ").strip()
            all_recommendations.append(clean)

        wc = entry.get("word_count", 0)
        tw = entry.get("target_words", 0)
        if wc and tw:
            word_count_misses.append({"actual": wc, "target": tw})

    # Build distilled lessons
    recurring_issues = [
        issue for issue, count in sorted(
            issue_counts.items(), key=lambda x: -x[1]
        )
        if count >= 1  # Keep all issues for now; raise threshold as history grows
    ][:15]  # Cap at 15 most common

    # Deduplicate recommendations (keep unique by first 80 chars)
    seen_recs: set[str] = set()
    unique_recs: list[str] = []
    for rec in all_recommendations:
        key = rec[:80].lower()
        if key not in seen_recs:
            seen_recs.add(key)
            unique_recs.append(rec)

    # Word count trend
    wc_trend = ""
    if word_count_misses:
        avg_ratio = sum(
            m["actual"] / m["target"] for m in word_count_misses
        ) / len(word_count_misses)
        if avg_ratio > 1.15:
            wc_trend = f"Scripts tend to run LONG (avg {avg_ratio:.0%} of target). Be more concise."
        elif avg_ratio < 0.85:
            wc_trend = f"Scripts tend to run SHORT (avg {avg_ratio:.0%} of target). Add more detail and scenes."

    distilled = {
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_runs": len(entries),
        "recurring_issues": recurring_issues,
        "top_recommendations": unique_recs[:10],
        "word_count_trend": wc_trend,
        "pass_rate": sum(1 for e in entries if e.get("qc_pass")) / len(entries),
    }

    with open(lessons_path, "w", encoding="utf-8") as f:
        json.dump(distilled, f, indent=2, ensure_ascii=False)

    logger.info(
        "lessons_distilled",
        total_runs=len(entries),
        recurring_issues=len(recurring_issues),
        pass_rate=f"{distilled['pass_rate']:.0%}",
    )


# ---------------------------------------------------------------------------
# Read — called by ScriptGeneration, Outline, RetentionPass nodes
# ---------------------------------------------------------------------------


def load_lessons_prompt() -> str:
    """Return a prompt fragment with distilled lessons from past runs.

    If no history exists, returns an empty string so prompts work
    unchanged on the first run.
    """
    lessons_path = _memory_dir() / _LESSONS_FILE

    if not lessons_path.exists():
        return ""

    try:
        with open(lessons_path, encoding="utf-8") as f:
            distilled = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""

    parts: list[str] = []

    parts.append("=== LESSONS FROM PREVIOUS RUNS ===")
    parts.append(f"(Based on {distilled.get('total_runs', 0)} previous pipeline runs, "
                 f"pass rate: {distilled.get('pass_rate', 0):.0%})")

    if distilled.get("word_count_trend"):
        parts.append(f"\n⚠️ WORD COUNT TREND: {distilled['word_count_trend']}")

    issues = distilled.get("recurring_issues", [])
    if issues:
        parts.append("\n🔴 RECURRING ISSUES TO AVOID:")
        for i, issue in enumerate(issues, 1):
            parts.append(f"  {i}. {issue}")

    recs = distilled.get("top_recommendations", [])
    if recs:
        parts.append("\n✅ RECOMMENDATIONS TO FOLLOW:")
        for i, rec in enumerate(recs, 1):
            parts.append(f"  {i}. {rec}")

    parts.append("\nApply these lessons proactively. Do NOT repeat past mistakes.")
    parts.append("=== END LESSONS ===\n")

    return "\n".join(parts)


def load_last_run_feedback() -> dict[str, Any] | None:
    """Return the most recent feedback entry, or None if no history."""
    feedback_path = _memory_dir() / _FEEDBACK_FILE

    if not feedback_path.exists():
        return None

    last_line = ""
    with open(feedback_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last_line = line.strip()

    if not last_line:
        return None

    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return None
