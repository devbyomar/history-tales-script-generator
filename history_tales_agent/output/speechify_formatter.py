"""Speechify TTS formatter — converts pipeline script to paste-ready plain text.

Speechify reads at ~115 WPM.  The output is pure, clean narration:
- No ellipses, em dashes, SSML break tags, audio tags, or brackets
- No markdown headings, bold/italic, section labels, or stage directions
- Sentences kept concise (target 10–18 words, hard ceiling 25)
- Paragraphs capped at 2 sentences for breathing room
- Word count validated within ±3% of the 115-WPM target
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from history_tales_agent.config import (
    SPEECHIFY_WORDS_PER_MINUTE,
    SPEECHIFY_WORD_TOLERANCE,
)
from history_tales_agent.output.elevenlabs_formatter import _strip_structural
from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# 1.  SPEECHIFY-SPECIFIC STRIPPING
# ──────────────────────────────────────────────────────────────

# Audio emotion tags: [curious], [tense], [solemn], etc.
_AUDIO_TAG_RE = re.compile(r"\[(?:curious|tense|solemn|resolve|sensory|whispered|climax|revelation)\]\s*", re.IGNORECASE)

# SSML break tags: <break time="1.5s" />
_SSML_BREAK_RE = re.compile(r"<break\s+time=[\"'][^\"']*[\"']\s*/?>")

# Bracketed notes: [C001], [pause], [beat], etc.
_BRACKET_NOTE_RE = re.compile(r"\[[^\]]{1,40}\]")

# Ellipses (three dots or Unicode ellipsis)
_ELLIPSIS_RE = re.compile(r"\.{3}|\u2026")

# Em dashes (—) and en dashes (–) → comma or period depending on context
_EM_DASH_RE = re.compile(r"\s*[—–]\s*")

# CAPS emphasis words (3+ consecutive uppercase letters that are NOT acronyms)
# We keep known acronyms intact but lower-case emphasis words like "NEVER", "EVERYTHING"
_CAPS_WORD_RE = re.compile(r"\b([A-Z]{3,})\b")

# Known acronyms to preserve in upper case
_KNOWN_ACRONYMS = {
    "CIA", "FBI", "KGB", "NATO", "USSR", "RAF", "POW",
    "KIA", "MIA", "HQ", "GHQ", "BBC", "USA", "III",
    "WWI", "WWII", "SAS", "SOE", "OSS", "NKVD", "SS",
}

# Markdown artefacts
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC_RE = re.compile(r"\*([^*]+)\*")
_MD_HEADING_RE = re.compile(r"^#+\s*", flags=re.MULTILINE)

# Smart quotes → straight
_SMART_QUOTES = [
    ("\u201c", '"'), ("\u201d", '"'),
    ("\u2018", "'"), ("\u2019", "'"),
]

# Multiple consecutive blank lines → single
_MULTI_BLANK_RE = re.compile(r"\n{3,}")

# Multiple spaces → single
_MULTI_SPACE_RE = re.compile(r"  +")


def _strip_speechify_artifacts(text: str) -> str:
    """Remove all TTS-specific and formatting artifacts for Speechify."""

    # Audio tags
    text = _AUDIO_TAG_RE.sub("", text)

    # SSML breaks
    text = _SSML_BREAK_RE.sub("", text)

    # Bracketed notes
    text = _BRACKET_NOTE_RE.sub("", text)

    # Ellipses → nothing (let surrounding punctuation close the gap)
    text = _ELLIPSIS_RE.sub("", text)

    # Em/en dashes → comma (keeps the sentence flowing)
    text = _EM_DASH_RE.sub(", ", text)

    # Markdown
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_ITALIC_RE.sub(r"\1", text)
    text = _MD_HEADING_RE.sub("", text)

    # CAPS emphasis → title case (keeps natural reading)
    def _lower_caps(m: re.Match) -> str:
        word = m.group(1)
        if word in _KNOWN_ACRONYMS:
            return word
        return word.capitalize()

    text = _CAPS_WORD_RE.sub(_lower_caps, text)

    # Smart quotes
    for old, new in _SMART_QUOTES:
        text = text.replace(old, new)

    # Unicode ellipsis character (belt and suspenders)
    text = text.replace("\u2026", "")

    # Multiple spaces
    text = _MULTI_SPACE_RE.sub(" ", text)

    # Fix double commas / comma-period from dash replacement
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\.\s*,", ".", text)

    # Fix leading commas at line start
    text = re.sub(r"^\s*,\s*", "", text, flags=re.MULTILINE)

    return text


# ──────────────────────────────────────────────────────────────
# 2.  SENTENCE-LENGTH ENFORCEMENT
# ──────────────────────────────────────────────────────────────

# Sentence boundary — period, exclamation, or question mark followed by space
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Maximum words per sentence before we try to split
_MAX_SENTENCE_WORDS = 25

# Natural split points for long sentences (ordered by preference)
_SPLIT_POINTS = [
    re.compile(r",\s+(?:but|yet|so|and|or|because|while|although|though|which|where|when)\s+", re.IGNORECASE),
    re.compile(r";\s+"),
    re.compile(r",\s+"),
]


def _enforce_sentence_length(text: str) -> str:
    """Split sentences longer than _MAX_SENTENCE_WORDS at natural boundaries."""
    paragraphs = text.split("\n\n")
    result = []

    for para in paragraphs:
        sentences = _SENTENCE_SPLIT_RE.split(para.strip())
        new_sentences = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(sent.split()) <= _MAX_SENTENCE_WORDS:
                new_sentences.append(sent)
            else:
                new_sentences.extend(_split_long_sentence(sent))
        result.append(" ".join(new_sentences))

    return "\n\n".join(result)


def _split_long_sentence(sentence: str) -> list[str]:
    """Split a single long sentence into shorter ones at natural points."""
    words = sentence.split()
    if len(words) <= _MAX_SENTENCE_WORDS:
        return [sentence]

    for pattern in _SPLIT_POINTS:
        parts = pattern.split(sentence, maxsplit=1)
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            # Ensure left part ends with proper punctuation
            if left and not left[-1] in ".!?":
                left += "."
            # Ensure right part starts with upper case
            if right and right[0].islower():
                right = right[0].upper() + right[1:]
            # Recursively check the parts
            result = []
            result.extend(_split_long_sentence(left))
            result.extend(_split_long_sentence(right))
            return result

    # No good split point found — return as-is
    return [sentence]


# ──────────────────────────────────────────────────────────────
# 3.  PARAGRAPH-LENGTH ENFORCEMENT (max 2 sentences)
# ──────────────────────────────────────────────────────────────

_MAX_SENTENCES_PER_PARA = 2


def _enforce_paragraph_length(text: str) -> str:
    """Ensure no paragraph has more than _MAX_SENTENCES_PER_PARA sentences."""
    paragraphs = text.split("\n\n")
    result = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        sentences = _SENTENCE_SPLIT_RE.split(para)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Chunk into groups of _MAX_SENTENCES_PER_PARA
        for i in range(0, len(sentences), _MAX_SENTENCES_PER_PARA):
            chunk = sentences[i : i + _MAX_SENTENCES_PER_PARA]
            result.append(" ".join(chunk))

    return "\n\n".join(result)


# ──────────────────────────────────────────────────────────────
# 4.  WORD-COUNT VALIDATION
# ──────────────────────────────────────────────────────────────


def validate_speechify_word_count(
    text: str,
    video_length_minutes: int,
) -> dict[str, Any]:
    """Validate that word count is within ±3% of the 115-WPM target.

    Returns a dict with validation details (does NOT raise — the formatter
    logs a warning and the file is still written).
    """
    word_count = len(text.split())
    target = video_length_minutes * SPEECHIFY_WORDS_PER_MINUTE
    min_words = int(target * (1 - SPEECHIFY_WORD_TOLERANCE))
    max_words = int(target * (1 + SPEECHIFY_WORD_TOLERANCE))
    in_range = min_words <= word_count <= max_words

    if target > 0:
        deviation_pct = abs(word_count - target) / target * 100
    else:
        deviation_pct = 0.0

    return {
        "word_count": word_count,
        "target": target,
        "min_words": min_words,
        "max_words": max_words,
        "in_range": in_range,
        "deviation_pct": round(deviation_pct, 2),
    }


# ──────────────────────────────────────────────────────────────
# 5.  FINAL CLEANUP
# ──────────────────────────────────────────────────────────────


def _final_cleanup(text: str) -> str:
    """Normalise whitespace and ensure clean ending."""
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    text = text.strip()
    # Ensure file ends with a newline
    if text and not text.endswith("\n"):
        text += "\n"
    return text


# ──────────────────────────────────────────────────────────────
# 6.  MASTER PIPELINE
# ──────────────────────────────────────────────────────────────


def format_speechify(script: str) -> str:
    """Full pipeline: raw script → Speechify-ready plain narration.

    Steps:
      1. Strip structural markers (shared with ElevenLabs)
      2. Strip Speechify-specific artifacts (audio tags, SSML, brackets, etc.)
      3. Enforce sentence length (≤25 words)
      4. Enforce paragraph length (≤2 sentences)
      5. Final cleanup
    """
    text = _strip_structural(script)
    text = _strip_speechify_artifacts(text)
    text = _enforce_sentence_length(text)
    text = _enforce_paragraph_length(text)
    return _final_cleanup(text)


# ──────────────────────────────────────────────────────────────
# 7.  FILE WRITER (called from formatter.py)
# ──────────────────────────────────────────────────────────────


def write_speechify_script(
    state: dict[str, Any],
    output_dir: str = "output",
) -> Path:
    """Write the Speechify-ready plain narration file.

    Creates:
        output/script_speechify.txt

    Returns the path to the written file.
    """
    script = state.get("final_script", "")
    if not script:
        logger.warning("speechify_no_script")
        return Path(output_dir) / "script_speechify.txt"

    chosen = state.get("chosen_topic")
    title = chosen.title if chosen else "Untitled"
    video_length = state.get("video_length_minutes", 12)

    speechify_text = format_speechify(script)

    # Validate word count
    validation = validate_speechify_word_count(speechify_text, video_length)
    if not validation["in_range"]:
        logger.warning(
            "speechify_word_count_out_of_range",
            word_count=validation["word_count"],
            target=validation["target"],
            min_words=validation["min_words"],
            max_words=validation["max_words"],
            deviation_pct=validation["deviation_pct"],
            title=title,
        )
    else:
        logger.info(
            "speechify_word_count_ok",
            word_count=validation["word_count"],
            target=validation["target"],
            deviation_pct=validation["deviation_pct"],
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    speechify_path = out / "script_speechify.txt"
    speechify_path.write_text(speechify_text, encoding="utf-8")
    logger.info(
        "wrote_speechify",
        path=str(speechify_path),
        words=validation["word_count"],
        title=title,
    )

    return speechify_path
