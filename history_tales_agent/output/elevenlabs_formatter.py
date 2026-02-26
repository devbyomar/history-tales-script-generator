"""ElevenLabs TTS formatter — converts pipeline script to voice-ready text.

Produces TWO output variants from the same raw script:

  1. **v3** — optimised for Eleven v3 (audio tags for emotional direction,
     ellipsis / punctuation for pauses, emphasis via CAPS).
     v3 does NOT support SSML ``<break>`` tags.

  2. **Flash / Turbo** — optimised for Eleven Flash v2.5, Turbo v2.5, and
     Multilingual v2 (SSML ``<break>`` tags for pacing, no audio tags,
     aggressive text normalisation for smaller models).

Both variants share the same stripping, emphasis, and hedge-dedup steps.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# 1.  STRIPPING — remove everything the narrator should NOT read
# ──────────────────────────────────────────────────────────────

# Section headers the pipeline inserts
_SECTION_HEADER_RE = re.compile(
    r"^---\s*\[.*?\]\s*---\s*$", re.MULTILINE
)

# Markdown title line
_MD_TITLE_RE = re.compile(r"^#\s+.+$", re.MULTILINE)

# Re-hook labels  ("Re-hook: …")
_REHOOK_RE = re.compile(
    r"^Re-hook:\s*.+$", re.MULTILINE
)

# Cross-cut labels at the START of a paragraph.
# Matches several variants the LLM produces:
#   "Cross-cut: …"  /  "Cross-cut one. …"  /  "Cross-cut fourteen, 02:15. …"
#   "One more cross-cut, …"  /  "Define the countdown. …"
# The label (and any trailing period/comma) is stripped; narration after it is kept.
_CROSSCUT_LABEL_RE = re.compile(
    r"^Cross-cut(?:\s+\w+)?[.:,]\s*",
    re.MULTILINE,
)

# Standalone stage-direction lines that are NOT narration.
# e.g. "Define the countdown. T-0 is 23:45, the moment Oko first reports…"
# e.g. "Post-incident finding. Time: unspecified here, …"
# These start with a short directive phrase followed by a period, then scene context.
_STAGE_DIRECTION_RE = re.compile(
    r"^(?:Define the countdown|Post-incident finding)\.\s*",
    re.MULTILINE,
)

# Mid-sentence "one more cross-cut" phrasing
_INLINE_CROSSCUT_RE = re.compile(
    r"One more cross-cut,?\s*(?:narrow and )?(?:internal\.?\s*)?",
    re.IGNORECASE,
)

# Pivot labels
_PIVOT_LABEL_RE = re.compile(r"^Pivot:\s*", re.MULTILINE)

# On-screen advisory / VO note — entire paragraph
_ONSCREEN_RE = re.compile(
    r"^On-screen advisory.*?(?=\n\n|\Z)", re.MULTILINE | re.DOTALL
)

# Disclaimer at the very end
_DISCLAIMER_RE = re.compile(
    r"^This documentary script is a historical synthesis.*$", re.MULTILINE
)

# CTA section (whole block from "--- [CTA] ---" to end)
_CTA_BLOCK_RE = re.compile(
    r"---\s*\[CTA\]\s*---.*", re.DOTALL
)

# Timestamps like "T-48:00 (June 4, 1944, 22:00) —"  or  "T-00:00 (June 6, 22:00)."
# These are visual on-screen countdown markers — strip them.
_TIMESTAMP_RE = re.compile(
    r"T-[\d:?+]+\s*(?:\([^)]*\))?\s*[—–.\s]*"
)

# Source attribution phrases — safety net for any "According to Wikipedia" etc.
# Strips the attribution prefix while keeping the factual content.
# e.g. "According to Wikipedia, Harris was..." → "Harris was..."
# e.g. "According to Wikipedia's Juan Pujol García entry, ..." → "..."
# e.g. "Wikipedia says ..." → "..."
_SOURCE_ATTRIBUTION_RE = re.compile(
    r"(?:According to|As (?:noted|documented|recorded|described) (?:by|in|on))"
    r"\s+(?:Wikipedia(?:'s\s+[^,]+?)?|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:'s\s+[^,]+?)?)"
    r"(?:\s+(?:article|entry|page|biography|source|account))?"
    r"[,;]\s*",
    re.IGNORECASE,
)

# Catch remaining "Wikipedia says/states/notes" patterns
_WIKI_VERB_RE = re.compile(
    r"Wikipedia\s+(?:says|states|notes|reports|indicates|mentions|records)\s+(?:that\s+)?",
    re.IGNORECASE,
)

# Hedge-phrase deduplication — safety net for over-hedged scripts.
# Matches sentence-initial or mid-sentence hedging like:
#   "Evidence suggests that ...", "The evidence suggests ...",
#   "Records show that ...", "The evidence points to ..."
# After the first 2 occurrences in the entire script, remaining hedges are stripped
# (the factual content after the hedge is kept).
_HEDGE_PHRASE_RE = re.compile(
    r"(?:The\s+)?(?:evidence\s+suggests|evidence\s+points?\s+to|records\s+show|records\s+indicate)"
    r"(?:\s+that)?\s+",
    re.IGNORECASE,
)

_MAX_HEDGE_OCCURRENCES = 2

# ──────────────────────────────────────────────────────────────
# 2.  EMOTIONAL DIRECTION — audio tag injection
# ──────────────────────────────────────────────────────────────
#
# Strategy: Pattern-match on NARRATIVE CONTEXT, not just keywords.
# A great voice director reads the SCENE, not a glossary.
#
# We classify sentences into delivery modes and prepend the
# appropriate Eleven v3 audio tag.

# --- 2a. Sentence-level patterns → audio tags ---

# Revelations, twists, dramatic turns
_REVELATION_PATTERNS = [
    re.compile(r"\b(?:twist|secret|hidden|covert|concealed|reveal)\b", re.I),
    re.compile(r"\bthat (?:was|is) (?:the|this) (?:real|true|actual)\b", re.I),
    re.compile(r"\bno[- ]?one (?:knew|suspected|realized)\b", re.I),
]

# Tension, urgency, danger
_TENSION_PATTERNS = [
    re.compile(r"\bif (?:he|she|they|it) (?:warned|failed|missed|slipped)\b", re.I),
    re.compile(r"\b(?:lethal|deadly|fatal|irreversible|collapse)\b", re.I),
    re.compile(r"\b(?:scramble|alarm|panic|desperate|risk everything)\b", re.I),
    re.compile(r"\bcould (?:not|never) afford\b", re.I),
    re.compile(r"\bhung from\b", re.I),
]

# Quiet, solemn, reflective moments
_SOLEMN_PATTERNS = [
    re.compile(r"\b(?:silence|quiet|still|hush|exhale[ds]?)\b", re.I),
    re.compile(r"\b(?:remember|endure[sd]?|remain[sed]*|outlive[sd]?)\b", re.I),
    re.compile(r"\b(?:buried|forgotten|empty|hollow|absence[s]?)\b", re.I),
    re.compile(r"\bwhat endures\b", re.I),
]

# Defiance, resolve, determination
_RESOLVE_PATTERNS = [
    re.compile(r"\bhe (?:decided|chose|resolved|committed|would (?:not|never))\b", re.I),
    re.compile(r"\bshe (?:decided|chose|resolved|committed|would (?:not|never))\b", re.I),
    re.compile(r"\bnever again\b", re.I),
    re.compile(r"\bfor the good of humanity\b", re.I),
]

# Visceral / sensory-heavy imagery (slow down, let it land)
_SENSORY_PATTERNS = [
    re.compile(r"\bsmell(?:ed|s)? (?:of|like|faintly)\b", re.I),
    re.compile(r"\btast(?:e|ed) (?:of|like)\b", re.I),
    re.compile(r"\bthe (?:sound|hiss|hum|buzz|whine|clatter|crack|thump)\b", re.I),
    re.compile(r"\bfelt (?:slick|cold|warm|damp|rough|smooth)\b", re.I),
]

# Rhetorical questions aimed at the viewer
_QUESTION_PATTERN = re.compile(
    r"^(?:What|How|Why|Can|Will|Which|Picture|Think|Hear|See|Remember)\b.*\?$"
)

# Direct quoted speech
_DIALOGUE_PATTERN = re.compile(r'"[^"]{8,}"')

# Climactic / peak-stakes sentences (Act 3 payoff)
_CLIMAX_PATTERNS = [
    re.compile(r"\bkeyed the (?:first|last)\b", re.I),
    re.compile(r"\bthe (?:network|legend|channel) held\b", re.I),
    re.compile(r"\b(?:irreversible|consequence|cemented|locked)\b", re.I),
    re.compile(r"\bdawn broke\b", re.I),
    re.compile(r"\bmen crouched and ran and fell\b", re.I),
]


def _classify_sentence(sentence: str) -> str | None:
    """Return the best audio tag for a sentence, or None if neutral."""
    s = sentence.strip()
    if not s:
        return None

    # Order matters — more specific patterns first, broader later.

    # Rhetorical questions get a conspiratorial lean-in
    if _QUESTION_PATTERN.match(s):
        return "[curious]"

    # Climactic payoff
    for p in _CLIMAX_PATTERNS:
        if p.search(s):
            return "[intense]"

    # Tension / danger
    for p in _TENSION_PATTERNS:
        if p.search(s):
            return "[tense]"

    # Revelation / twist
    for p in _REVELATION_PATTERNS:
        if p.search(s):
            return "[intrigued]"

    # Defiance / resolve
    for p in _RESOLVE_PATTERNS:
        if p.search(s):
            return "[resolute]"

    # Solemn / reflective
    for p in _SOLEMN_PATTERNS:
        if p.search(s):
            return "[solemn]"

    # Rich sensory imagery — no tag, but we'll use pacing (handled below)
    for p in _SENSORY_PATTERNS:
        if p.search(s):
            return None  # pacing handles these

    return None


# ──────────────────────────────────────────────────────────────
# 3.  PACING — pauses, emphasis, breath marks
# ──────────────────────────────────────────────────────────────

def _apply_pacing_ssml(text: str) -> str:
    """Add SSML breaks for Flash / Turbo / Multilingual v2 models."""

    BREAK_15 = '<break time="1.5s" />'
    BREAK_05 = '<break time="0.5s" />'
    BREAK_04 = '<break time="0.4s" />'
    BREAK_03 = '<break time="0.3s" />'

    # 3a.  Paragraph breaks → 1.5s pause (scene transition)
    text = re.sub(r"\n\n+", f"\n\n{BREAK_15}\n\n", text)

    # 3b.  Em dashes used for dramatic parentheticals → short pause around them
    text = re.sub(r"(\w)—(\w)", r"\1 … \2", text)

    # 3c.  Sentences ending with "?" get a micro-pause before them
    text = re.sub(
        r"\.\s+([A-Z][^.?!]*\?)",
        lambda m: f". {BREAK_05} {m.group(1)}",
        text,
    )

    # 3d.  Lists of short fragments (e.g. "By absences. By units. By orders.")
    text = re.sub(
        r"\.\s+(By\s)",
        lambda m: f". {BREAK_03} {m.group(1)}",
        text,
    )

    # 3e.  "Close enough that" repetition pattern → staccato pacing
    text = re.sub(
        r"\.\s+(Close enough that)",
        lambda m: f". {BREAK_04} {m.group(1)}",
        text,
    )

    return text


def _apply_pacing_v3(text: str) -> str:
    """Add punctuation-based pauses for Eleven v3 (no SSML support).

    Uses ellipsis (…), em dashes, and line breaks — the pause cues
    that v3 actually responds to.
    """

    # 3a.  Paragraph breaks → double newline + ellipsis breath
    text = re.sub(r"\n\n+", "\n\n...\n\n", text)

    # 3b.  Em dashes → ellipsis (v3 reads "…" as a natural hesitation)
    text = re.sub(r"(\w)—(\w)", r"\1... \2", text)

    # 3c.  Pre-question pause via ellipsis
    text = re.sub(
        r"\.\s+([A-Z][^.?!]*\?)",
        lambda m: f". ... {m.group(1)}",
        text,
    )

    # 3d.  Staccato fragments
    text = re.sub(r"\.\s+(By\s)", r". ... \1", text)

    # 3e.  "Close enough that" pattern
    text = re.sub(r"\.\s+(Close enough that)", r". ... \1", text)

    return text


# Legacy alias — keeps existing tests / imports working
_apply_pacing = _apply_pacing_ssml


# ──────────────────────────────────────────────────────────────
# 4.  EMPHASIS — capitalise key payoff words
# ──────────────────────────────────────────────────────────────

# Words/phrases that should land harder when spoken
_EMPHASIS_PHRASES = [
    # Format: (pattern, replacement)
    (re.compile(r"\bnever again\b", re.I), "NEVER again"),
    (re.compile(r"\bfor the good of humanity\b", re.I), "for the GOOD of humanity"),
    (re.compile(r"\brisk everything\b", re.I), "risk EVERYTHING"),
    (re.compile(r"\bnone of them existed\b", re.I), "NONE of them existed"),
    (re.compile(r"\bthe network held\b", re.I), "the network HELD"),
    (re.compile(r"\birreversible\b", re.I), "IRREVERSIBLE"),
    (re.compile(r"\btwenty-seven\b", re.I), "TWENTY-SEVEN"),
    (re.compile(r"\b27 entirely invented\b"), "twenty-seven ENTIRELY invented"),
    (re.compile(r"\bone perfectly wrong message\b", re.I), "one PERFECTLY wrong message"),
]


def _apply_emphasis(text: str) -> str:
    """Capitalise key payoff words for vocal stress."""
    for pattern, replacement in _EMPHASIS_PHRASES:
        text = pattern.sub(replacement, text)
    return text


# ──────────────────────────────────────────────────────────────
# 5.  TEXT NORMALISATION for TTS
# ──────────────────────────────────────────────────────────────

def _normalise_for_tts(text: str) -> str:
    """Clean up text artefacts that TTS engines stumble on."""

    # 5a.  Markdown artefacts
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*([^*]+)\*", r"\1", text)       # italic
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)  # headings

    # 5b.  Smart quotes → straight (ElevenLabs handles straight better)
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")

    # 5c.  En/em dashes normalisation (em handled by pacing already,
    #       but clean up any remaining en-dashes)
    text = text.replace("\u2013", " — ")

    # 5d.  Ellipsis character → three dots (more consistent TTS pause)
    text = text.replace("\u2026", "...")

    # 5e.  Multiple spaces → single
    text = re.sub(r"  +", " ", text)

    # 5f.  Abbreviations that TTS might mispronounce
    text = text.replace("MI5", "M.I. Five")
    text = text.replace("MI6", "M.I. Six")
    text = re.sub(r"\bVO\b", "voice-over", text)
    text = re.sub(r"\bD-Day\b", "D-Day", text)  # already fine
    text = re.sub(r"\bPas-de-Calais\b", "Pah-de-Callay", text)

    return text


def _normalise_for_tts_flash(text: str) -> str:
    """Aggressive normalisation for Flash / Turbo / v2 models.

    These smaller models struggle more with numbers, abbreviations,
    and uncommon formatting than v3.  We spell things out explicitly.
    """
    # Start with standard normalisation
    text = _normalise_for_tts(text)

    # 5g.  Ordinal numbers — spell out common ones
    _ordinals = {
        "1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth",
        "5th": "fifth", "6th": "sixth", "7th": "seventh", "8th": "eighth",
        "9th": "ninth", "10th": "tenth", "11th": "eleventh", "12th": "twelfth",
        "13th": "thirteenth", "14th": "fourteenth", "15th": "fifteenth",
        "16th": "sixteenth", "17th": "seventeenth", "18th": "eighteenth",
        "19th": "nineteenth", "20th": "twentieth", "21st": "twenty-first",
    }
    for k, v in _ordinals.items():
        text = re.sub(rf"\b{k}\b", v, text, flags=re.IGNORECASE)

    # 5h.  Common military / historical abbreviations
    text = re.sub(r"\bHQ\b", "headquarters", text)
    text = re.sub(r"\bGHQ\b", "general headquarters", text)
    text = re.sub(r"\bPOW\b", "prisoner of war", text)
    text = re.sub(r"\bKIA\b", "killed in action", text)
    text = re.sub(r"\bMIA\b", "missing in action", text)
    text = re.sub(r"\bSS\b", "S.S.", text)
    text = re.sub(r"\bRAF\b", "R.A.F.", text)
    text = re.sub(r"\bCIA\b", "C.I.A.", text)
    text = re.sub(r"\bFBI\b", "F.B.I.", text)
    text = re.sub(r"\bKGB\b", "K.G.B.", text)
    text = re.sub(r"\bNATO\b", "NATO", text)  # already pronounceable
    text = re.sub(r"\bUSSR\b", "U.S.S.R.", text)

    # 5i.  Percentage sign
    text = re.sub(r"(\d+)%", r"\1 percent", text)

    # 5j.  Ampersand
    text = text.replace(" & ", " and ")

    return text


# ──────────────────────────────────────────────────────────────
# 6.  AUDIO TAG INJECTION — paragraph-level emotional direction
# ──────────────────────────────────────────────────────────────

def _inject_audio_tags(text: str) -> str:
    """Add Eleven v3 audio tags at the start of paragraphs based on
    emotional context analysis of the opening sentence."""

    paragraphs = text.split("\n\n")
    result = []

    prev_tag = None
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Skip break tags standing alone
        if para.startswith("<break"):
            result.append(para)
            continue

        # Get the first sentence for classification
        first_sentence = _extract_first_sentence(para)
        tag = _classify_sentence(first_sentence)

        # Avoid repeating the same tag consecutively — monotony kills delivery
        if tag and tag == prev_tag:
            tag = None

        if tag:
            para = f"{tag} {para}"
            prev_tag = tag
        else:
            prev_tag = None

        result.append(para)

    return "\n\n".join(result)


def _extract_first_sentence(text: str) -> str:
    """Extract the first sentence from a paragraph."""
    # Match up to the first sentence-ending punctuation
    m = re.match(r"^(.*?[.!?])\s", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: first 200 chars
    return text[:200]


# ──────────────────────────────────────────────────────────────
# 7.  SECTION TRANSITION BREATHS
# ──────────────────────────────────────────────────────────────

def _add_section_transitions_ssml(text: str) -> str:
    """Insert SSML 2s pauses at major scene changes (Flash / Turbo)."""
    text = re.sub(
        r"(\.\s*)\n\n(<break[^>]*>\s*\n\n)?(\d{4}|London|Madrid|Dawn|Back in)",
        r"\1\n\n<break time=\"2.0s\" />\n\n\3",
        text,
    )
    return text


def _add_section_transitions_v3(text: str) -> str:
    """Insert ellipsis-based scene-change breaths for v3."""
    text = re.sub(
        r"(\.\s*)\n\n(\.\.\.\s*\n\n)?(\d{4}|London|Madrid|Dawn|Back in)",
        r"\1\n\n...\n\n\3",
        text,
    )
    return text


# Legacy alias
_add_section_transitions = _add_section_transitions_ssml


# ──────────────────────────────────────────────────────────────
# 8.  DIALOGUE TREATMENT
# ──────────────────────────────────────────────────────────────

def _treat_dialogue_ssml(text: str) -> str:
    """Add SSML micro-pause before quoted speech (Flash / Turbo)."""
    text = re.sub(
        r'(\w[.:,])\s+"([A-Z])',
        r'\1 <break time="0.3s" /> "\2',
        text,
    )
    return text


def _treat_dialogue_v3(text: str) -> str:
    """Add ellipsis pause before quoted speech (v3 — no SSML)."""
    text = re.sub(
        r'(\w[.:,])\s+"([A-Z])',
        r'\1 ... "\2',
        text,
    )
    return text


# Legacy alias
_treat_dialogue = _treat_dialogue_ssml


# ──────────────────────────────────────────────────────────────
# 8b. HEDGE DEDUPLICATION — strip excessive hedging phrases
# ──────────────────────────────────────────────────────────────

def _deduplicate_hedges(text: str) -> str:
    """Keep at most _MAX_HEDGE_OCCURRENCES hedge phrases; strip the rest.

    When a hedge is stripped the factual content that follows is kept,
    with its first letter capitalised so the sentence still reads
    correctly.
    """
    count = 0

    def _replacer(m: re.Match) -> str:
        nonlocal count
        count += 1
        if count <= _MAX_HEDGE_OCCURRENCES:
            return m.group(0)  # keep this one
        # Strip the hedge, capitalise the continuation
        return ""

    result = _HEDGE_PHRASE_RE.sub(_replacer, text)
    # Capitalise the first letter after a stripped hedge at sentence start
    # e.g. "  potiorek" → "  Potiorek"
    result = re.sub(r"(?<=\.\s)([a-z])", lambda m: m.group(1).upper(), result)
    result = re.sub(r"(?<=\n)([a-z])", lambda m: m.group(1).upper(), result)
    return result


# ──────────────────────────────────────────────────────────────
# 9.  MASTER PIPELINES
# ──────────────────────────────────────────────────────────────

def _strip_structural(script: str) -> str:
    """Step 1 — shared stripping of structural markers."""
    text = script
    text = _CTA_BLOCK_RE.sub("", text)
    text = _SECTION_HEADER_RE.sub("", text)
    text = _MD_TITLE_RE.sub("", text)
    text = _REHOOK_RE.sub("", text)
    text = _CROSSCUT_LABEL_RE.sub("", text)
    text = _INLINE_CROSSCUT_RE.sub("", text)
    text = _STAGE_DIRECTION_RE.sub("", text)
    text = _PIVOT_LABEL_RE.sub("", text)
    text = _ONSCREEN_RE.sub("", text)
    text = _DISCLAIMER_RE.sub("", text)
    text = _TIMESTAMP_RE.sub("", text)
    text = _SOURCE_ATTRIBUTION_RE.sub("", text)
    text = _WIKI_VERB_RE.sub("", text)
    text = _deduplicate_hedges(text)
    return text


def _final_cleanup(text: str) -> str:
    """Step 8 — shared final cleanup."""
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = text.strip()
    text += "\n"
    return text


# ── 9a.  v3 pipeline ─────────────────────────────────────────

def format_elevenlabs_v3(script: str) -> str:
    """Full pipeline: raw script → Eleven v3-ready narration text.

    v3 supports audio tags ([curious], [tense], etc.) and emphasis
    via CAPS. It does NOT support SSML <break> tags. Pauses are
    achieved via ellipsis (…) and punctuation.
    """
    text = _strip_structural(script)
    text = _normalise_for_tts(text)
    text = _apply_emphasis(text)
    text = _apply_pacing_v3(text)
    text = _treat_dialogue_v3(text)
    text = _inject_audio_tags(text)
    text = _add_section_transitions_v3(text)
    return _final_cleanup(text)


# ── 9b.  Flash / Turbo pipeline ──────────────────────────────

def format_elevenlabs_flash(script: str) -> str:
    """Full pipeline: raw script → Eleven Flash / Turbo-ready text.

    Flash v2.5, Turbo v2.5, and Multilingual v2 support SSML
    <break> tags but do NOT support audio tags. Text normalisation
    is more aggressive (spell out abbreviations, ordinals, etc.)
    because these are smaller models.
    """
    text = _strip_structural(script)
    text = _normalise_for_tts_flash(text)
    text = _apply_emphasis(text)
    text = _apply_pacing_ssml(text)
    text = _treat_dialogue_ssml(text)
    # NO audio tag injection — Flash/Turbo ignore them
    text = _add_section_transitions_ssml(text)
    return _final_cleanup(text)


# ── 9c.  Legacy alias — keeps old call-sites working ─────────

def format_elevenlabs(script: str) -> str:
    """Legacy pipeline — produces Flash/Turbo output with audio tags.

    Maintained for backward compatibility with existing tests.
    New code should use ``format_elevenlabs_v3`` or
    ``format_elevenlabs_flash`` directly.
    """
    text = _strip_structural(script)
    text = _normalise_for_tts(text)
    text = _apply_emphasis(text)
    text = _apply_pacing_ssml(text)
    text = _treat_dialogue_ssml(text)
    text = _inject_audio_tags(text)
    text = _add_section_transitions_ssml(text)
    return _final_cleanup(text)


# ──────────────────────────────────────────────────────────────
# 10.  FILE WRITER (called from formatter.py)
# ──────────────────────────────────────────────────────────────

def write_elevenlabs_script(
    state: dict[str, Any],
    output_dir: str = "output",
) -> tuple[Path, Path]:
    """Write both ElevenLabs-ready narration files.

    Creates:
        output/script_elevenlabs_v3.txt   — for Eleven v3
        output/script_elevenlabs_flash.txt — for Flash / Turbo / v2

    Returns tuple of (v3_path, flash_path).
    """
    script = state.get("final_script", "")
    if not script:
        logger.warning("elevenlabs_no_script")
        out = Path(output_dir)
        return out / "script_elevenlabs_v3.txt", out / "script_elevenlabs_flash.txt"

    chosen = state.get("chosen_topic")
    title = chosen.title if chosen else "Untitled"

    v3_text = format_elevenlabs_v3(script)
    flash_text = format_elevenlabs_flash(script)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    v3_path = out / "script_elevenlabs_v3.txt"
    v3_path.write_text(v3_text, encoding="utf-8")
    logger.info(
        "wrote_elevenlabs_v3",
        path=str(v3_path),
        words=len(v3_text.split()),
        title=title,
    )

    flash_path = out / "script_elevenlabs_flash.txt"
    flash_path.write_text(flash_text, encoding="utf-8")
    logger.info(
        "wrote_elevenlabs_flash",
        path=str(flash_path),
        words=len(flash_text.split()),
        title=title,
    )

    return v3_path, flash_path
