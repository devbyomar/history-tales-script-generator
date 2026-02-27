"""ScriptGenerationNode — Stage A: writes the draft history script.

Stage B (FactTightenNode) follows to add trace tags and tighten facts.
"""

from __future__ import annotations

import json
from typing import Any

from history_tales_agent.prompts.templates import (
    SCRIPT_GENERATION_SYSTEM,
    SCRIPT_GENERATION_USER,
    HARD_GUARDRAILS_FEEDBACK,
    get_tone_instructions,
)
from history_tales_agent.narrative.lenses import resolve_lenses, build_lens_prompt_block
from history_tales_agent.narrative.geo import build_geo_prompt_block
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
    """Generate the complete history script."""
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
        f"- [{c.claim_id}] [{c.confidence}] {c.claim_text} (Source: {c.source_name})"
        for c in claims if c.confidence in ("High", "Moderate")
    )[:5000]

    # Build script-safe language lines from cross-checked claims
    script_language_lines = "\n".join(
        f"- [{c.claim_id}] {c.script_language}"
        for c in claims
        if c.script_language and c.confidence in ("High", "Moderate")
    )[:3000] or "None available."

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
        script_language_lines=script_language_lines,
        consensus_contested=contested_str,
        rehook_interval=f"{rehook_interval[0]}–{rehook_interval[1]}",
        rehook_words=rehook_words,
    )

    # ── Inject narrative lens & geo context (no-ops when not set) ──
    lenses = resolve_lenses(state.get("narrative_lens"))
    lens_block = build_lens_prompt_block(lenses, state.get("lens_strength", 0.6))
    geo_block = build_geo_prompt_block(
        geo_scope=state.get("geo_scope"),
        geo_anchor=state.get("geo_anchor"),
        mobility_mode=state.get("mobility_mode"),
    )
    if lens_block:
        user_prompt += lens_block
        logger.info("lens_injected", node="ScriptGenerationNode", lenses=[l.lens_id for l in lenses])
    if geo_block:
        user_prompt += geo_block
        logger.info("geo_injected", node="ScriptGenerationNode")

    # ── Inject lessons from previous runs ──
    lessons = load_lessons_prompt()
    if lessons:
        user_prompt = lessons + "\n\n" + user_prompt
        logger.info("lessons_injected", node="ScriptGenerationNode", lessons_len=len(lessons))

    # ── Inject hard-guardrail feedback so the LLM avoids known issues ──
    validation_issues = state.get("validation_issues", [])
    if validation_issues and iteration_count == 0:
        issues_text = "\n".join(f"  • {issue}" for issue in validation_issues)
        guardrail_feedback = HARD_GUARDRAILS_FEEDBACK.format(issues_text=issues_text)
        user_prompt = guardrail_feedback + "\n\n" + user_prompt
        logger.info("guardrail_feedback_injected", issues=len(validation_issues))

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
        script = call_llm(system_prompt, user_prompt, temperature=0.75, tier="fast")
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
    pre_expand_script = script  # Save in case expansion overshoots
    for attempt in range(1, MAX_EXPAND_ATTEMPTS + 1):
        if word_count >= min_words:
            break

        words_needed = target_words - word_count
        logger.warning(
            "script_under_target",
            word_count=word_count,
            min_words=min_words,
            words_needed=words_needed,
            attempt=attempt,
        )
        expand_system = (
            "You are an expert long-form YouTube history storyteller performing a "
            "SURGICAL expansion. You will add exactly the number of words "
            "requested, spread proportionally across the entire script. "
            "Do NOT rewrite existing sentences — INSERT new ones "
            "between them.\n\n"
            "RULES:\n"
            "1. Keep every existing sentence UNCHANGED — do not rephrase, "
            "merge, or delete anything.\n"
            "2. Spread new material EVENLY across the script — do not dump "
            "all additions into one stretch.\n"
            "3. Each new sentence must contain a concrete historical detail, "
            "a REAL person's name, or a functional sensory cue.\n"
            "4. Do NOT invent fictional characters. Every named person must "
            "be historically documented.\n"
            "5. Do NOT add filler, hedging, or meta-commentary.\n"
            "6. Output PURE SPOKEN TEXT — no section headers, no labels, no markers.\n"
            "7. Count your output carefully. Your FINAL word count must land "
            f"between {min_words} and {max_words}."
        )
        expand_user = (
            f"CURRENT word count: {word_count}\n"
            f"TARGET word count: {target_words}\n"
            f"ALLOWED range: {min_words}–{max_words}\n"
            f"WORDS TO ADD: approximately {words_needed}\n\n"
            f"Spread ~{words_needed} new words across the script below. "
            f"Add 2–4 new sentences throughout, each with a concrete "
            f"historical detail. Do NOT remove or change existing text.\n\n"
            f"Output ONLY the complete expanded script.\n\n"
            f"{script}"
        )
        try:
            script = call_llm(expand_system, expand_user, temperature=0.4, tier="fast")
            word_count = len(script.split())
            logger.info("script_expanded", word_count=word_count, attempt=attempt)
            # If expansion overshot massively (>20% over max), fall back to
            # the previous version to avoid drowning FactTighten.
            if word_count > int(max_words * 1.2):
                logger.warning(
                    "expansion_overshot",
                    word_count=word_count,
                    max_words=max_words,
                    action="reverting_to_pre_expansion",
                )
                script = pre_expand_script
                word_count = len(script.split())
                break
        except Exception as e:
            logger.error("script_expansion_failed", error=str(e), attempt=attempt)
            break

    return {
        "draft_script": script,
        "final_script": script,  # Also set final_script so downstream nodes work if fact_tighten is skipped
        "current_node": "ScriptGenerationNode",
    }
