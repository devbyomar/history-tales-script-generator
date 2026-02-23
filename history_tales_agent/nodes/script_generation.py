"""ScriptGenerationNode — Stage A: writes the draft documentary script.

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

    # -----------------------------------------------------------------------
    # Chunked generation: for longer scripts (>6000 words target) we split
    # the outline into batches of sections and generate each batch separately
    # to stay within the LLM's output-token ceiling (~16 384 tokens ≈ 12 000
    # words).  Shorter scripts are generated in a single call as before.
    # -----------------------------------------------------------------------
    CHUNK_WORD_CEILING = 6000  # max words we trust a single LLM call to produce

    if target_words <= CHUNK_WORD_CEILING:
        # --- Single-shot generation (short/medium videos) -----------------
        script = _generate_single_shot(
            system_prompt, user_prompt, target_words, min_words, max_words
        )
    else:
        # --- Chunked generation (long videos 30+ min) ---------------------
        script = _generate_chunked(
            system_prompt=system_prompt,
            user_prompt_base=user_prompt,
            outline=outline,
            target_words=target_words,
            min_words=min_words,
            max_words=max_words,
        )

    if script is None:
        return {
            "errors": state.get("errors", []) + [
                "ScriptGenerationNode: All generation attempts returned empty/near-empty"
            ],
            "current_node": "ScriptGenerationNode",
        }

    return {
        "draft_script": script,
        "final_script": script,
        "current_node": "ScriptGenerationNode",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_single_shot(
    system_prompt: str,
    user_prompt: str,
    target_words: int,
    min_words: int,
    max_words: int,
) -> str | None:
    """Generate the full script in one LLM call with expansion retries."""
    try:
        script = call_llm(system_prompt, user_prompt, temperature=0.75)
    except Exception as e:
        logger.error("script_generation_failed", error=str(e))
        return None

    word_count = len(script.split())
    logger.info("script_generated", word_count=word_count, target=target_words)

    if word_count < 100:
        logger.error(
            "script_generation_empty",
            word_count=word_count,
            msg="LLM returned empty/near-empty script",
        )
        return None

    # Expansion retries — only for single-shot mode
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
            expanded = call_llm(expand_system, expand_user, temperature=0.7)
            expanded_wc = len(expanded.split())
            logger.info("script_expanded", word_count=expanded_wc, attempt=attempt)
            if expanded_wc > word_count:
                script = expanded
                word_count = expanded_wc
            else:
                logger.warning(
                    "expansion_not_longer",
                    input_wc=word_count,
                    output_wc=expanded_wc,
                    attempt=attempt,
                    msg="Expansion returned fewer/equal words — keeping previous draft",
                )
                break
        except Exception as e:
            logger.error("script_expansion_failed", error=str(e), attempt=attempt)
            break

    return script


def _generate_chunked(
    system_prompt: str,
    user_prompt_base: str,
    outline: list,
    target_words: int,
    min_words: int,
    max_words: int,
) -> str | None:
    """Generate the script in chunks of sections, then stitch together.

    Splits the outline into batches where each batch targets ≤5 000 words,
    keeping the LLM well within its output-token ceiling.
    """
    BATCH_WORD_TARGET = 5000

    # Build batches of sections
    batches: list[list[dict]] = []
    current_batch: list[dict] = []
    current_words = 0

    sections_data = [
        {
            "section": s.section_name,
            "description": s.description,
            "target_words": s.target_word_count,
            "re_hooks": s.re_hooks,
            "key_beats": s.key_beats,
        }
        for s in outline
    ]

    for sec in sections_data:
        if current_words + sec["target_words"] > BATCH_WORD_TARGET and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_words = 0
        current_batch.append(sec)
        current_words += sec["target_words"]

    if current_batch:
        batches.append(current_batch)

    logger.info(
        "chunked_generation_plan",
        total_sections=len(sections_data),
        batches=len(batches),
        batch_sizes=[sum(s["target_words"] for s in b) for b in batches],
    )

    # Generate each batch
    script_parts: list[str] = []
    total_words = 0
    previous_ending = ""  # Last ~200 words of previous chunk for continuity

    for batch_idx, batch in enumerate(batches):
        batch_target = sum(s["target_words"] for s in batch)
        batch_min = int(batch_target * 0.9)
        batch_max = int(batch_target * 1.1)
        batch_sections_json = json.dumps(batch, indent=2)

        section_names = [s["section"] for s in batch]
        is_first = batch_idx == 0
        is_last = batch_idx == len(batches) - 1

        continuity_context = ""
        if previous_ending:
            continuity_context = (
                f"\n\nCONTINUITY — the previous chunk ended with:\n"
                f'"""\n{previous_ending}\n"""\n'
                f"Continue seamlessly from where this left off. "
                f"Do NOT repeat content already written. "
                f"Do NOT write a new title or opening.\n"
            )

        chunk_instructions = (
            f"{'Write' if is_first else 'Continue writing'} the documentary script.\n"
            f"This is chunk {batch_idx + 1} of {len(batches)}.\n"
            f"{'Start with the title and opening.' if is_first else 'Continue from the previous chunk.'}\n"
            f"Write ONLY these sections: {', '.join(section_names)}\n"
            f"Target for this chunk: {batch_target} words "
            f"(STRICT: between {batch_min} and {batch_max})\n\n"
            f"Sections for this chunk:\n{batch_sections_json}\n"
            f"{continuity_context}\n\n"
            f"{'Include the closing disclaimer at the end.' if is_last else 'Do NOT include a disclaimer or final sign-off — more sections follow.'}\n\n"
            f"FULL CONTEXT (for reference — do NOT rewrite earlier sections):\n"
            f"{user_prompt_base}\n\n"
            f"Output ONLY the script text for the sections listed above."
        )

        try:
            chunk = call_llm(system_prompt, chunk_instructions, temperature=0.75)
        except Exception as e:
            logger.error(
                "chunk_generation_failed",
                batch=batch_idx + 1,
                sections=section_names,
                error=str(e),
            )
            # If first chunk fails, we can't continue
            if is_first:
                return None
            # Otherwise, log and stop — return what we have
            logger.warning(
                "chunk_generation_partial",
                completed_batches=batch_idx,
                total_batches=len(batches),
            )
            break

        chunk_wc = len(chunk.split())
        logger.info(
            "chunk_generated",
            batch=batch_idx + 1,
            sections=section_names,
            word_count=chunk_wc,
            target=batch_target,
        )

        if chunk_wc < 50:
            logger.error(
                "chunk_empty",
                batch=batch_idx + 1,
                word_count=chunk_wc,
            )
            if is_first:
                return None
            break

        script_parts.append(chunk)
        total_words += chunk_wc

        # Save ending for continuity
        words = chunk.split()
        previous_ending = " ".join(words[-200:]) if len(words) > 200 else chunk

    if not script_parts:
        return None

    script = "\n\n".join(script_parts)
    word_count = len(script.split())
    logger.info(
        "chunked_generation_complete",
        total_words=word_count,
        target=target_words,
        chunks_used=len(script_parts),
    )

    return script
