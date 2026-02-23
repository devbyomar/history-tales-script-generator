"""ScriptGenerationNode — writes the complete documentary script."""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import (
    SCRIPT_GENERATION_SYSTEM,
    SCRIPT_GENERATION_USER,
    get_tone_instructions,
)
from history_tales_agent.state import (
    Claim,
    EmotionalDriver,
    QCReport,
    ScriptSection,
    TimelineBeat,
    TopicCandidate,
)
from history_tales_agent.utils.llm import call_llm
from history_tales_agent.utils.feedback_memory import load_lessons_prompt
from history_tales_agent.utils.reference_library import find_best_reference, build_reference_prompt
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


def script_generation_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate the complete documentary script."""
    logger.info("node_start", node="ScriptGenerationNode")

    chosen: TopicCandidate | None = state.get("chosen_topic")
    outline: list[ScriptSection] = state.get("script_outline", [])
    beats: list[TimelineBeat] = state.get("timeline_beats", [])
    drivers: list[EmotionalDriver] = state.get("emotional_drivers", [])
    claims: list[Claim] = state.get("claims", [])
    consensus_contested = state.get("consensus_vs_contested", [])
    tone = state.get("tone", "cinematic-serious")
    target_words = state.get("target_words", 1860)
    min_words = state.get("min_words", 1674)
    max_words = state.get("max_words", 2046)
    video_length = state.get("video_length_minutes", 12)
    format_tag = state.get("format_tag", "Countdown")
    rehook_interval = state.get("rehook_interval", (60, 90))
    iteration_count = state.get("iteration_count", 0)
    qc_report: QCReport | None = state.get("qc_report")

    if not chosen or not outline:
        return {
            "errors": state.get("errors", []) + ["ScriptGenerationNode: Missing data"],
            "current_node": "ScriptGenerationNode",
        }

    tone_instructions = get_tone_instructions(tone)
    avg_rehook = (rehook_interval[0] + rehook_interval[1]) // 2
    rehook_words = int(avg_rehook * (155 / 60))  # Words per rehook interval

    outline_json = json.dumps(
        [{"section": s.section_name, "description": s.description,
          "target_words": s.target_word_count, "re_hooks": s.re_hooks,
          "key_beats": s.key_beats}
         for s in outline], indent=2,
    )

    timeline_json = json.dumps(
        [{"time": b.timestamp, "event": b.event, "pov": b.pov, "tension": b.tension_level}
         for b in beats], indent=2,
    )

    emotional_json = json.dumps(
        [{"type": d.driver_type, "desc": d.description, "pov": d.pov}
         for d in drivers], indent=2,
    )

    verified = "\n".join(
        f"- [{c.confidence}] {c.claim_text} (Source: {c.source_name})"
        for c in claims if c.confidence in ("High", "Moderate")
    )[:5000]

    contested_str = "\n".join(
        f"- {cc.get('claim', '')}: {cc.get('conflict', '')} → {cc.get('treatment', '')}"
        for cc in consensus_contested
    ) if consensus_contested else "None identified."

    system_prompt = SCRIPT_GENERATION_SYSTEM.format(
        tone=tone,
        tone_instructions=tone_instructions,
    )

    user_prompt = SCRIPT_GENERATION_USER.format(
        target_words=target_words,
        min_words=min_words,
        max_words=max_words,
        video_length_minutes=video_length,
        topic_title=chosen.title,
        format_tag=format_tag,
        tone=tone,
        outline_json=outline_json,
        timeline_beats_json=timeline_json,
        emotional_drivers_json=emotional_json,
        verified_claims=verified,
        consensus_contested=contested_str,
        rehook_interval=f"{rehook_interval[0]}–{rehook_interval[1]}",
        rehook_words=rehook_words,
    )

    # ── Inject lessons from previous runs ──
    lessons = load_lessons_prompt()
    if lessons:
        user_prompt = lessons + "\n\n" + user_prompt
        logger.info("lessons_injected", node="ScriptGenerationNode", lessons_len=len(lessons))

    # ── Inject best-matching reference transcript as style exemplar ──
    if iteration_count == 0:  # only on the first attempt — retries focus on QC fixes
        ref = find_best_reference(
            duration_minutes=video_length,
            tone=tone,
            format_tag=format_tag,
            era=chosen.era if chosen else None,
            geo=chosen.geo if chosen else None,
        )
        if ref:
            ref_prompt = build_reference_prompt(ref, target_duration_minutes=video_length)
            user_prompt = ref_prompt + "\n\n" + user_prompt
            logger.info(
                "reference_injected",
                node="ScriptGenerationNode",
                title=ref.get("title", "?"),
            )

    # ── On retry: inject QC feedback so the LLM knows what to fix ──
    if iteration_count > 0 and qc_report and qc_report.issues:
        qc_feedback = (
            f"\n\n⚠️ REWRITE ATTEMPT {iteration_count} — PREVIOUS QC FAILED.\n"
            f"The previous draft had these issues that MUST be fixed:\n"
        )
        for i, issue in enumerate(qc_report.issues, 1):
            qc_feedback += f"  {i}. {issue}\n"
        if qc_report.word_count:
            qc_feedback += (
                f"\nPrevious draft was {qc_report.word_count} words. "
                f"Target range is {min_words}–{max_words} (target: {target_words}).\n"
                f"PAY CAREFUL ATTENTION to the word count constraint.\n"
            )
        user_prompt = qc_feedback + "\n" + user_prompt
        logger.info(
            "qc_feedback_injected",
            iteration=iteration_count,
            issues=len(qc_report.issues),
        )

    try:
        script = call_llm(system_prompt, user_prompt, temperature=0.75)
    except Exception as e:
        logger.error("script_generation_failed", error=str(e))
        return {
            "errors": state.get("errors", []) + [f"ScriptGenerationNode: {str(e)}"],
            "current_node": "ScriptGenerationNode",
        }

    word_count = len(script.split())
    logger.info("script_generated", word_count=word_count, target=target_words)

    # -----------------------------------------------------------------------
    # Retry loop: if word count is significantly below target, ask the LLM to
    # expand the draft.  Up to 2 expansion attempts.
    # -----------------------------------------------------------------------
    MAX_EXPAND_ATTEMPTS = 2
    for attempt in range(1, MAX_EXPAND_ATTEMPTS + 1):
        if word_count >= min_words:
            break
        logger.warning(
            "script_under_target",
            word_count=word_count,
            min_words=min_words,
            attempt=attempt,
        )
        expand_system = (
            "You are an expert history documentary scriptwriter. "
            "The draft below is too short. Your job is to EXPAND it — "
            "add richer sensory detail, deepen character moments, add "
            "historical context, and develop transitions — until the script "
            "meets the target word count. Do NOT remove or summarise existing "
            "content. Keep every section marker intact. "
            "IMPORTANT: Do NOT invent fictional characters. Every named person "
            "must be a real, historically documented individual."
        )
        expand_user = (
            f"The script below is {word_count} words. "
            f"It MUST be between {min_words} and {max_words} words "
            f"(target: {target_words}).\n\n"
            f"Expand it to reach AT LEAST {min_words} words. "
            f"Add depth, not filler. Every added sentence must contain "
            f"a concrete detail, a REAL historical person, or a sensory cue. "
            f"Do NOT invent fictional characters.\n\n"
            f"Output ONLY the complete expanded script.\n\n"
            f"{script}"
        )
        try:
            script = call_llm(expand_system, expand_user, temperature=0.7)
            word_count = len(script.split())
            logger.info("script_expanded", word_count=word_count, attempt=attempt)
        except Exception as e:
            logger.error("script_expansion_failed", error=str(e), attempt=attempt)
            break

    return {
        "final_script": script,
        "current_node": "ScriptGenerationNode",
    }
