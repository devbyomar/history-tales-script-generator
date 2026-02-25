"""ElevenLabs TTS formatter — converts pipeline script to voice-ready text.

Strips structural markers, injects Eleven v3 audio tags, adds SSML break tags
for pacing, normalises text for TTS, and applies emotional direction based on
narrative context analysis.

Output: a plain-text file ready for seamless paste into ElevenLabs.
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

# Cross-cut labels at the START of a paragraph  ("Cross-cut: …")
# We keep the content after the label — the narrator should read the scene.
_CROSSCUT_LABEL_RE = re.compile(r"^Cross-cut:\s*", re.MULTILINE)

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

def _apply_pacing(text: str) -> str:
    """Add SSML breaks and emphasis for natural documentary delivery."""

    BREAK_15 = '<break time="1.5s" />'
    BREAK_05 = '<break time="0.5s" />'
    BREAK_04 = '<break time="0.4s" />'
    BREAK_03 = '<break time="0.3s" />'

    # 3a.  Paragraph breaks → 1.5s pause (scene transition)
    text = re.sub(r"\n\n+", f"\n\n{BREAK_15}\n\n", text)

    # 3b.  Em dashes used for dramatic parentheticals → short pause around them
    #       "Harris's cigarette—Players Navy Cut, soft-packed—left a blister"
    #       becomes natural breath-pause territory.
    #       Replace "—" with " … " which ElevenLabs reads as a hesitation pause.
    #       But ONLY when used as parenthetical dashes (surrounded by words).
    text = re.sub(r"(\w)—(\w)", r"\1 … \2", text)

    # 3c.  Sentences ending with "?" get a micro-pause before them
    #       to let the question land with weight.
    text = re.sub(
        r"\.\s+([A-Z][^.?!]*\?)",
        lambda m: f". {BREAK_05} {m.group(1)}",
        text,
    )

    # 3d.  Lists of short fragments (e.g. "By absences. By units. By orders.")
    #       → add breath between each for staccato delivery
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

def _add_section_transitions(text: str) -> str:
    """Insert longer pauses where major story sections transition.

    After stripping section headers, we detect natural act boundaries
    by looking for temporal jumps or scene changes and add a 2s breath.
    """
    # After a paragraph that ends a scene, before a new time marker
    text = re.sub(
        r"(\.\s*)\n\n(<break[^>]*>\s*\n\n)?(\d{4}|London|Madrid|Dawn|Back in)",
        r"\1\n\n<break time=\"2.0s\" />\n\n\3",
        text,
    )
    return text


# ──────────────────────────────────────────────────────────────
# 8.  DIALOGUE TREATMENT
# ──────────────────────────────────────────────────────────────

def _treat_dialogue(text: str) -> str:
    """Add subtle delivery cues around quoted speech.

    ElevenLabs reads quoted text with a slight voice shift if
    we add a micro-pause before the quote. This mimics the narrator
    'stepping into character' briefly.
    """
    # Add a tiny pause before dialogue quotes that follow narration
    text = re.sub(
        r'(\w[.:,])\s+"([A-Z])',
        r'\1 <break time="0.3s" /> "\2',
        text,
    )
    return text


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
# 9.  MASTER PIPELINE
# ──────────────────────────────────────────────────────────────

def format_elevenlabs(script: str) -> str:
    """Full pipeline: raw script → ElevenLabs-ready narration text.

    Processing order matters:
    1. Strip structural markers (section headers, rehooks, CTA, etc.)
    2. Normalise text for TTS (abbreviations, smart quotes, markdown)
    3. Apply emphasis on payoff words
    4. Apply pacing (breaks, em-dash → ellipsis, staccato patterns)
    5. Treat dialogue (pre-quote pauses)
    6. Inject audio tags (emotional direction per paragraph)
    7. Add section transition breaths
    8. Final cleanup
    """

    text = script

    # ── Step 1: Strip ──
    text = _CTA_BLOCK_RE.sub("", text)
    text = _SECTION_HEADER_RE.sub("", text)
    text = _MD_TITLE_RE.sub("", text)
    text = _REHOOK_RE.sub("", text)
    text = _CROSSCUT_LABEL_RE.sub("", text)
    text = _PIVOT_LABEL_RE.sub("", text)
    text = _ONSCREEN_RE.sub("", text)
    text = _DISCLAIMER_RE.sub("", text)
    text = _TIMESTAMP_RE.sub("", text)
    text = _SOURCE_ATTRIBUTION_RE.sub("", text)
    text = _WIKI_VERB_RE.sub("", text)
    text = _deduplicate_hedges(text)

    # ── Step 2: Normalise ──
    text = _normalise_for_tts(text)

    # ── Step 3: Emphasis ──
    text = _apply_emphasis(text)

    # ── Step 4: Pacing ──
    text = _apply_pacing(text)

    # ── Step 5: Dialogue ──
    text = _treat_dialogue(text)

    # ── Step 6: Audio tags ──
    text = _inject_audio_tags(text)

    # ── Step 7: Section transitions ──
    text = _add_section_transitions(text)

    # ── Step 8: Final cleanup ──
    # Remove excessive blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # Remove leading/trailing whitespace
    text = text.strip()
    # Ensure single newline at end
    text += "\n"

    return text


# ──────────────────────────────────────────────────────────────
# 10.  FILE WRITER (called from formatter.py)
# ──────────────────────────────────────────────────────────────

def write_elevenlabs_script(
    state: dict[str, Any],
    output_dir: str = "output",
) -> Path:
    """Write the ElevenLabs-ready narration file.

    Returns the path to the written file.
    """
    script = state.get("final_script", "")
    if not script:
        logger.warning("elevenlabs_no_script")
        return Path(output_dir)

    chosen = state.get("chosen_topic")
    title = chosen.title if chosen else "Untitled"

    el_text = format_elevenlabs(script)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    el_path = out / "script_elevenlabs.txt"
    el_path.write_text(el_text, encoding="utf-8")

    word_count = len(el_text.split())
    logger.info(
        "wrote_elevenlabs_script",
        path=str(el_path),
        words=word_count,
        title=title,
    )

    return el_path
