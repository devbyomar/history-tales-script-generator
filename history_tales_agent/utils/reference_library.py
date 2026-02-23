"""Reference transcript library — loads successful video transcripts as style exemplars.

The `references/` directory contains JSON files representing successful
YouTube video transcripts in a rich chunked format.  At script-generation
time, the most relevant transcript is selected by matching era, narrative
style, themes, duration, and geography.  The transcript chunks are
reconstructed and injected into the prompt as a *style exemplar* — the
LLM studies pacing, hooks, story structure, and transitions without
copying content.

See `references/README.md` for the full JSON schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REFERENCES_DIR = Path("references")

# ---------------------------------------------------------------------------
# Helpers — extract normalised fields from the rich JSON format
# ---------------------------------------------------------------------------


def _get_era(ref: dict[str, Any]) -> str:
    """Extract the era string, handling both flat and nested formats."""
    era = ref.get("era", "")
    if isinstance(era, dict):
        return era.get("macro", "")
    return str(era)


def _get_geo_regions(ref: dict[str, Any]) -> list[str]:
    """Extract all geographic regions as a flat lowercase list."""
    geo = ref.get("geographic_focus", {})
    if isinstance(geo, dict):
        regions = geo.get("primary_regions", []) + geo.get("secondary_regions", [])
        regions += geo.get("noted_locations_verbatim", [])
        return [r.lower() for r in regions]
    # Fallback: flat string
    if ref.get("geo"):
        return [ref["geo"].lower()]
    return []


def _get_narrative_styles(ref: dict[str, Any]) -> list[str]:
    """Extract narrative style tags as lowercase list."""
    styles = ref.get("narrative_style", [])
    if isinstance(styles, list):
        return [s.lower() for s in styles]
    return []


def _get_themes(ref: dict[str, Any]) -> list[str]:
    """Extract theme tags as lowercase list."""
    themes = ref.get("themes", [])
    if isinstance(themes, list):
        return [t.lower() for t in themes]
    return []


def _get_retrieval_tags(ref: dict[str, Any]) -> list[str]:
    """Extract retrieval tags as lowercase list."""
    tags = ref.get("retrieval_tags", ref.get("tags", []))
    if isinstance(tags, list):
        return [t.lower() for t in tags]
    return []


def _get_story_structures(ref: dict[str, Any]) -> list[str]:
    """Extract story structure labels."""
    structs = ref.get("story_structures_present", [])
    return [s.lower() for s in structs]


def _reconstruct_transcript(ref: dict[str, Any]) -> str:
    """Reconstruct a readable transcript from chunks.

    Concatenates each chunk's verbatim_excerpt_sample with its label
    and summary as section headers, preserving the narrative flow.
    Falls back to a flat 'transcript' field if present.
    """
    # Flat transcript fallback (simple format)
    if ref.get("transcript"):
        return ref["transcript"]

    chunks = ref.get("chunks", [])
    if not chunks:
        return ""

    parts: list[str] = []
    for chunk in chunks:
        labels = ", ".join(chunk.get("labels", []))
        summary = chunk.get("summary", "")
        excerpt = chunk.get("verbatim_excerpt_sample", "")
        if not excerpt:
            continue

        header = f"[{labels}]" if labels else ""
        if summary:
            header += f" {summary}" if header else summary

        if header:
            parts.append(f"--- {header} ---")
        parts.append(excerpt)
        parts.append("")  # blank line between chunks

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_all_references() -> list[dict[str, Any]]:
    """Load every JSON file from the references directory."""
    ref_dir = _REFERENCES_DIR
    if not ref_dir.exists():
        logger.info("no_references_dir", path=str(ref_dir))
        return []

    refs: list[dict[str, Any]] = []
    for path in sorted(ref_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            # Skip the example template
            if data.get("doc_id") == "example_template":
                continue

            # Validate: must have chunks with excerpts OR a transcript field
            transcript = _reconstruct_transcript(data)
            if len(transcript.split()) < 50:
                logger.warning("skipping_short_reference", path=str(path))
                continue

            data["_path"] = str(path)
            data["_transcript"] = transcript  # cache reconstructed text
            refs.append(data)
        except Exception as exc:
            logger.warning("failed_to_load_reference", path=str(path), error=str(exc))
    logger.info("references_loaded", count=len(refs))
    return refs


# ---------------------------------------------------------------------------
# Scoring / matching
# ---------------------------------------------------------------------------


def _score_relevance(
    ref: dict[str, Any],
    *,
    duration_minutes: int,
    tone: str,
    format_tag: str,
    era: str | None = None,
    geo: str | None = None,
) -> float:
    """Score how relevant a reference transcript is to the current run.

    Higher = more relevant.  Weights:
      - Duration proximity:   25 pts
      - Era overlap:          25 pts  (macro era match)
      - Narrative style/tone: 20 pts  (matches against narrative_style list)
      - Theme/tag overlap:    15 pts  (retrieval_tags + themes)
      - Geo overlap:          10 pts  (any region match)
      - Story structure:       5 pts  (bonus for matching format patterns)
    """
    score = 0.0

    # Duration proximity (max 25)
    ref_dur = ref.get("duration_minutes", 0)
    if ref_dur:
        diff = abs(ref_dur - duration_minutes)
        if diff == 0:
            score += 25
        elif diff <= 2:
            score += 20
        elif diff <= 5:
            score += 15
        elif diff <= 10:
            score += 8
        elif diff <= 20:
            score += 3

    # Era overlap (max 25)
    ref_era = _get_era(ref).lower()
    if era:
        era_low = era.lower()
        if ref_era and (era_low in ref_era or ref_era in era_low):
            score += 25
        else:
            # Check retrieval tags for era keywords
            ref_tags = _get_retrieval_tags(ref)
            if any(era_low in tag or tag in era_low for tag in ref_tags):
                score += 10

    # Narrative style / tone match (max 20)
    ref_styles = _get_narrative_styles(ref)
    tone_low = tone.lower()
    # Direct tone match in narrative_style
    if any(tone_low in s or s in tone_low for s in ref_styles):
        score += 20
    else:
        # Partial: "cinematic" in "cinematic-serious", etc.
        tone_parts = set(tone_low.replace("-", "_").split("_"))
        style_parts = set()
        for s in ref_styles:
            style_parts.update(s.replace("-", "_").split("_"))
        overlap = tone_parts & style_parts
        if overlap:
            score += 10

    # Theme / tag overlap (max 15)
    ref_themes = set(_get_themes(ref) + _get_retrieval_tags(ref))
    if ref_themes:
        # Build a simple keyword set from the current run context
        run_keywords = set()
        if era:
            run_keywords.update(era.lower().split())
        if geo:
            run_keywords.update(geo.lower().split())
        run_keywords.update(tone_low.replace("-", "_").split("_"))
        run_keywords.update(format_tag.lower().replace(" ", "_").split("_"))
        # Remove very short / common words
        run_keywords = {w for w in run_keywords if len(w) > 2}

        overlap_count = sum(
            1 for t in ref_themes
            if any(kw in t or t in kw for kw in run_keywords)
        )
        score += min(overlap_count * 3, 15)

    # Geo overlap (max 10)
    ref_regions = _get_geo_regions(ref)
    if geo and ref_regions:
        geo_low = geo.lower()
        if any(geo_low in r or r in geo_low for r in ref_regions):
            score += 10

    # Story structure bonus (max 5)
    ref_structures = _get_story_structures(ref)
    fmt_low = format_tag.lower().replace(" ", "_")
    structure_map = {
        "countdown": ["statistics_crescendo", "evidence_numbers"],
        "one_room": ["case_study_vignette"],
        "two_truths": ["myth_to_reality_reframes", "counterargument"],
        "chain_reaction": ["doctrine_shift"],
        "impossible_choice": ["case_study_vignette"],
        "hunt": ["in_medias_res_hook"],
    }
    matching_structs = structure_map.get(fmt_low, [])
    if any(s in ref_structures for s in matching_structs):
        score += 5

    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_MIN_RELEVANCE_SCORE = 10  # Low bar — any era or style match qualifies


def find_best_reference(
    *,
    duration_minutes: int,
    tone: str,
    format_tag: str,
    era: str | None = None,
    geo: str | None = None,
) -> Optional[dict[str, Any]]:
    """Return the most relevant reference transcript, or None.

    Returns the full reference dict (including reconstructed '_transcript')
    if the best match exceeds the minimum relevance threshold.
    """
    refs = _load_all_references()
    if not refs:
        return None

    scored = [
        (
            _score_relevance(
                r,
                duration_minutes=duration_minutes,
                tone=tone,
                format_tag=format_tag,
                era=era,
                geo=geo,
            ),
            r,
        )
        for r in refs
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_ref = scored[0]

    logger.info(
        "reference_selection",
        best_title=best_ref.get("title", "?"),
        best_score=best_score,
        total_refs=len(refs),
    )

    if best_score < _MIN_RELEVANCE_SCORE:
        logger.info("no_reference_above_threshold", threshold=_MIN_RELEVANCE_SCORE)
        return None

    return best_ref


def _extract_structural_dna(ref: dict[str, Any]) -> str:
    """Distil the abstract structural techniques from a reference transcript.

    Instead of just listing chunks, this analyses *why* the architecture
    works — producing transferable craft principles the LLM can apply to
    any topic.
    """
    chunks = ref.get("chunks", [])
    if not chunks:
        return ""

    lines: list[str] = []

    # 1. Opening strategy
    first = chunks[0]
    first_labels = [l.lower() for l in first.get("labels", [])]
    if "opening_image" in first_labels:
        lines.append(
            "• OPENING: Starts in-scene with a specific person, place, and sensory "
            "detail — NOT with background context. The viewer is dropped into a moment "
            "before they understand its significance."
        )
    else:
        lines.append(
            "• OPENING: Leads with context or thesis framing before the first scene."
        )

    # 2. Thesis placement
    for i, ch in enumerate(chunks[:5]):
        if "HISTORIAN_THESIS" in ch.get("labels", []):
            lines.append(
                f"• THESIS: The central argument is planted in segment {i + 1} "
                f"(early, before deep detail). This gives the viewer a framework "
                f"to interpret everything that follows."
            )
            break

    # 3. Escalation pattern
    evidence_positions = []
    resolution_positions = []
    for i, ch in enumerate(chunks):
        labels = ch.get("labels", [])
        if "EVIDENCE_NUMBERS" in labels:
            evidence_positions.append(i + 1)
        if "RESOLUTION" in labels:
            resolution_positions.append(i + 1)

    if evidence_positions:
        lines.append(
            f"• EVIDENCE DISTRIBUTION: Data/statistics appear at segments "
            f"{', '.join(str(p) for p in evidence_positions)} — spread across the "
            f"narrative, never dumped in one block. Each data point arrives when the "
            f"viewer *needs* it to understand what just happened."
        )

    # 4. Counterargument / tension
    for i, ch in enumerate(chunks):
        if "COUNTERARGUMENT" in ch.get("labels", []):
            lines.append(
                f"• COUNTERPOINT: An opposing perspective or complication appears at "
                f"segment {i + 1}, preventing the narrative from feeling one-sided. "
                f"This re-engages skeptical viewers."
            )
            break

    # 5. Closing strategy
    last = chunks[-1]
    last_summary = last.get("summary", "").lower()
    if any(kw in last_summary for kw in ["reunion", "epilogue", "legacy", "return", "callback"]):
        lines.append(
            "• CLOSING: Returns to the human/image from the opening — creating a "
            "narrative loop. The ending recontextualises the beginning."
        )

    # 6. Chunk count / pacing density
    total = len(chunks)
    lines.append(
        f"• PACING: {total} distinct segments — roughly one shift in focus every "
        f"{max(1, round(ref.get('duration_minutes', 30) / total))} minutes. "
        f"No single idea overstays."
    )

    return "\n".join(lines)


def build_reference_prompt(
    ref: dict[str, Any],
    *,
    target_duration_minutes: int | None = None,
    max_words: int = 3000,
) -> str:
    """Build a prompt section from a reference transcript.

    The prompt heavily emphasises *transferable structural craft* — the
    abstract techniques that make the reference work — and explicitly
    forbids topic gravity (the LLM leaning toward the reference's
    subject matter).

    If *target_duration_minutes* is provided, the prompt includes a
    DURATION SCALING section that teaches the LLM how to compress or
    expand the reference architecture proportionally.
    """
    title = ref.get("title", "Unknown")  # used only for logging, not in prompt
    views = ref.get("views", 0)
    duration = ref.get("duration_minutes", "?")
    narrative_style = ", ".join(ref.get("narrative_style", []))

    # Story structure analysis from chunks
    structures = ref.get("story_structures_present", [])
    structures_str = ", ".join(structures) if structures else "N/A"

    # Chunk structure summary — shows the architectural blueprint
    chunks = ref.get("chunks", [])
    structure_map = ""
    if chunks:
        lines = []
        for i, chunk in enumerate(chunks, 1):
            labels = ", ".join(chunk.get("labels", []))
            summary = chunk.get("summary", "")
            lines.append(f"  {i}. [{labels}] {summary}")
        structure_map = "\n".join(lines)

    # Abstract structural DNA — the transferable craft principles
    structural_dna = _extract_structural_dna(ref)

    # Reconstructed transcript
    transcript = ref.get("_transcript", _reconstruct_transcript(ref))
    words = transcript.split()
    if len(words) > max_words:
        transcript = " ".join(words[:max_words]) + "\n\n[... transcript trimmed for length ...]"

    views_str = f"{views:,}" if isinstance(views, int) and views > 0 else "N/A"

    prompt = (
        "══════════════════════════════════════════════════════════════\n"
        "  CRAFT REFERENCE — STRUCTURAL & PACING GUIDE ONLY\n"
        "══════════════════════════════════════════════════════════════\n\n"
        "⚠️  CRITICAL: TOPIC INDEPENDENCE RULE\n"
        "The reference below is about a COMPLETELY DIFFERENT subject than yours.\n"
        "You must IGNORE its topic, era, people, and facts entirely.\n"
        "Extract ONLY the abstract craft — the structural skeleton, pacing rhythm,\n"
        "escalation patterns, and narrative techniques that made it successful.\n"
        "Your script's topic, content, and characters are defined solely by the\n"
        "outline, timeline beats, and verified claims provided separately below.\n"
        "If you catch yourself gravitating toward the reference's subject matter,\n"
        "STOP and refocus on YOUR assigned topic.\n\n"
        f"Source: A successful documentary ({views_str} views, {duration} min)\n"
        f"Narrative Style: {narrative_style}\n"
        f"Story Structures Used: {structures_str}\n\n"
    )

    # Structural DNA — the abstract, transferable principles
    if structural_dna:
        prompt += (
            "── WHAT MAKES THIS REFERENCE WORK (transferable principles) ──\n\n"
            f"{structural_dna}\n\n"
        )

    if structure_map:
        prompt += (
            "── ARCHITECTURAL BLUEPRINT (segment-by-segment structure) ──\n"
            "Study the *rhythm* of how segment types alternate — not the content:\n\n"
            f"{structure_map}\n\n"
        )

    # ── Duration scaling guidance ──
    ref_dur = ref.get("duration_minutes")
    if target_duration_minutes and ref_dur and isinstance(ref_dur, (int, float)) and ref_dur > 0:
        ratio = target_duration_minutes / ref_dur
        ref_segments = len(chunks) if chunks else 0

        if ratio < 0.85:
            # Compression needed
            ideal_segments = max(4, round(ref_segments * ratio))
            prompt += (
                "── DURATION SCALING — COMPRESSION ──\n\n"
                f"The reference is {ref_dur} minutes. YOUR script targets ~{target_duration_minutes} minutes\n"
                f"(ratio ≈ {ratio:.2f}×). You MUST scale the architecture DOWN:\n\n"
                f"• The reference uses {ref_segments} segments. Aim for roughly {ideal_segments}.\n"
                "• PRESERVE the opening cold open and the closing loop — these are\n"
                "  non-negotiable bookends that define the reference's power.\n"
                "• MERGE middle segments thematically. If the reference has 5 segments\n"
                "  of escalating evidence, condense to 2–3 that still ratchet tension.\n"
                "• MAINTAIN the *rhythm* — alternate between narrative, analysis, and\n"
                "  action even with fewer segments. Do not flatten into one mode.\n"
                "• CUT parallel subplots or secondary character arcs first. Keep the\n"
                "  single strongest narrative thread.\n"
                "• Each remaining segment should be proportionally shorter, not just\n"
                "  the segment count. A 10-minute script cannot have 5-minute segments.\n"
                "• Think of it as a highlight reel of the *structure*, not the content.\n\n"
            )
        elif ratio > 1.15:
            # Expansion needed
            ideal_segments = round(ref_segments * ratio)
            prompt += (
                "── DURATION SCALING — EXPANSION ──\n\n"
                f"The reference is {ref_dur} minutes. YOUR script targets ~{target_duration_minutes} minutes\n"
                f"(ratio ≈ {ratio:.2f}×). You MUST scale the architecture UP:\n\n"
                f"• The reference uses {ref_segments} segments. Aim for roughly {ideal_segments}.\n"
                "• PRESERVE the opening cold open and the closing loop unchanged.\n"
                "• SPLIT dense middle segments into multiple beats. A single 'rising\n"
                "  action' segment can become 2–3 stages with breathing room between.\n"
                "• ADD deeper context and scene-setting between action segments.\n"
                "  Use 'humanising detail' pauses — sensory moments that immerse.\n"
                "• INTRODUCE secondary narrative threads or perspective shifts that\n"
                "  weave back into the main arc.\n"
                "• Let transitions breathe. The pivot sentences can become full\n"
                "  bridging paragraphs that shift mood gradually.\n\n"
            )
        else:
            # Close enough — no special scaling needed
            prompt += (
                "── DURATION SCALING ──\n\n"
                f"The reference ({ref_dur} min) closely matches your target (~{target_duration_minutes} min).\n"
                f"You can follow its {ref_segments}-segment architecture at approximately 1:1 scale.\n\n"
            )

    prompt += (
        "── WHAT TO EXTRACT FROM THE TRANSCRIPT BELOW ──\n\n"
        "Read the transcript to absorb these ABSTRACT techniques:\n"
        "1. COLD OPEN MECHANICS: How does the first paragraph create urgency\n"
        "   before the viewer understands context? What is withheld vs revealed?\n"
        "2. ESCALATION CADENCE: How frequently does tension ratchet up? Notice\n"
        "   that stakes never plateau — each segment raises them.\n"
        "3. EVIDENCE INTEGRATION: Statistics and facts are embedded inside\n"
        "   narrative action, not presented as standalone data dumps.\n"
        "4. TRANSITION CRAFT: How does the writer move between segments?\n"
        "   Look for pivot sentences that close one idea and open the next.\n"
        "5. OPEN LOOP MANAGEMENT: Questions are posed, then answered 2–3\n"
        "   segments later — keeping the viewer leaning forward.\n"
        "6. SENTENCE RHYTHM: Short declarative sentences after longer\n"
        "   descriptive ones. Impact through variation, not uniformity.\n"
        "7. PERSPECTIVE SHIFTS: Alternating between protagonists, antagonists,\n"
        "   and omniscient narration to create dramatic irony.\n"
        "8. CLOSING LOOP: The ending returns to — and recontextualises — the\n"
        "   opening image or person.\n"
        "9. CONTINUOUS MOTION: Notice that the reference NEVER stops to lecture.\n"
        "   There is no standalone 'why this matters' essay. Relevance is shown\n"
        "   through action. Myth-busting lands as dramatic reveals inside scenes,\n"
        "   not as sidebar bullet lists. The story never pauses to explain itself.\n\n"
        "DO NOT extract: topic, subject matter, names, dates, facts, specific\n"
        "phrases, or any content. These belong to the reference, not your script.\n\n"
        "─── BEGIN REFERENCE TRANSCRIPT ───\n\n"
        f"{transcript}\n\n"
        "─── END REFERENCE TRANSCRIPT ───\n\n"
        "══════════════════════════════════════════════════════════════\n"
        "  NOW WRITE YOUR SCRIPT — about YOUR topic, using YOUR outline\n"
        "  and verified claims. Apply the structural craft above.\n"
        "══════════════════════════════════════════════════════════════\n"
    )
    return prompt
